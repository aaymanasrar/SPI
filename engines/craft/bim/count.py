"""BIMCraft: count devices in an IFC model.

The same contract as cad.count_devices, for the same reason. Rows are shaped for
`drawing_objects` with source='imported' and review_status='pending': a count is
a proposal; an engineer promotes it.

An unmapped element is the important case. A device class in scope that no rule
recognises makes the whole count `missing_data`, with the partial tallies still
returned — a count that silently skips every proxy would look authoritative and
be short.
"""
from __future__ import annotations

import time
from collections import Counter

from pydantic import BaseModel, Field

from ..core import (ENGINE_VERSION, InvalidInput, MissingItem, Provenance,
                    Storage, ToolResult, register)
from .element_map import ElementMap, default_map
from .model import SPATIAL_CLASSES, IfcModel, _text, open_ifc

# Classes that can be an ELV device. Anything else in the model (walls, ducts,
# luminaires) is tallied under out_of_scope_classes and is not a gap.
DEVICE_CLASSES = (
    "IfcSensor", "IfcAlarm", "IfcActuator", "IfcController",
    "IfcUnitaryControlElement", "IfcAudioVisualAppliance",
    "IfcCommunicationsAppliance", "IfcOutlet", "IfcBuildingElementProxy",
    # Generic IFC2x3 occurrences with no type object to say what they are.
    "IfcDistributionControlElement", "IfcFlowTerminal",
)


class CountInput(BaseModel):
    document_id: str
    storage_key: str
    element_map: dict | None = Field(
        None,
        description="an ElementMap as data — see bim/element_map.py. Omitted means "
                    "the default map, which knows IFC's standard predefined types "
                    "only and interprets no family name.")
    classes: list[str] | None = Field(
        None, description="IFC classes treated as devices; omitted means the ELV "
                          "default set (sensors, alarms, controllers, AV and "
                          "communications appliances, outlets, proxies)")
    storeys: list[str] | None = Field(None, description="restrict to these storey names")


@register("bim.count_devices", "bim", CountInput,
          "Count IFC elements per device type and storey using an element map")
def count_devices(data: CountInput, storage: Storage | None = None,
                  model: IfcModel | None = None) -> ToolResult:
    """`model` lets bim.scene_3d reuse a parse; the HTTP surface never passes it."""
    started = time.perf_counter()
    res = ToolResult(tool="bim.count_devices", engine_version=ENGINE_VERSION)
    if model is None:
        if storage is None:
            raise InvalidInput("bim.count_devices needs storage to fetch the document")
        model = open_ifc(storage.read(data.storage_key), data.storage_key)

    emap = (ElementMap.load(data.element_map) if data.element_map is not None
            else default_map())
    step = model.step

    scope = {c.upper() for c in (data.classes or DEVICE_CLASSES)}
    wanted = {s.casefold() for s in data.storeys} if data.storeys else None

    # Placed elements, plus any in-scope instance the model forgot to place.
    ids = {i for i in list(model.container) + list(model.parent)
           if step.type_of(i) and step.type_of(i) not in SPATIAL_CLASSES}
    for cls in scope:
        ids.update(e.id for e in step.of_type(cls))

    tallies: Counter[tuple[str, str, str]] = Counter()      # system, device_type, unit
    by_storey: Counter[tuple[str, str, str]] = Counter()    # storey, system, device_type
    unmapped: Counter[tuple[str, str, str]] = Counter()     # class, predefined, label
    ignored: Counter[tuple[str, str, str]] = Counter()
    out_of_scope: Counter[str] = Counter()
    objects: list[dict] = []
    unplaced = 0

    for eid in sorted(ids):
        el = step.get(eid)
        d = model.describe(el)
        if d["ifc_class"] not in scope:
            out_of_scope[d["ifc_class"]] += 1
            continue

        storey = model.storey_of(eid)
        storey_name = (_text(storey.arg(2)) or f"#{storey.id}") if storey else None
        if wanted is not None and (storey_name or "").casefold() not in wanted:
            continue

        label = d["type_name"] or d["object_type"] or d["name"] or ""
        key = (d["ifc_class"], d["predefined_type"] or "", label)
        rule = emap.resolve(d)
        if rule is None:
            unmapped[key] += 1
            continue
        if rule.ignore:
            ignored[key] += 1
            continue

        if storey is None:
            unplaced += 1
        space = model.space_of(eid)
        tallies[(rule.system, rule.device_type, rule.unit)] += 1
        by_storey[(storey_name or "(no storey)", rule.system, rule.device_type)] += 1
        where = model.locate(el)
        position = where["position_m"]
        objects.append({
            "drawing_page_id": None,
            "object_type": rule.device_type,
            "geometry": {"type": "Point", "coordinates": position} if position else None,
            "extracted_value": {
                "system": rule.system, "unit": rule.unit,
                "ifc_class": d["ifc_class"], "predefined_type": d["predefined_type"],
                "name": d["name"], "type_name": d["type_name"], "tag": d["tag"],
                "global_id": d["global_id"],
                "storey": storey_name,
                "space": (_text(space.arg(2)) if space else None),
                "yaw_deg": where["yaw_deg"],
                "position_basis": where["basis"],
            },
            "source": "imported",
            # Read off an IFC class or an exact mapping rule — not inferred, so a
            # confidence score would be theatre. Left null deliberately.
            "confidence": None,
            "source_reference": f"{data.storage_key}#{d['global_id'] or eid}",
            "review_status": "pending",
        })

    res.outputs = {
        "counts": [{"system": s, "device_type": t, "unit": u, "quantity": n}
                   for (s, t, u), n in sorted(tallies.items())],
        "counts_by_storey": [{"storey": st, "system": s, "device_type": t, "quantity": n}
                             for (st, s, t), n in sorted(by_storey.items())],
        "objects": objects,
        "mapped_element_count": sum(tallies.values()),
        "unmapped_element_count": sum(unmapped.values()),
        "unmapped_elements": [{"ifc_class": c, "predefined_type": p or None,
                               "type_name": n or None, "count": k}
                              for (c, p, n), k in sorted(unmapped.items())],
        "ignored_elements": [{"ifc_class": c, "predefined_type": p or None,
                              "type_name": n or None, "count": k}
                             for (c, p, n), k in sorted(ignored.items())],
        "out_of_scope_classes": dict(sorted(out_of_scope.items())),
        "element_map": {"name": emap.name, "version": emap.version,
                        "source_document": emap.source_document},
        "model": {"schema": model.schema, "originating_system": model.originating_system},
    }
    res.provenance = [
        Provenance(value_ref=f"count:{s}.{t}={n}",
                   source=f"{data.storage_key} via element map "
                          f"{emap.name}@{emap.version} ({emap.source_document})")
        for (s, t, _u), n in sorted(tallies.items())
    ]

    if unmapped:
        res.status = "missing_data"
        res.missing = [MissingItem(
            field="element_mapping",
            record=f"{c}{'.' + p if p else ''} '{n}'",
            note=f"{k} element(s) are not in element map {emap.name}@{emap.version}. "
                 "Add a rule naming the family, or an ignore rule if it is not a "
                 "device. Counting without it would under-report.")
            for (c, p, n), k in sorted(unmapped.items())]
    if unplaced:
        res.warnings.append(
            f"{unplaced} counted element(s) belong to no storey. They are in the "
            "total and listed under '(no storey)'.")
    if objects and model.metres_per_unit is None:
        res.warnings.append(
            "The model declares no usable length unit, so element positions are "
            "withheld. Counts are unaffected.")
    if not tallies and not unmapped:
        res.warnings.append(
            "No device elements matched. Either the model has none of the classes "
            "in scope, or the storey filter excluded them all.")

    res.duration_ms = int((time.perf_counter() - started) * 1000)
    return res
