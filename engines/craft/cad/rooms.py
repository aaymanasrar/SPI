"""CADCraft: recover rooms from closed polylines and their labels.

Area needs units. A unitless DXF gets polygon outlines and label matches but no
square metres: the number would be a guess dressed as a measurement.
"""
from __future__ import annotations

import time

from pydantic import BaseModel, Field

from ..core import (ENGINE_VERSION, InvalidInput, MissingItem, Storage,
                    ToolResult, register)
from .read_dxf import open_dxf
from .units import describe


def polygon_area(points: list[tuple[float, float]]) -> float:
    """Shoelace. Returns drawing units squared, sign discarded."""
    n = len(points)
    if n < 3:
        return 0.0
    total = 0.0
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def point_in_polygon(x: float, y: float, poly: list[tuple[float, float]]) -> bool:
    """Ray casting. Points exactly on an edge are not guaranteed either way."""
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            t = (y - y1) / (y2 - y1)
            if x < x1 + t * (x2 - x1):
                inside = not inside
    return inside


class RoomsInput(BaseModel):
    document_id: str
    storage_key: str
    boundary_layers: list[str] = Field(
        description="layers holding closed room outlines — required, because "
                    "guessing which layer is architectural is how a corridor "
                    "becomes a room")
    label_layers: list[str] | None = Field(
        None, description="layers holding room names; default: any text layer")
    min_area_units: float = Field(
        0.0, description="drop polygons smaller than this, in drawing units squared")


@register("cad.extract_rooms", "cad", RoomsInput,
          "Recover room outlines, labels and areas from closed polylines",
          modes=("preview",))
def extract_rooms(data: RoomsInput, storage: Storage | None = None) -> ToolResult:
    started = time.perf_counter()
    res = ToolResult(tool="cad.extract_rooms", engine_version=ENGINE_VERSION)
    if storage is None:
        raise InvalidInput("cad.extract_rooms needs storage to fetch the document")
    if not data.boundary_layers:
        raise InvalidInput(
            "boundary_layers is required. There is no reliable convention for "
            "which layer holds room outlines; it has to be stated.")

    doc = open_dxf(storage.read(data.storage_key), data.storage_key)
    msp = doc.modelspace()
    insunits = int(doc.header.get("$INSUNITS", 0))
    unit_name, mpu = describe(insunits)

    bl = {l.casefold() for l in data.boundary_layers}
    ll = {l.casefold() for l in data.label_layers} if data.label_layers else None

    labels: list[dict] = []
    for e in msp:
        if e.dxftype() not in ("TEXT", "MTEXT"):
            continue
        layer = str(getattr(e.dxf, "layer", ""))
        if ll is not None and layer.casefold() not in ll:
            continue
        text = e.plain_text() if e.dxftype() == "MTEXT" else str(e.dxf.text)
        if not text.strip():
            continue
        p = e.dxf.insert
        labels.append({"text": text.strip(), "x": float(p[0]), "y": float(p[1]),
                       "layer": layer})

    rooms: list[dict] = []
    unlabelled = 0
    for e in msp:
        if e.dxftype() != "LWPOLYLINE":
            continue
        layer = str(getattr(e.dxf, "layer", ""))
        if layer.casefold() not in bl:
            continue
        if not e.closed:
            # An open outline has no inside, so it has no area and cannot hold a
            # label. Reported, not silently closed for the author.
            res.warnings.append(
                f"An open polyline on layer '{layer}' was skipped: an unclosed "
                "outline has no enclosed area.")
            continue
        pts = [(round(float(p[0]), 3), round(float(p[1]), 3))
               for p in e.get_points("xy")]
        area_u = polygon_area(pts)
        if area_u <= data.min_area_units:
            continue
        inside = [l for l in labels if point_in_polygon(l["x"], l["y"], pts)]
        if not inside:
            unlabelled += 1
        rooms.append({
            "name": inside[0]["text"] if len(inside) == 1 else None,
            "candidate_labels": [l["text"] for l in inside],
            "boundary": pts,
            "layer": layer,
            "area_drawing_units": round(area_u, 3),
            "area_m2": round(area_u * mpu * mpu, 3) if mpu is not None else None,
        })

    res.outputs = {
        "units": {"insunits": insunits, "name": unit_name, "metres_per_unit": mpu},
        "room_count": len(rooms),
        "rooms": rooms,
        "label_count": len(labels),
        "unlabelled_rooms": unlabelled,
    }

    if rooms and mpu is None:
        res.status = "missing_data"
        res.missing = [MissingItem(
            field="drawing_units",
            record=f"document:{data.document_id}",
            note=f"$INSUNITS is {insunits} ({unit_name}), so a drawing unit has no "
                 "real-world length and areas cannot be given in m². Outlines and "
                 "labels are in the output. Set the units in the DXF, or state the "
                 "scale, and re-run.")]
    if unlabelled:
        res.warnings.append(
            f"{unlabelled} room(s) contain no text label and have name=null. "
            "They are not named by position or sequence.")
    ambiguous = sum(1 for r in rooms if len(r["candidate_labels"]) > 1)
    if ambiguous:
        res.warnings.append(
            f"{ambiguous} room(s) contain more than one text label; name is null "
            "and every candidate is listed for a person to choose.")

    res.duration_ms = int((time.perf_counter() - started) * 1000)
    return res
