"""CADCraft: write a device takeoff back onto a copy of the drawing.

`cad.count_devices` answers "how many"; an engineer reviewing that answer still
has to find each device on the sheet. This tool puts the answer where the
engineer looks: every counted insert is ringed in its system colour and tagged
with an item code, each system gets a device schedule (item, description, block,
quantity, unit), and — if room outlines are named — rooms are tinted and given
their area plus an area schedule.

Same discipline as the count it is built on:
  * Counting goes through `scan_inserts`, the same walk `cad.count_devices`
    uses, so the drawing and the BOQ cannot disagree.
  * Unmapped blocks are not dropped. They get their own red NOT COUNTED table,
    the schedule footer says INCOMPLETE, and the status is `missing_data`.
  * Everything added sits on three SPI_* layers, so a recipient can freeze or
    delete them and get the original drawing back. The original file is never
    written.
"""
from __future__ import annotations

import io
import time
from collections import Counter, defaultdict

from ezdxf import bbox
from ezdxf.enums import TextEntityAlignment
from pydantic import BaseModel, Field

from ..core import (ENGINE_VERSION, Assumption, InvalidInput, MissingItem,
                    OutputFile, Provenance, Storage, ToolResult, register, sha256)
from .count import scan_inserts
from .read_dxf import open_dxf
from .rooms import find_rooms
from .symbols import SymbolMap, default_map
from .units import describe

TAKEOFF_LAYER = "SPI_TAKEOFF"
SCHEDULE_LAYER = "SPI_SCHEDULE"
ROOMS_LAYER = "SPI_ROOMS"
DXF_MIME = "application/dxf"

#: AutoCAD Colour Index per system. Unknown systems cycle through the spares.
SYSTEM_COLOUR = {"fire_alarm": 1, "cctv": 5, "access_control": 3,
                 "public_address": 6, "voice_evacuation": 6,
                 "structured_cabling": 4, "data": 4, "intrusion": 30,
                 "nurse_call": 40, "bms": 140}
SPARE_COLOURS = (200, 30, 140, 40, 210)
SYSTEM_PREFIX = {"fire_alarm": "FA", "cctv": "CC", "access_control": "AC",
                 "public_address": "PA", "voice_evacuation": "VE",
                 "structured_cabling": "SC", "data": "DT", "intrusion": "IN",
                 "nurse_call": "NC", "bms": "BM"}
UNMAPPED_COLOUR = 1


class TakeoffSheetInput(BaseModel):
    document_id: str
    storage_key: str
    symbol_map: dict | None = Field(
        None, description="a SymbolMap as data — see cad/symbols.py. Omitted means "
                          "the generic default map, which is not a client standard.")
    layers: list[str] | None = Field(None, description="count only inserts on these layers")
    room_boundary_layers: list[str] | None = Field(
        None, description="layers with closed room outlines. Omitted means no room "
                          "tint, area labels or area schedule — which layer is "
                          "architectural is never guessed.")
    room_label_layers: list[str] | None = Field(
        None, description="layers with room names; default: any text layer")
    text_height: float | None = Field(
        None, gt=0, description="drawing units. Omitted means 1/150 of the drawing's "
                                "larger extent, recorded as an assumption.")
    table_x: float | None = Field(None, description="schedule top-left x; default right of the drawing")
    table_y: float | None = Field(None, description="schedule top-left y; default level with the drawing top")
    tag_devices: bool = Field(True, description="write the item code beside each ring")
    output_key: str | None = None
    output_name: str = "takeoff.dxf"


def _label(device_type: str) -> str:
    return device_type.replace("_", " ").strip().capitalize()


def _prefix(system: str) -> str:
    if system in SYSTEM_PREFIX:
        return SYSTEM_PREFIX[system]
    parts = [p for p in system.replace("-", "_").split("_") if p]
    return "".join(p[0] for p in parts[:2]).upper() or "X"


class _Table:
    """A ruled table drawn with lines and text, top-left anchored.

    Plain LINE/TEXT rather than ACAD_TABLE: every DXF viewer renders these, and
    ezdxf cannot round-trip ACAD_TABLE reliably.
    """

    def __init__(self, msp, x: float, y: float, h: float, widths: list[float], layer: str):
        self.msp, self.x, self.y, self.h = msp, x, y, h
        self.widths = [w * h for w in widths]
        self.layer = layer
        self.row_h = 2.0 * h

    @property
    def width(self) -> float:
        return sum(self.widths)

    def _line(self, a, b, colour=None):
        attrs = {"layer": self.layer}
        if colour is not None:
            attrs["color"] = colour
        self.msp.add_line(a, b, dxfattribs=attrs)

    def _text(self, s: str, x: float, y: float, height: float, colour=None,
              align=TextEntityAlignment.MIDDLE_LEFT):
        attrs = {"layer": self.layer, "height": height}
        if colour is not None:
            attrs["color"] = colour
        self.msp.add_text(s, dxfattribs=attrs).set_placement((x, y), align=align)

    def title(self, s: str, colour=None):
        top, bottom = self.y, self.y - self.row_h * 1.2
        self._box(top, bottom, colour)
        self._text(s, self.x + 0.6 * self.h, (top + bottom) / 2, self.h * 1.1, colour)
        self.y = bottom

    def row(self, cells: list[str], colour=None, numeric_from: int | None = None):
        top, bottom = self.y, self.y - self.row_h
        self._box(top, bottom, colour)
        cx = self.x
        for i, (cell, w) in enumerate(zip(cells, self.widths)):
            if i:
                self._line((cx, top), (cx, bottom), colour)
            max_chars = max(int(w / (0.62 * self.h)) - 1, 3)
            text = cell if len(cell) <= max_chars else cell[: max_chars - 1] + "…"
            if numeric_from is not None and i >= numeric_from:
                self._text(text, cx + w - 0.5 * self.h, (top + bottom) / 2, self.h * 0.8,
                           colour, TextEntityAlignment.MIDDLE_RIGHT)
            else:
                self._text(text, cx + 0.5 * self.h, (top + bottom) / 2, self.h * 0.8, colour)
            cx += w
        self.y = bottom

    def note(self, s: str, colour=None):
        self._text(s, self.x, self.y - 1.2 * self.h, self.h * 0.7, colour)
        self.y -= 2.0 * self.h

    def _box(self, top, bottom, colour):
        x0, x1 = self.x, self.x + self.width
        self._line((x0, top), (x1, top), colour)
        self._line((x0, bottom), (x1, bottom), colour)
        self._line((x0, top), (x0, bottom), colour)
        self._line((x1, top), (x1, bottom), colour)


def _centroid(pts: list[tuple[float, float]]) -> tuple[float, float]:
    """Area centroid; falls back to the vertex mean for a degenerate outline."""
    a = cx = cy = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        cross = x1 * y2 - x2 * y1
        a += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    if abs(a) < 1e-9:
        return (sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n)
    return (cx / (3 * a), cy / (3 * a))


@register("cad.takeoff_sheet", "cad", TakeoffSheetInput,
          "Write the device takeoff onto a copy of a DXF: coloured rings and item "
          "tags on every counted device, a schedule per system, and room areas")
def takeoff_sheet(data: TakeoffSheetInput, storage: Storage | None = None) -> ToolResult:
    started = time.perf_counter()
    res = ToolResult(tool="cad.takeoff_sheet", engine_version=ENGINE_VERSION)
    if storage is None:
        raise InvalidInput("cad.takeoff_sheet needs storage to fetch the document")

    smap: SymbolMap = (SymbolMap.load(data.symbol_map) if data.symbol_map is not None
                       else default_map())
    doc = open_dxf(storage.read(data.storage_key), data.storage_key)
    msp = doc.modelspace()

    ext = bbox.extents(msp, fast=True)
    if not ext.has_data:
        raise InvalidInput(f"{data.storage_key} has no model-space geometry to take off")

    h = data.text_height
    if h is None:
        h = round(max(ext.size.x, ext.size.y) / 150.0, 3) or 1.0
        res.assumptions.append(Assumption(
            key="text_height", value=h, unit="drawing units",
            basis="No text height was supplied; 1/150 of the drawing's larger extent "
                  "keeps the schedule legible whatever the drawing units are.",
            verify_from="the project's CAD text standard and plot scale"))

    insunits = int(doc.header.get("$INSUNITS", 0))
    unit_name, mpu = describe(insunits)

    for name, colour in ((TAKEOFF_LAYER, 2), (SCHEDULE_LAYER, 7), (ROOMS_LAYER, 8)):
        if name not in doc.layers:
            doc.layers.add(name, color=colour)

    # ---- count, exactly as cad.count_devices does --------------------------
    hits, unmapped = scan_inserts(msp, smap, data.layers)
    # Rooms are read now, before anything is drawn: the tags written below are
    # text too, and read afterwards they would be taken for room names.
    found_rooms: list[dict] = []
    if data.room_boundary_layers:
        found_rooms, _labels, room_warnings = find_rooms(
            msp, data.room_boundary_layers, data.room_label_layers, 0.0, mpu)
        res.warnings.extend(room_warnings)
    by_system: dict[str, Counter[tuple[str, str]]] = defaultdict(Counter)
    blocks: dict[tuple[str, str], set[str]] = defaultdict(set)
    for hit in hits:
        key = (hit.rule.device_type, hit.rule.unit)
        by_system[hit.rule.system][key] += 1
        blocks[(hit.rule.system, hit.rule.device_type)].add(hit.block)

    colours: dict[str, int] = {}
    spare = iter(SPARE_COLOURS * 4)
    for system in sorted(by_system):
        colours[system] = SYSTEM_COLOUR.get(system) or next(spare)

    codes: dict[tuple[str, str], str] = {}
    schedule: list[dict] = []
    for system in sorted(by_system):
        prefix = _prefix(system)
        for i, ((device_type, unit), qty) in enumerate(sorted(by_system[system].items()), 1):
            code = f"{prefix}{i}"
            codes[(system, device_type)] = code
            schedule.append({"item": code, "system": system, "device_type": device_type,
                             "description": _label(device_type),
                             "blocks": sorted(blocks[(system, device_type)]),
                             "quantity": qty, "unit": unit})

    # ---- rings and tags on the drawing --------------------------------------
    for hit in hits:
        colour = colours[hit.rule.system]
        msp.add_circle((hit.x, hit.y), 0.9 * h,
                       dxfattribs={"layer": TAKEOFF_LAYER, "color": colour})
        if data.tag_devices:
            msp.add_text(codes[(hit.rule.system, hit.rule.device_type)],
                         dxfattribs={"layer": TAKEOFF_LAYER, "color": colour,
                                     "height": 0.7 * h}
                         ).set_placement((hit.x + 1.1 * h, hit.y + 0.6 * h),
                                         align=TextEntityAlignment.BOTTOM_LEFT)
    # Unmapped inserts are marked too, so the gap is visible where it is.
    if unmapped:
        for e in msp.query("INSERT"):
            key = (str(e.dxf.name), str(getattr(e.dxf, "layer", "")))
            if key in unmapped:
                x, y = float(e.dxf.insert[0]), float(e.dxf.insert[1])
                msp.add_circle((x, y), 0.9 * h, dxfattribs={
                    "layer": TAKEOFF_LAYER, "color": UNMAPPED_COLOUR, "linetype": "DASHED"
                    if "DASHED" in doc.linetypes else "CONTINUOUS"})
                msp.add_text("?", dxfattribs={"layer": TAKEOFF_LAYER, "height": h,
                                              "color": UNMAPPED_COLOUR}
                             ).set_placement((x, y), align=TextEntityAlignment.MIDDLE_CENTER)

    # ---- rooms ---------------------------------------------------------------
    room_rows: list[dict] = []
    if data.room_boundary_layers:
        rooms = found_rooms
        for n, room in enumerate(rooms, 1):
            pts = room["boundary"]
            hatch = msp.add_hatch(color=8, dxfattribs={"layer": ROOMS_LAYER})
            hatch.paths.add_polyline_path(pts, is_closed=True)
            hatch.transparency = 0.75
            cx, cy = _centroid(pts)
            name = room["name"] or (" / ".join(room["candidate_labels"]) or f"Unnamed {n}")
            area = (f"{room['area_m2']:.2f} m²" if room["area_m2"] is not None
                    else "area: units unknown")
            msp.add_text(area, dxfattribs={"layer": ROOMS_LAYER, "height": 0.8 * h}
                         ).set_placement((cx, cy - 1.7 * h), align=TextEntityAlignment.MIDDLE_CENTER)
            room_rows.append({"name": name, "named": room["name"] is not None,
                              "area_m2": room["area_m2"], "layer": room["layer"]})
        if rooms and mpu is None:
            res.missing.append(MissingItem(
                field="drawing_units", record=f"document:{data.document_id}",
                note=f"$INSUNITS is {insunits} ({unit_name}); room areas cannot be given "
                     "in m². Set the units in the DXF and re-run."))
        if not rooms:
            res.warnings.append(
                f"No closed outlines on {data.room_boundary_layers}; no room areas written.")

    # ---- schedules -------------------------------------------------------------
    tx = data.table_x if data.table_x is not None else ext.extmax.x + 6 * h
    ty = data.table_y if data.table_y is not None else ext.extmax.y
    widths = [5, 20, 14, 6, 5]
    for system in sorted(by_system):
        t = _Table(msp, tx, ty, h, widths, SCHEDULE_LAYER)
        t.title(f"{system.replace('_', ' ').upper()} — DEVICE SCHEDULE", colours[system])
        t.row(["ITEM", "DESCRIPTION", "BLOCK", "QTY", "UNIT"], numeric_from=3)
        total = 0
        for row in (r for r in schedule if r["system"] == system):
            t.row([row["item"], row["description"], ", ".join(row["blocks"]),
                   str(row["quantity"]), row["unit"]], numeric_from=3)
            total += row["quantity"]
        t.row(["", "TOTAL", "", str(total), ""], numeric_from=3)
        ty = t.y - 3 * h

    if unmapped:
        t = _Table(msp, tx, ty, h, [25, 14, 6, 5], SCHEDULE_LAYER)
        t.title("NOT COUNTED — BLOCKS NOT IN SYMBOL MAP", UNMAPPED_COLOUR)
        t.row(["BLOCK", "LAYER", "QTY", ""], UNMAPPED_COLOUR, numeric_from=2)
        for (b, l), n in sorted(unmapped.items()):
            t.row([b, l, str(n), ""], UNMAPPED_COLOUR, numeric_from=2)
        ty = t.y - 3 * h

    if room_rows:
        t = _Table(msp, tx, ty, h, [30, 10, 10], SCHEDULE_LAYER)
        t.title("AREA SCHEDULE")
        t.row(["ROOM", "AREA m²", "NAMED"], numeric_from=1)
        for r in room_rows:
            t.row([r["name"], f"{r['area_m2']:.2f}" if r["area_m2"] is not None else "—",
                   "yes" if r["named"] else "NO"], numeric_from=1)
        total_area = sum(r["area_m2"] or 0 for r in room_rows)
        t.row(["TOTAL", f"{total_area:.2f}" if mpu is not None else "—", ""], numeric_from=1)
        ty = t.y - 3 * h

    foot = _Table(msp, tx, ty, h, widths, SCHEDULE_LAYER)
    foot.note(f"Source: {data.storage_key} · symbol map {smap.name}@{smap.version} · {ENGINE_VERSION}")
    foot.note("PROPOSAL — quantities read off block names; pending engineer review.")
    if unmapped:
        foot.note(f"INCOMPLETE — {sum(unmapped.values())} insert(s) of {len(unmapped)} "
                  "block type(s) not counted. See NOT COUNTED table.", UNMAPPED_COLOUR)

    out = io.StringIO()
    doc.write(out)
    payload = out.getvalue().encode("utf-8")
    key = data.output_key or f"craft/takeoff/{data.output_name}"
    storage.write(key, payload)

    res.files = [OutputFile(name=data.output_name, mime=DXF_MIME, storage_key=key,
                            byte_size=len(payload), sha256=sha256(payload))]
    res.outputs = {
        "schedule": schedule,
        "rooms": room_rows,
        "mapped_insert_count": len(hits),
        "unmapped_insert_count": sum(unmapped.values()),
        "unmapped_blocks": [{"block": b, "layer": l, "count": n}
                            for (b, l), n in sorted(unmapped.items())],
        "layers": [TAKEOFF_LAYER, SCHEDULE_LAYER, ROOMS_LAYER],
        "text_height": h,
        "units": {"insunits": insunits, "name": unit_name, "metres_per_unit": mpu},
        "symbol_map": {"name": smap.name, "version": smap.version,
                       "source_document": smap.source_document},
        "source_storage_key": data.storage_key,
    }
    res.provenance = [
        Provenance(value_ref=f"schedule:{r['item']}={r['quantity']}",
                   source=f"{data.storage_key} via symbol map {smap.name}@{smap.version}")
        for r in schedule
    ]
    if unmapped:
        res.missing.extend(
            MissingItem(field="symbol_mapping", record=f"block:{b} layer:{l}",
                        note=f"{n} insert(s) of '{b}' on '{l}' are marked '?' on the "
                             "drawing and listed as NOT COUNTED. Add a rule, or confirm "
                             "the block is not a device.")
            for (b, l), n in sorted(unmapped.items()))
    if res.missing:
        res.status = "missing_data"
    if not hits and not unmapped:
        res.warnings.append("No block inserts found; the schedule is empty.")

    res.duration_ms = int((time.perf_counter() - started) * 1000)
    return res
