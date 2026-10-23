"""Check a drawing's dimensions against itself.

Two independent checks, both exact, neither heuristic.

**Overridden dimension text.** A DXF DIMENSION carries both a measured value,
derived from the geometry it attaches to, and the text that prints. When someone
types a number over a dimension the two diverge, the sheet reads correctly and
the model is wrong. This is the defect that survives every visual check, because
the drawing looks right.

**Chain arithmetic.** A chain of part dimensions must sum to the overall it sits
under. On the KG sheet the west chain reads 23.56 m and the east 21.40 m for the
same building: a conflict visible only by adding them up. Chains are supplied as
data because a raster drawing has no DIMENSION entities to read -- what is
checked is what the caller says the sheet says.

Neither check decides which number is right. That is an engineer's call, and the
finding says so.
"""
from __future__ import annotations

import time

from pydantic import BaseModel, Field

from ..core import (ENGINE_VERSION, Finding, InvalidInput, Storage, ToolResult,
                    register)
from .read_dxf import open_dxf
from .units import describe


class DimensionChain(BaseModel):
    """A run of part dimensions read off the sheet, and what it should total."""
    name: str = Field(description="e.g. 'west elevation chain'")
    axis: str = Field(description="'x' or 'y' -- which direction it runs")
    segments: list[float]
    expected_total: float | None = Field(
        None, description="the overall dimension printed over this chain, if any")


class CheckDimensionsInput(BaseModel):
    document_id: str
    storage_key: str | None = Field(
        None, description="a DXF to read DIMENSION entities from; omit to check "
                          "supplied chains only")
    chains: list[DimensionChain] = Field(default_factory=list)
    tolerance_m: float = Field(
        0.01, gt=0,
        description="how far a sum may drift before it is a conflict. Drawing "
                    "dimensions are rounded, so some drift is normal.")


@register("cad.check_dimensions", "cad", CheckDimensionsInput,
          "Check dimension text against measured geometry, and chains against "
          "their totals", modes=("preview",))
def check_dimensions(data: CheckDimensionsInput,
                     storage: Storage | None = None) -> ToolResult:
    started = time.perf_counter()
    res = ToolResult(tool="cad.check_dimensions", engine_version=ENGINE_VERSION)

    overrides: list[dict] = []
    dim_count = 0
    units = None

    if data.storage_key:
        if storage is None:
            raise InvalidInput("cad.check_dimensions needs storage to read a DXF")
        doc = open_dxf(storage.read(data.storage_key), data.storage_key)
        insunits = int(doc.header.get("$INSUNITS", 0))
        unit_name, mpu = describe(insunits)
        units = {"insunits": insunits, "name": unit_name, "metres_per_unit": mpu}
        for e in doc.modelspace():
            if e.dxftype() != "DIMENSION":
                continue
            dim_count += 1
            raw = str(getattr(e.dxf, "text", "") or "")
            # '' and '<>' both mean "print the measurement", which cannot lie.
            if raw.strip() in ("", "<>"):
                continue
            try:
                measured = float(e.get_measurement())
            except Exception:                      # noqa: BLE001
                continue
            stated = _number_in(raw)
            if stated is None:
                continue
            drift = abs(stated - measured) * (mpu or 1)
            if drift > data.tolerance_m:
                overrides.append({"text": raw.strip(), "stated": stated,
                                  "measured": round(measured, 4),
                                  "drift_m": round(drift, 4),
                                  "layer": str(getattr(e.dxf, "layer", ""))})

    for o in overrides:
        res.findings.append(Finding(
            code="DIM-TEXT-OVERRIDE", severity="blocker",
            subject=f"document:{data.document_id}",
            detail=f"A dimension prints '{o['text']}' but measures {o['measured']} "
                   f"against the geometry it attaches to, a difference of "
                   f"{o['drift_m']} m. The sheet reads correctly and the model does "
                   "not, so anything taken off the geometry will be wrong.",
            action="Have the drawing's author confirm which value is correct and "
                   "reissue. Do not take quantities off this drawing until then."))

    chain_results: list[dict] = []
    for ch in data.chains:
        total = round(sum(ch.segments), 6)
        row = {"name": ch.name, "axis": ch.axis, "segments": len(ch.segments),
               "sum": total, "expected_total": ch.expected_total,
               "agrees": None, "difference": None}
        if ch.expected_total is not None:
            diff = round(total - ch.expected_total, 6)
            row["difference"] = diff
            row["agrees"] = abs(diff) <= data.tolerance_m
            if not row["agrees"]:
                res.findings.append(Finding(
                    code="DIM-CHAIN-SUM", severity="blocker",
                    subject=f"chain:{ch.name}",
                    detail=f"The parts of '{ch.name}' sum to {total} m but the "
                           f"overall printed over them is {ch.expected_total} m, "
                           f"a difference of {diff:+} m.",
                    action="Confirm against the original drawing which dimension "
                           "governs, and reissue the sheet or correct the chain."))
        chain_results.append(row)

    # Two chains on the same axis must describe the same building.
    by_axis: dict[str, list[dict]] = {}
    for row in chain_results:
        by_axis.setdefault(row["axis"], []).append(row)
    for axis, rows in sorted(by_axis.items()):
        if len(rows) < 2:
            continue
        lo = min(rows, key=lambda r: r["sum"])
        hi = max(rows, key=lambda r: r["sum"])
        diff = round(hi["sum"] - lo["sum"], 6)
        if diff > data.tolerance_m:
            res.findings.append(Finding(
                code="DIM-CHAIN-CONFLICT", severity="blocker",
                subject=f"axis:{axis}",
                detail=f"Two chains measure the same {axis} extent and disagree: "
                       f"'{hi['name']}' totals {hi['sum']} m, '{lo['name']}' totals "
                       f"{lo['sum']} m, a difference of {diff} m. One of them is "
                       "wrong, and this tool cannot tell which.",
                action="Resolve against the original DXF or the architect's model. "
                       "Until then any area, route or quantity taken along this "
                       "axis inherits the error."))

    res.outputs = {
        "units": units,
        "dimension_entities": dim_count,
        "overridden_text": overrides,
        "chains": chain_results,
        "conflicts": sum(1 for f in res.findings if f.severity == "blocker"),
    }
    if any(f.severity == "blocker" for f in res.findings):
        # The envelope refuses status='ok' alongside a blocker, which is the
        # point: a drawing that contradicts itself must not read as checked.
        res.status = "invalid_input"
    res.duration_ms = int((time.perf_counter() - started) * 1000)
    return res


def _number_in(text: str) -> float | None:
    import re
    m = re.search(r"-?\d+(?:[.,]\d+)?", text.replace(",", "."))
    return float(m.group(0)) if m else None
