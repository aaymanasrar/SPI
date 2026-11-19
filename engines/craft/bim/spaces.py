"""BIMCraft: the rooms of an IFC model.

IfcSpace is what a Revit Room becomes on export. The number, name and storey are
attributes; the floor area is a quantity the exporter may or may not have
written. Where it did not, the area is reported as missing — it is never
computed from geometry here, and never assumed.
"""
from __future__ import annotations

import time

from pydantic import BaseModel

from ..core import (ENGINE_VERSION, InvalidInput, MissingItem, Storage,
                    ToolResult, register)
from .model import IfcModel, _number, _refs, _text, open_ifc
from .step import Entity, Typed

# Quantity names in order of preference. Net is the usable floor.
AREA_QUANTITIES = ("NetFloorArea", "GrossFloorArea")


class SpacesInput(BaseModel):
    document_id: str
    storage_key: str
    storeys: list[str] | None = None


def _area(model: IfcModel, space: Entity) -> tuple[float | None, str | None]:
    """(area in the file's unit, where it was read from)."""
    step = model.step
    found: dict[str, float] = {}
    fallback: tuple[float, str] | None = None
    for ref in model.definitions.get(space.id, []):
        definition = step.get(ref)
        if definition is None:
            continue
        set_name = _text(definition.arg(2)) or definition.type
        if definition.type == "IFCELEMENTQUANTITY":
            for q in (step.get(r) for r in _refs(definition.arg(5))):
                if q is not None and q.type == "IFCQUANTITYAREA":
                    value = _number(q.arg(3))
                    name = _text(q.arg(0)) or ""
                    if value is not None:
                        found.setdefault(name, value)
                        found.setdefault(f"@{name}", set_name)   # remember the set
        elif definition.type == "IFCPROPERTYSET" and fallback is None:
            # Revit writes the room's Area parameter as a property when base
            # quantities are switched off in the export setup.
            for p in (step.get(r) for r in _refs(definition.arg(4))):
                if (p is not None and p.type == "IFCPROPERTYSINGLEVALUE"
                        and (_text(p.arg(0)) or "").casefold() == "area"
                        and isinstance(p.arg(2), Typed)
                        and p.arg(2).type == "IFCAREAMEASURE"):
                    value = _number(p.arg(2))
                    if value is not None:
                        fallback = (value, f"property {set_name}.Area")
    for name in AREA_QUANTITIES:
        if name in found:
            return found[name], f"quantity {found['@' + name]}.{name}"
    return fallback if fallback else (None, None)


@register("bim.extract_spaces", "bim", SpacesInput,
          "List the rooms (IfcSpace) of an IFC model with storey and floor area",
          modes=("preview",))
def extract_spaces(data: SpacesInput, storage: Storage | None = None) -> ToolResult:
    started = time.perf_counter()
    res = ToolResult(tool="bim.extract_spaces", engine_version=ENGINE_VERSION)
    if storage is None:
        raise InvalidInput("bim.extract_spaces needs storage to fetch the document")

    model = open_ifc(storage.read(data.storage_key), data.storage_key)
    wanted = {s.casefold() for s in data.storeys} if data.storeys else None

    spaces: list[dict] = []
    without_area: list[str] = []
    for space in model.step.of_type("IFCSPACE"):
        storey = model.storey_of(space.id)
        storey_name = (_text(storey.arg(2)) or f"#{storey.id}") if storey else None
        if wanted is not None and (storey_name or "").casefold() not in wanted:
            continue
        number, name = _text(space.arg(2)), _text(space.arg(7))
        raw_area, source = _area(model, space)
        area_m2 = (round(raw_area * model.sqm_per_unit, 3)
                   if raw_area is not None and model.sqm_per_unit else None)
        label = " ".join(x for x in (number, name) if x) or f"#{space.id}"
        if area_m2 is None:
            without_area.append(label)
        spaces.append({
            "global_id": _text(space.arg(0)),
            "number": number,
            "name": name,
            "storey": storey_name,
            "area_m2": area_m2,
            "area_source": source if area_m2 is not None else None,
            "source_reference": f"{data.storage_key}#{_text(space.arg(0)) or space.id}",
        })
    spaces.sort(key=lambda s: (s["storey"] or "", s["number"] or "", s["name"] or ""))

    totals: dict[str, dict] = {}
    for s in spaces:
        t = totals.setdefault(s["storey"] or "(no storey)",
                              {"space_count": 0, "area_m2": 0.0, "spaces_without_area": 0})
        t["space_count"] += 1
        if s["area_m2"] is None:
            t["spaces_without_area"] += 1
        else:
            t["area_m2"] = round(t["area_m2"] + s["area_m2"], 3)

    res.outputs = {
        "units": {"area": {"name": model.area_unit,
                           "square_metres_per_unit": model.sqm_per_unit}},
        "space_count": len(spaces),
        "spaces": spaces,
        "by_storey": [{"storey": k, **v} for k, v in sorted(totals.items())],
    }

    if without_area:
        res.status = "missing_data"
        if model.sqm_per_unit is None:
            note = ("The model declares no usable area unit, so no area can be "
                    "given in m².")
        else:
            note = ("No floor-area quantity was exported for this space. In Revit's "
                    "IFC export setup, enable 'Export base quantities' and export "
                    "again. The area is not derived from geometry.")
        res.missing = [MissingItem(field="floor_area", record=f"space:{label}", note=note)
                       for label in without_area]
    if not spaces:
        res.warnings.append(
            "No IfcSpace in the model. Rooms must be placed in Revit and 'Export "
            "rooms' enabled in the IFC export setup for spaces to be written.")

    res.duration_ms = int((time.perf_counter() - started) * 1000)
    return res
