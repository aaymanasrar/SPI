"""GridCraft: a client's BOQ workbook -> normalised rows, as PROPOSALS.

Nothing read here is authoritative. A client spreadsheet has whatever columns the
client felt like using; this maps them to our shape, records how confident the
mapping was, and hands back rows for an engineer to confirm.
"""
from __future__ import annotations

import io
import time

from openpyxl import load_workbook
from pydantic import BaseModel, Field

from ..core import (ENGINE_VERSION, InvalidInput, Storage, ToolResult, register)

#: Header synonyms seen in client BOQs. Data, not cleverness -- extend the lists
#: rather than adding fuzzy matching, so a mapping is always explainable.
#: Each list is in priority order: when two columns match one field (a sheet
#: with both "Item" and "Description"), the earlier synonym wins.
HEADER_MAP: dict[str, tuple[str, ...]] = {
    "description": ("description", "item", "item description", "particulars",
                    "description of work", "scope"),
    "unit":        ("unit", "uom", "u/m", "units"),
    "quantity":    ("qty", "quantity", "qnty", "no.", "nos", "count"),
    "unit_rate":   ("rate", "unit rate", "unit price", "price", "u. rate"),
    "amount":      ("amount", "total", "line total", "value"),
    "part_number": ("part number", "part no", "mlfb", "model", "cat no",
                    "catalogue number", "manufacturer ref"),
}


class ReadClientBoqInput(BaseModel):
    document_id: str
    storage_key: str
    sheet: str | None = Field(None, description="Sheet name; default is the first visible sheet")
    header_row: int | None = Field(None, description="1-indexed; autodetected when omitted")
    max_rows: int = 5000


def _normalise(s) -> str:
    return str(s or "").strip().lower().replace("_", " ")


def _map_row(ws, r: int) -> dict[str, int]:
    """field -> column for one header row, preferring the earlier synonym."""
    best: dict[str, tuple[int, int]] = {}
    for c in range(1, min(ws.max_column, 40) + 1):
        label = _normalise(ws.cell(row=r, column=c).value)
        if not label:
            continue
        for field, synonyms in HEADER_MAP.items():
            if label in synonyms:
                rank = synonyms.index(label)
                if field not in best or rank < best[field][0]:
                    best[field] = (rank, c)
    return {f: c for f, (_, c) in best.items()}


def _detect_header(ws, limit: int = 25) -> tuple[int, dict[str, int]]:
    """The header row is the one that matches the most known synonyms."""
    best_row, best_map = 0, {}
    for r in range(1, min(limit, ws.max_row) + 1):
        mapping = _map_row(ws, r)
        if len(mapping) > len(best_map):
            best_row, best_map = r, mapping
    if not best_map:
        raise InvalidInput(
            "No recognisable BOQ header row found in the first 25 rows. "
            f"Known column names: {sorted({s for v in HEADER_MAP.values() for s in v})}")
    return best_row, best_map


@register("grid.read_client_boq", "grid", ReadClientBoqInput,
          "Read a client BOQ workbook into normalised rows (proposals, not truth)",
          modes=("preview",))
def read_client_boq(data: ReadClientBoqInput, storage: Storage | None = None) -> ToolResult:
    started = time.perf_counter()
    res = ToolResult(tool="grid.read_client_boq", engine_version=ENGINE_VERSION)
    if storage is None:
        raise InvalidInput("read_client_boq needs storage to fetch the workbook")

    wb = load_workbook(io.BytesIO(storage.read(data.storage_key)),
                       data_only=True, read_only=True)
    ws = wb[data.sheet] if data.sheet else next(
        (s for s in wb.worksheets if s.sheet_state == "visible"), wb.worksheets[0])

    if data.header_row:
        header_row = data.header_row
        colmap = _map_row(ws, header_row)
    else:
        header_row, colmap = _detect_header(ws)

    if "description" not in colmap:
        raise InvalidInput(
            f"Sheet {ws.title!r} has no description column; found {sorted(colmap)}")

    rows, skipped = [], 0
    for r in range(header_row + 1, min(ws.max_row, header_row + data.max_rows) + 1):
        def val(field):
            c = colmap.get(field)
            return ws.cell(row=r, column=c).value if c else None

        desc = val("description")
        if desc is None or not str(desc).strip():
            skipped += 1
            continue
        qty = val("quantity")
        try:
            qty = None if qty in (None, "") else float(qty)
        except (TypeError, ValueError):
            qty = None
        rate = val("unit_rate")
        try:
            rate = None if rate in (None, "") else float(rate)
        except (TypeError, ValueError):
            rate = None
        rows.append({
            "source_row": r,
            "description": str(desc).strip(),
            "unit": (str(val("unit")).strip() if val("unit") else None),
            "quantity": qty,
            "unit_rate": rate,
            "part_number": (str(val("part_number")).strip() if val("part_number") else None),
            # Everything read from a client file is 'imported' and unconfirmed.
            "quantity_source": "imported",
        })

    wb.close()
    res.outputs = {
        "sheet": ws.title,
        "header_row": header_row,
        "column_map": colmap,
        "unmapped_fields": sorted(set(HEADER_MAP) - set(colmap)),
        "row_count": len(rows),
        "blank_rows_skipped": skipped,
        "rows": rows,
        "proposal_target": "boq_items",
    }
    if "quantity" not in colmap:
        res.warnings.append("No quantity column recognised — every row has quantity null.")
    res.warnings.append(
        "Imported rows are proposals. Nothing here is a quantity until an engineer confirms it.")
    res.duration_ms = int((time.perf_counter() - started) * 1000)
    return res
