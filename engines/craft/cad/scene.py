"""CADCraft: turn a 2D drawing into a 3D scene description.

The point is to let someone walk a floor before it is built and see where the
ELV devices actually land -- the same idea as a kitchen walkthrough, applied to
fire alarm, CCTV, access control and data.

Two things a DXF does not contain, and which this module therefore refuses to
invent:

* **Ceiling height.** A floor plan is a horizontal section; the slab-to-ceiling
  dimension is on the sections and the RCP, not here. It is a required input.
* **Mounting heights.** How high a call point or a reader sits is an engineering
  requirement from a code, not a drawing measurement. They are passed in with
  their citation, exactly as `cad.count_devices` takes its symbol map as data.
  Nothing in this package holds a height, for the same reason
  `cad.place_devices` holds no spacing: an engineering value with no source is
  worse than a gap, because it looks like an answer.

A device whose type has no supplied mounting height is still returned, with
`z_m: null` and a note, and the whole result is `missing_data`.
"""
from __future__ import annotations

import time

from pydantic import BaseModel, Field

from ..core import (ENGINE_VERSION, InvalidInput, MissingItem, Provenance,
                    Storage, ToolResult, register)
from .count import CountInput, count_devices
from .read_dxf import open_dxf
from .rooms import RoomsInput, extract_rooms, polygon_area
from .units import describe


class MountingHeight(BaseModel):
    """Where a device type sits vertically, and who says so."""
    height_m: float | None = Field(
        None, description="metres above finished floor; null means ceiling-mounted")
    at_ceiling: bool = False
    source: str = Field(
        description="the rule or standard this came from, e.g. "
                    "'SPT-FA-12 (NFPA 72 17.15.9)'. Required: a height with no "
                    "citation cannot be defended on site.")
    tolerance_m: tuple[float, float] | None = Field(
        None, description="the permitted band, when the code gives one")


class Scene3dInput(BaseModel):
    document_id: str
    storage_key: str
    boundary_layers: list[str]
    label_layers: list[str] | None = None
    ceiling_height_m: float = Field(
        description="slab-to-ceiling in metres. NOT on the floor plan -- take it "
                    "from the sections or the reflected ceiling plan.")
    mounting_heights: dict[str, MountingHeight] = Field(
        default_factory=dict,
        description="device_type -> where it sits, with the rule that says so")
    symbol_map: dict | None = None
    layers: list[str] | None = None


@register("cad.scene_3d", "cad", Scene3dInput,
          "Build a 3D scene description: rooms, device placement and provenance",
          modes=("preview",))
def scene_3d(data: Scene3dInput, storage: Storage | None = None) -> ToolResult:
    started = time.perf_counter()
    res = ToolResult(tool="cad.scene_3d", engine_version=ENGINE_VERSION)
    if storage is None:
        raise InvalidInput("cad.scene_3d needs storage to fetch the document")
    if data.ceiling_height_m <= 0:
        raise InvalidInput(
            "ceiling_height_m must be positive. It is not on the floor plan; "
            "read it off the sections or the reflected ceiling plan.")

    doc = open_dxf(storage.read(data.storage_key), data.storage_key)
    insunits = int(doc.header.get("$INSUNITS", 0))
    unit_name, mpu = describe(insunits)
    if mpu is None:
        res.status = "missing_data"
        res.missing = [MissingItem(
            field="drawing_units", record=f"document:{data.document_id}",
            note=f"$INSUNITS is {insunits} ({unit_name}). Without a real-world "
                 "length for a drawing unit the model cannot be built to scale.")]
        res.duration_ms = int((time.perf_counter() - started) * 1000)
        return res

    rooms_res = extract_rooms(RoomsInput(
        document_id=data.document_id, storage_key=data.storage_key,
        boundary_layers=data.boundary_layers, label_layers=data.label_layers), storage)
    count_res = count_devices(CountInput(
        document_id=data.document_id, storage_key=data.storage_key,
        symbol_map=data.symbol_map, layers=data.layers), storage)

    rooms = [{
        "name": r["name"],
        "boundary_m": [[round(x * mpu, 3), round(y * mpu, 3)] for x, y in r["boundary"]],
        "area_m2": r["area_m2"],
        "height_m": data.ceiling_height_m,
    } for r in rooms_res.outputs.get("rooms", [])]

    def room_of(x: float, y: float) -> str | None:
        from .rooms import point_in_polygon
        for r in rooms:
            if point_in_polygon(x, y, [(p[0], p[1]) for p in r["boundary_m"]]):
                return r["name"]
        return None

    devices: list[dict] = []
    unresolved: dict[str, int] = {}
    for obj in count_res.outputs.get("objects", []):
        dt = obj["object_type"]
        x, y = obj["geometry"]["coordinates"]
        xm, ym = round(x * mpu, 3), round(y * mpu, 3)
        mh = data.mounting_heights.get(dt)
        if mh is None:
            z, src, band = None, None, None
            unresolved[dt] = unresolved.get(dt, 0) + 1
        elif mh.at_ceiling:
            z, src, band = data.ceiling_height_m, mh.source, None
        else:
            z, src, band = mh.height_m, mh.source, mh.tolerance_m
        devices.append({
            "device_type": dt,
            "system": obj["extracted_value"]["system"],
            "x_m": xm, "y_m": ym, "z_m": z,
            "height_source": src,
            "height_band_m": list(band) if band else None,
            "room": room_of(xm, ym),
            "block": obj["extracted_value"]["block"],
            "layer": obj["extracted_value"]["layer"],
            "source_reference": obj["source_reference"],
        })

    systems = sorted({d["system"] for d in devices})
    res.outputs = {
        "units": {"insunits": insunits, "name": unit_name, "metres_per_unit": mpu},
        "ceiling_height_m": data.ceiling_height_m,
        "rooms": rooms,
        "devices": devices,
        "systems": systems,
        "room_count": len(rooms),
        "device_count": len(devices),
        "floor_area_m2": round(sum(r["area_m2"] or 0 for r in rooms), 2),
        "devices_without_mounting_height": unresolved,
        "counts_by_system": {s: sum(1 for d in devices if d["system"] == s)
                             for s in systems},
    }
    res.provenance = [
        Provenance(value_ref=f"mounting_height:{dt}",
                   source=mh.source)
        for dt, mh in sorted(data.mounting_heights.items())
    ] + [Provenance(value_ref="ceiling_height_m",
                    source=f"supplied by caller: {data.ceiling_height_m} m")]

    # Pass through what the underlying tools could not resolve.
    res.missing = list(rooms_res.missing) + list(count_res.missing)
    res.warnings = list(rooms_res.warnings) + list(count_res.warnings)
    for dt, n in sorted(unresolved.items()):
        res.missing.append(MissingItem(
            field="mounting_height", record=f"device_type:{dt}",
            note=f"{n} {dt}(s) placed in plan but with no mounting height supplied, "
                 "so they have no vertical position. Supply one with the rule it "
                 "comes from (e.g. SPT-FA-12, NFPA 72 17.15.9). This package holds "
                 "no heights of its own."))
    if res.missing:
        res.status = "missing_data"

    res.duration_ms = int((time.perf_counter() - started) * 1000)
    return res
