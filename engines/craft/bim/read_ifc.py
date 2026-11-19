"""BIMCraft: inventory an IFC model exported from Revit (or any BIM tool).

Reports what is actually in the file — schema, authoring tool, units, storeys,
element classes and the type objects behind them — so an engineer can see what
a count would be based on before anyone counts anything.
"""
from __future__ import annotations

import time
from collections import Counter

from pydantic import BaseModel

from ..core import ENGINE_VERSION, InvalidInput, Storage, ToolResult, register
from .model import SPATIAL_CLASSES, _text, open_ifc


class ReadIfcInput(BaseModel):
    document_id: str
    storage_key: str


@register("bim.read_ifc", "bim", ReadIfcInput,
          "Inventory an IFC model: schema, authoring tool, units, storeys, "
          "element classes and element types",
          modes=("preview",))
def read_ifc(data: ReadIfcInput, storage: Storage | None = None) -> ToolResult:
    started = time.perf_counter()
    res = ToolResult(tool="bim.read_ifc", engine_version=ENGINE_VERSION)
    if storage is None:
        raise InvalidInput("bim.read_ifc needs storage to fetch the document")

    model = open_ifc(storage.read(data.storage_key), data.storage_key)
    step = model.step

    # Elements are whatever the model places in a storey or space, or nests
    # under such an element — not every instance in the file, which is mostly
    # geometry.
    element_ids = {i for i in list(model.container) + list(model.parent)
                   if step.type_of(i) not in SPATIAL_CLASSES and step.type_of(i)}
    classes: Counter[str] = Counter()
    types: Counter[tuple[str, str, str]] = Counter()
    for eid in element_ids:
        d = model.describe(step.get(eid))
        classes[d["ifc_class"]] += 1
        types[(d["ifc_class"], d["predefined_type"] or "",
               d["type_name"] or d["object_type"] or "")] += 1

    project = model.project()
    storeys = model.storeys()
    res.outputs = {
        "schema": model.schema,
        "originating_system": model.originating_system,
        "preprocessor": model.preprocessor,
        "exported_at": model.timestamp,
        "authoring_application": model.authoring_application,
        "is_revit_export": model.is_revit,
        "project": {"global_id": _text(project.arg(0)), "name": _text(project.arg(2)),
                    "long_name": _text(project.arg(5))} if project else None,
        "units": {
            "length": {"name": model.length_unit, "metres_per_unit": model.metres_per_unit},
            "area": {"name": model.area_unit, "square_metres_per_unit": model.sqm_per_unit},
        },
        "instance_count": len(step),
        "storeys": storeys,
        "space_count": step.types().get("IFCSPACE", 0),
        "element_count": len(element_ids),
        "element_classes": dict(sorted(classes.items())),
        "element_types": [{"ifc_class": c, "predefined_type": p or None,
                           "type_name": n or None, "count": k}
                          for (c, p, n), k in sorted(types.items())],
    }

    if model.metres_per_unit is None:
        res.warnings.append(
            "The model declares no usable length unit. Counting is unaffected; "
            "positions and elevations are withheld rather than assumed to be "
            "millimetres.")
    if not storeys:
        res.warnings.append(
            "No IfcBuildingStorey in the model, so nothing can be reported per "
            "level.")
    if not element_ids:
        res.warnings.append(
            "No element is contained in a storey or space. The export may hold "
            "geometry only, or use a model view that drops spatial containment.")
    proxies = classes.get("IFCBUILDINGELEMENTPROXY", 0)
    if proxies:
        res.warnings.append(
            f"{proxies} element(s) are IfcBuildingElementProxy — exported without "
            "an IFC class. They can only be counted by a family-name rule in the "
            "element map. Setting the IFC export class on the Revit families "
            "removes the need.")

    res.duration_ms = int((time.perf_counter() - started) * 1000)
    return res
