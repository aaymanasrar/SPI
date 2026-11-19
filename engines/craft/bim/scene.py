"""BIMCraft: a 3D scene description of an IFC model, for the simulator.

The BIM counterpart of cad.scene_3d, and simpler for one reason: a model knows
how high things are. A device's height is read off its placement rather than
supplied as a mounting rule, and a room's height is its extrusion depth rather
than an assumed ceiling. What the model does not say is still not invented: a
room with no extruded footprint has no outline, and a device with no usable
placement has no position.
"""
from __future__ import annotations

import time
from collections import Counter

from pydantic import BaseModel, Field

from ..core import (ENGINE_VERSION, Finding, InvalidInput, Storage, ToolResult,
                    register)
from .count import CountInput, count_devices
from .geometry import footprint, polygon_area, world_frame
from .model import _text, open_ifc
from .spaces import _area

CONTEXT_CLASSES = {
    "IFCWALL": "wall", "IFCWALLSTANDARDCASE": "wall", "IFCCOLUMN": "column",
    "IFCSLAB": "slab", "IFCCOVERING": "covering", "IFCRAILING": "railing",
}


class SceneInput(BaseModel):
    document_id: str
    storage_key: str
    element_map: dict | None = Field(None, description="as for bim.count_devices")
    classes: list[str] | None = Field(None, description="as for bim.count_devices")
    storeys: list[str] | None = Field(None, description="restrict to these storey names")
    include_context: bool = Field(
        True, description="also return walls, columns and slabs as extruded "
                          "outlines, so the scene is legible")
    context_limit: int = Field(6000, ge=0, description="cap on context elements")


def _inside(x: float, y: float, poly: list) -> bool:
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i][0], poly[i][1]
        xj, yj = poly[j][0], poly[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-30) + xi:
            inside = not inside
        j = i
    return inside


@register("bim.scene_3d", "bim", SceneInput,
          "Build a 3D scene of an IFC model: storeys, room outlines and heights, "
          "and device positions read from the model",
          modes=("preview",))
def scene_3d(data: SceneInput, storage: Storage | None = None) -> ToolResult:
    started = time.perf_counter()
    res = ToolResult(tool="bim.scene_3d", engine_version=ENGINE_VERSION)
    if storage is None:
        raise InvalidInput("bim.scene_3d needs storage to fetch the document")

    model = open_ifc(storage.read(data.storage_key), data.storage_key)
    mpu = model.metres_per_unit
    if mpu is None:
        raise InvalidInput(
            "The model declares no usable length unit, so nothing in it can be "
            "placed in metres. Re-export with project units set.")
    wanted = {s.casefold() for s in data.storeys} if data.storeys else None
    m = lambda v: round(v * mpu, 4)  # noqa: E731

    def storey_name(eid: int) -> str | None:
        s = model.storey_of(eid)
        return (_text(s.arg(2)) or f"#{s.id}") if s else None

    def included(name: str | None) -> bool:
        return wanted is None or (name or "").casefold() in wanted

    # -- rooms -----------------------------------------------------------
    spaces: list[dict] = []
    no_outline: list[str] = []
    for sp in model.step.of_type("IFCSPACE"):
        st = storey_name(sp.id)
        if not included(st):
            continue
        number, name = _text(sp.arg(2)), _text(sp.arg(7))
        label = " ".join(x for x in (number, name) if x) or f"#{sp.id}"
        world = world_frame(model, sp)
        fp = footprint(model, sp, world) if world else None
        raw_area, area_source = _area(model, sp)
        area = (round(raw_area * model.sqm_per_unit, 3)
                if raw_area is not None and model.sqm_per_unit else None)
        entry = {
            "id": _text(sp.arg(0)) or f"#{sp.id}",
            "number": number, "name": name, "label": label, "storey": st,
            "footprint_m": [[m(x), m(y)] for x, y in fp["points"]] if fp else None,
            "base_z_m": m(fp["base"]) if fp else None,
            "height_m": m(fp["height"]) if fp else None,
            "area_m2": area,
            "area_source": area_source if area is not None else None,
            "outline_area_m2": round(polygon_area(fp["points"]) * mpu * mpu, 3) if fp else None,
        }
        if fp is None:
            no_outline.append(label)
        spaces.append(entry)

    # -- devices ---------------------------------------------------------
    count = count_devices(CountInput(document_id=data.document_id,
                                     storage_key=data.storage_key,
                                     element_map=data.element_map,
                                     classes=data.classes, storeys=data.storeys),
                          storage=None, model=model)
    devices: list[dict] = []
    unplaced: list[str] = []
    for obj in count.outputs["objects"]:
        ev = obj["extracted_value"]
        pos = obj["geometry"]["coordinates"] if obj["geometry"] else None
        label = ev["name"] or ev["type_name"] or obj["source_reference"]
        space, space_basis = ev["space"], "model" if ev["space"] else None
        if pos and space is None:
            # Revit places devices in the storey, not the room. Find the room
            # whose outline and height contain the device.
            for s in spaces:
                if (s["storey"] == ev["storey"] and s["footprint_m"]
                        and s["base_z_m"] - 0.05 <= pos[2] <= s["base_z_m"] + s["height_m"] + 0.05
                        and _inside(pos[0], pos[1], s["footprint_m"])):
                    space, space_basis = s["label"], "located"
                    break
        if pos is None:
            unplaced.append(label)
        devices.append({
            "id": ev["global_id"] or obj["source_reference"],
            "system": ev["system"], "device_type": obj["object_type"],
            "name": ev["name"], "type_name": ev["type_name"], "tag": ev["tag"],
            "ifc_class": ev["ifc_class"], "predefined_type": ev["predefined_type"],
            "storey": ev["storey"], "space": space, "space_basis": space_basis,
            "x_m": pos[0] if pos else None, "y_m": pos[1] if pos else None,
            "z_m": pos[2] if pos else None,
            "yaw_deg": ev["yaw_deg"], "position_basis": ev["position_basis"],
            "source_reference": obj["source_reference"],
        })

    # -- context ---------------------------------------------------------
    context: list[dict] = []
    context_skipped: Counter[str] = Counter()
    if data.include_context:
        for cls, kind in CONTEXT_CLASSES.items():
            for el in model.step.of_type(cls):
                st = storey_name(el.id)
                if not included(st):
                    continue
                if len(context) >= data.context_limit:
                    context_skipped["over context_limit"] += 1
                    continue
                world = world_frame(model, el)
                fp = footprint(model, el, world) if world else None
                if fp is None:
                    context_skipped[cls] += 1
                    continue
                context.append({"kind": kind, "storey": st,
                                "footprint_m": [[m(x), m(y)] for x, y in fp["points"]],
                                "base_z_m": m(fp["base"]), "height_m": m(fp["height"])})

    # -- the frame of the whole thing --------------------------------------
    xs, ys, zs = [], [], []
    for s in spaces:
        for x, y in s["footprint_m"] or []:
            xs.append(x), ys.append(y)
        if s["base_z_m"] is not None:
            zs += [s["base_z_m"], s["base_z_m"] + s["height_m"]]
    for c in context:
        for x, y in c["footprint_m"]:
            xs.append(x), ys.append(y)
        zs += [c["base_z_m"], c["base_z_m"] + c["height_m"]]
    for d in devices:
        if d["x_m"] is not None:
            xs.append(d["x_m"]), ys.append(d["y_m"]), zs.append(d["z_m"])

    project = model.project()
    storeys = [s for s in model.storeys() if included(s["name"])]
    systems = sorted({d["system"] for d in devices})
    res.outputs = {
        "model": {
            "schema": model.schema,
            "authoring_application": model.authoring_application,
            "is_revit_export": model.is_revit,
            "project": _text(project.arg(2)) if project else None,
            "project_long_name": _text(project.arg(5)) if project else None,
            "source": data.storage_key,
        },
        "units": {"length": model.length_unit, "metres_per_unit": mpu},
        "storeys": storeys,
        "spaces": spaces,
        "devices": devices,
        "context": context,
        "systems": systems,
        "counts": count.outputs["counts"],
        "counts_by_storey": count.outputs["counts_by_storey"],
        "unmapped_elements": count.outputs["unmapped_elements"],
        "element_map": count.outputs["element_map"],
        "context_without_outline": dict(sorted(context_skipped.items())),
        "bounds_m": ({"min": [min(xs), min(ys), min(zs) if zs else 0.0],
                      "max": [max(xs), max(ys), max(zs) if zs else 0.0]}
                     if xs else None),
    }
    res.provenance = list(count.provenance)
    res.status = count.status
    res.missing = list(count.missing)
    res.warnings = list(count.warnings)

    if no_outline:
        res.findings.append(Finding(
            code="SPACE-NO-OUTLINE", severity="review",
            subject=f"document:{data.document_id}",
            detail=f"{len(no_outline)} room(s) have no vertically extruded body, so "
                   "they have no plan outline and are left out of any coverage "
                   "check: " + ", ".join(no_outline[:20])
                   + (" …" if len(no_outline) > 20 else ""),
            action="In Revit, make sure the rooms are bounded and re-export with "
                   "'Export rooms' on; a room cut by a sloped ceiling exports as "
                   "a brep and has to be checked by hand."))
    if unplaced:
        res.findings.append(Finding(
            code="DEVICE-NO-POSITION", severity="review",
            subject=f"document:{data.document_id}",
            detail=f"{len(unplaced)} counted device(s) have no usable placement and "
                   "are not shown: " + ", ".join(unplaced[:20]),
            action="Check the elements in Revit; they are still in the counts."))
    baked = sum(1 for d in devices if d["position_basis"] == "geometry")
    if baked:
        res.findings.append(Finding(
            code="DEVICE-POSITION-FROM-GEOMETRY", severity="info",
            subject=f"document:{data.document_id}",
            detail=f"{baked} device(s) were exported with their placement at the "
                   "origin, so their position is the origin of their geometry "
                   "instead of the family insertion point.",
            action="Spot-check one of them against the Revit model."))
    if not storeys:
        res.warnings.append("No storeys in the model; the scene has a single level.")

    res.duration_ms = int((time.perf_counter() - started) * 1000)
    return res
