"""GridCraft: BOQ rows -> .xlsx with live formulas and a provenance sheet."""
from __future__ import annotations

import io
import time
from typing import Literal

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from pydantic import BaseModel, Field

from ..core import (ENGINE_VERSION, LocalStorage, MissingItem, OutputFile,
                    Provenance, Storage, ToolResult, register, sha256)
from .formulas import product, total

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheetml"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

HDR_FILL = PatternFill("solid", fgColor="1F3A5F")
HDR_FONT = Font(bold=True, color="FFFFFF")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(top=THIN, bottom=THIN, left=THIN, right=THIN)
MONEY = '#,##0.00'
QTY = '#,##0.###'


class BoqLine(BaseModel):
    description: str
    unit: str
    quantity: float
    system: str | None = None
    category: str | None = None
    ordinal: int | None = None
    quantity_source: Literal["rule_execution", "manual", "imported"] = "manual"
    rule_execution_id: str | None = None
    boq_item_id: str | None = None
    part_number: str | None = None
    unit_cost_minor: int | None = None
    price_source: str | None = None
    currency: str | None = None


class WriteBoqInput(BaseModel):
    boq_id: str
    project_name: str
    project_code: str
    revision: int = 1
    currency: str = "SAR"
    lines: list[BoqLine] = Field(default_factory=list)
    #: When true, a line without a resolved price is missing_data rather than a
    #: blank rate. An unpriced BOQ is a legitimate deliverable; a SILENTLY
    #: unpriced one that was meant to be priced is not.
    require_pricing: bool = False
    output_key: str | None = None


def _sheet(wb: Workbook, name: str, lines: list[BoqLine], currency: str,
           prov: list[Provenance]) -> float:
    ws = wb.create_sheet(name[:31])
    headers = ["#", "Part number", "Description", "Unit", "Qty",
               f"Rate ({currency})", f"Amount ({currency})", "Quantity source"]
    ws.append(headers)
    for c in ws[1]:
        c.fill, c.font = HDR_FILL, HDR_FONT
        c.alignment = Alignment(wrap_text=True, vertical="center")

    first_data = 2
    for i, ln in enumerate(lines, start=1):
        row = first_data + i - 1
        rate = None if ln.unit_cost_minor is None else ln.unit_cost_minor / 100
        ws.cell(row=row, column=1, value=ln.ordinal if ln.ordinal is not None else i)
        ws.cell(row=row, column=2, value=ln.part_number or "")
        ws.cell(row=row, column=3, value=ln.description)
        ws.cell(row=row, column=4, value=ln.unit)
        ws.cell(row=row, column=5, value=ln.quantity).number_format = QTY
        rc = ws.cell(row=row, column=6, value=rate)
        rc.number_format = MONEY
        # The value is computed in Python by Excel's own rule; the formula is
        # written so the human can change the rate and see the amount follow.
        ac = ws.cell(row=row, column=7,
                     value=product(f"E{row}", f"F{row}"))
        ac.number_format = MONEY
        src = ln.quantity_source
        if ln.quantity_source == "rule_execution" and ln.rule_execution_id:
            src = f"rule_execution:{ln.rule_execution_id}"
            prov.append(Provenance(value_ref=f"{name}!E{row}",
                                   source=f"rule_execution:{ln.rule_execution_id}"))
        elif ln.boq_item_id:
            prov.append(Provenance(value_ref=f"{name}!E{row}",
                                   source=f"boq_item:{ln.boq_item_id}.quantity"))
        if ln.price_source and ln.boq_item_id:
            prov.append(Provenance(value_ref=f"{name}!F{row}",
                                   source=f"price_source:{ln.price_source}"))
        ws.cell(row=row, column=8, value=src)
        for col in range(1, 9):
            ws.cell(row=row, column=col).border = BORDER

    last = first_data + len(lines) - 1
    trow = last + 1
    ws.cell(row=trow, column=3, value="Subtotal").font = Font(bold=True)
    tc = ws.cell(row=trow, column=7, value=total(f"G{first_data}", f"G{last}"))
    tc.font, tc.number_format = Font(bold=True), MONEY

    for col, w in zip(range(1, 9), (6, 22, 56, 10, 12, 14, 16, 30)):
        ws.column_dimensions[get_column_letter(col)].width = w
    ws.freeze_panes = "A2"

    return sum((ln.quantity * (ln.unit_cost_minor or 0) / 100) for ln in lines)


@register("grid.write_boq", "grid", WriteBoqInput,
          "Render BOQ lines to .xlsx with live formulas and a provenance sheet")
def write_boq(data: WriteBoqInput, storage: Storage | None = None) -> ToolResult:
    started = time.perf_counter()
    res = ToolResult(tool="grid.write_boq", engine_version=ENGINE_VERSION)

    if not data.lines:
        res.status = "invalid_input"
        res.warnings.append("No BOQ lines supplied")
        return res

    if data.require_pricing:
        missing = [
            MissingItem(field="unit_cost_minor",
                        record=f"boq_item:{ln.boq_item_id or ln.description}",
                        note="No price resolved. Spec 13.2 has no fallback to a market "
                             "price; capture a vendor or supplier price first.")
            for ln in data.lines if ln.unit_cost_minor is None
        ]
        if missing:
            res.status = "missing_data"
            res.missing = missing
            res.duration_ms = int((time.perf_counter() - started) * 1000)
            return res

    wb = Workbook()
    wb.remove(wb.active)
    prov: list[Provenance] = []

    by_system: dict[str, list[BoqLine]] = {}
    for ln in data.lines:
        by_system.setdefault(ln.system or "General", []).append(ln)

    sheet_totals: dict[str, float] = {}
    for system, lines in by_system.items():
        sheet_totals[system] = _sheet(wb, system, lines, data.currency, prov)

    # Summary first, built from cross-sheet references so Excel keeps it live.
    summary = wb.create_sheet("Summary", 0)
    summary.append([f"{data.project_name} ({data.project_code})"])
    summary["A1"].font = Font(bold=True, size=14)
    summary.append([f"BOQ revision {data.revision} · {data.boq_id}"])
    summary.append([])
    summary.append(["System", f"Amount ({data.currency})"])
    for c in summary[4]:
        c.fill, c.font = HDR_FILL, HDR_FONT
    for system in by_system:
        ws = wb[system[:31]]
        last_row = ws.max_row
        summary.append([system, f"='{system[:31]}'!G{last_row}"])
        summary.cell(row=summary.max_row, column=2).number_format = MONEY
    tr = summary.max_row + 1
    summary.cell(row=tr, column=1, value="Total").font = Font(bold=True)
    gt = summary.cell(row=tr, column=2, value=total(f"B5", f"B{tr-1}"))
    gt.font, gt.number_format = Font(bold=True), MONEY
    summary.column_dimensions["A"].width = 40
    summary.column_dimensions["B"].width = 18

    # Provenance sheet: hidden, because it is for audit rather than for reading,
    # but present in the file so the workbook can always answer for itself.
    pws = wb.create_sheet("Provenance")
    pws.append(["Cell", "Value reference", "Source"])
    for c in pws[1]:
        c.fill, c.font = HDR_FILL, HDR_FONT
    for p in prov:
        pws.append([p.value_ref, p.value_ref, p.source])
    pws.append([])
    pws.append(["Generated by", ENGINE_VERSION])
    pws.append(["BOQ", data.boq_id])
    for col, w in zip("ABC", (28, 28, 60)):
        pws.column_dimensions[col].width = w
    pws.sheet_state = "hidden"

    buf = io.BytesIO()
    wb.save(buf)
    payload = buf.getvalue()

    name = f"BOQ_{data.project_code}_Rev{data.revision:02d}.xlsx"
    key = data.output_key or f"craft/{data.boq_id}/{name}"
    if storage is not None:
        storage.write(key, payload)
    res.files = [OutputFile(name=name, mime=XLSX_MIME, storage_key=key,
                            byte_size=len(payload), sha256=sha256(payload))]
    res.provenance = prov
    res.outputs = {
        "systems": list(by_system),
        "line_count": len(data.lines),
        "sheet_totals": {k: round(v, 2) for k, v in sheet_totals.items()},
        "grand_total": round(sum(sheet_totals.values()), 2),
        "currency": data.currency,
        "priced_lines": sum(1 for l in data.lines if l.unit_cost_minor is not None),
    }
    unpriced = [l for l in data.lines if l.unit_cost_minor is None]
    if unpriced:
        res.warnings.append(
            f"{len(unpriced)} of {len(data.lines)} lines have no resolved price; "
            "rate and amount are blank for those rows.")
    res.duration_ms = int((time.perf_counter() - started) * 1000)
    return res
