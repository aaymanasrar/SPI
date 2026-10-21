"""CADCraft: count devices on a drawing.

Produces rows shaped for `drawing_objects` with source='imported' and
review_status='pending' (migration 0004). A count is a proposal; an engineer
promotes it.

An unmapped block is the important case. Counting only the blocks the mapping
knows yields a number that looks authoritative and is quietly short, which is
worse than no number: it flows into a BOQ and nobody sees the gap. So an
unmapped insert makes the whole count `missing_data`, and the partial tallies
are still returned so it is clear what completing the mapping would give.
"""
from __future__ import annotations

import time
from collections import Counter

from pydantic import BaseModel, Field

from ..core import (ENGINE_VERSION, InvalidInput, MissingItem, Provenance,
                    Storage, ToolResult, register)
from .read_dxf import open_dxf
from .symbols import SymbolMap, default_map

# Blocks that are drawing furniture, not devices. Named explicitly rather than
# pattern-guessed, and still reported so nothing vanishes silently.
IGNORED_PREFIXES = ("*",)


class CountInput(BaseModel):
    document_id: str
    storage_key: str
    symbol_map: dict | None = Field(
        None,
        description="a SymbolMap as data — see cad/symbols.py. Omitted means the "
                    "generic default map, which matches descriptive block names "
                    "only and is not a client drawing standard.")
    drawing_page_id: str | None = Field(
        None, description="the drawing_pages row these objects belong to")
    layers: list[str] | None = Field(None, description="restrict to these layers")


@register("cad.count_devices", "cad", CountInput,
          "Count block inserts per device type using a supplied symbol map")
def count_devices(data: CountInput, storage: Storage | None = None) -> ToolResult:
    started = time.perf_counter()
    res = ToolResult(tool="cad.count_devices", engine_version=ENGINE_VERSION)
    if storage is None:
        raise InvalidInput("cad.count_devices needs storage to fetch the document")

    smap = (SymbolMap.load(data.symbol_map) if data.symbol_map is not None
            else default_map())
    doc = open_dxf(storage.read(data.storage_key), data.storage_key)
    msp = doc.modelspace()

    tallies: Counter[tuple[str, str, str]] = Counter()   # system, device_type, unit
    objects: list[dict] = []
    unmapped: Counter[tuple[str, str]] = Counter()
    wanted = {l.casefold() for l in data.layers} if data.layers else None

    for e in msp:
        if e.dxftype() != "INSERT":
            continue
        block = str(e.dxf.name)
        layer = str(getattr(e.dxf, "layer", ""))
        if block.startswith(IGNORED_PREFIXES):
            continue
        if wanted is not None and layer.casefold() not in wanted:
            continue

        rule = smap.resolve(block, layer)
        if rule is None:
            unmapped[(block, layer)] += 1
            continue

        tallies[(rule.system, rule.device_type, rule.unit)] += 1
        objects.append({
            "drawing_page_id": data.drawing_page_id,
            "object_type": rule.device_type,
            "geometry": {"type": "Point",
                         "coordinates": [round(float(e.dxf.insert[0]), 3),
                                         round(float(e.dxf.insert[1]), 3)]},
            "extracted_value": {"system": rule.system, "block": block,
                                "layer": layer, "unit": rule.unit},
            "source": "imported",
            # Read off a block name by an exact mapping rule — not inferred, so
            # a confidence score would be theatre. Left null deliberately.
            "confidence": None,
            "source_reference": f"{data.storage_key}#{block}@{layer}",
            "review_status": "pending",
        })

    res.outputs = {
        "counts": [{"system": s, "device_type": d, "unit": u, "quantity": n}
                   for (s, d, u), n in sorted(tallies.items())],
        "objects": objects,
        "mapped_insert_count": sum(tallies.values()),
        "unmapped_insert_count": sum(unmapped.values()),
        "unmapped_blocks": [{"block": b, "layer": l, "count": n}
                            for (b, l), n in sorted(unmapped.items())],
        "symbol_map": {"name": smap.name, "version": smap.version,
                       "source_document": smap.source_document},
    }
    res.provenance = [
        Provenance(value_ref=f"count:{s}.{d}={n}",
                   source=f"{data.storage_key} via symbol map "
                          f"{smap.name}@{smap.version} ({smap.source_document})")
        for (s, d, _u), n in sorted(tallies.items())
    ]

    if unmapped:
        res.status = "missing_data"
        res.missing = []
        for (b, l), n in sorted(unmapped.items()):
            note = (f"{n} insert(s) of '{b}' on layer '{l}' are not in symbol map "
                    f"{smap.name}@{smap.version}. Add a rule, or confirm the block "
                    "is not a device. Counting without it would under-report.")
            why = smap.ambiguity_note(b)
            if why:
                # Not an oversight: this map refuses to interpret the code.
                note += (f" This map deliberately does not interpret '{b}': {why} "
                         "Resolve it against the drawing's legend sheet.")
            res.missing.append(MissingItem(
                field="symbol_mapping", record=f"block:{b} layer:{l}", note=note))
    if not tallies and not unmapped:
        res.warnings.append(
            "No block inserts matched. Either the drawing has none, or the layer "
            "filter excluded them all.")

    res.duration_ms = int((time.perf_counter() - started) * 1000)
    return res
