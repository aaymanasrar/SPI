"""WordCraft: build a Comply / Deviate / Clarify sheet.

The rule that shapes this module: a clause with no captured product
specification is NOT "Comply". Compliance is a claim made to a client, and the
cost of a wrong one is a variation order or a rejected submittal. So the engine
decides a clause only when it has a captured value to compare; otherwise the
clause is returned as missing_data and no sheet is written.

Comparison is deliberately narrow. Numeric clauses with an explicit operator and
unit are evaluated; prose clauses are not interpreted, they are routed to a
human as 'Clarify'. There is no partial credit and no fuzzy matching.
"""
from __future__ import annotations

import io
import time
from typing import Literal

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt
from pydantic import BaseModel, Field

from ..core import (ENGINE_VERSION, InvalidInput, MissingItem, OutputFile,
                    Provenance, Storage, ToolResult, register, sha256)
from .fill_template import DOCX_MIME

Verdict = Literal["Comply", "Deviate", "Clarify"]
Operator = Literal[">=", "<=", "==", ">", "<"]


class Clause(BaseModel):
    reference: str = Field(description="e.g. 'Spec 28 31 00 2.3.A'")
    text: str
    parameter: str | None = Field(
        None, description="the captured spec key to compare, e.g. 'alarm_current_ma'")
    operator: Operator | None = None
    value: float | None = None
    unit: str | None = None


class ComplianceInput(BaseModel):
    project_name: str
    product_model: str
    clauses: list[Clause]
    captured_specs: dict[str, float] = Field(
        default_factory=dict,
        description="values actually captured for this product model; a key that "
                    "is absent is absent, not zero")
    spec_source: str = Field(
        description="where captured_specs came from, printed in the sheet")
    output_key: str | None = None
    output_name: str = "Compliance_Sheet.docx"


def _evaluate(clause: Clause, specs: dict[str, float]) -> tuple[Verdict, str]:
    """Returns (verdict, remark). Only a fully specified numeric clause decides."""
    if clause.parameter is None or clause.operator is None or clause.value is None:
        return ("Clarify",
                "Not a numeric requirement; needs an engineer's reading.")
    actual = specs.get(clause.parameter)
    if actual is None:
        # Caller must treat this as missing_data; never a verdict.
        return ("Clarify", f"No captured value for '{clause.parameter}'.")
    ok = {">=": actual >= clause.value, "<=": actual <= clause.value,
          "==": actual == clause.value, ">": actual > clause.value,
          "<": actual < clause.value}[clause.operator]
    unit = f" {clause.unit}" if clause.unit else ""
    return (("Comply" if ok else "Deviate"),
            f"Offered {actual}{unit} against required {clause.operator} "
            f"{clause.value}{unit}.")


@register("word.compliance_sheet", "word", ComplianceInput,
          "Build a Comply/Deviate/Clarify sheet from spec clauses and captured specs")
def compliance_sheet(data: ComplianceInput,
                     storage: Storage | None = None) -> ToolResult:
    started = time.perf_counter()
    res = ToolResult(tool="word.compliance_sheet", engine_version=ENGINE_VERSION)
    if storage is None:
        raise InvalidInput("word.compliance_sheet needs storage to write the sheet")
    if not data.clauses:
        res.status = "invalid_input"
        res.warnings.append("No clauses given; there is nothing to assess")
        return res

    rows: list[dict] = []
    missing: list[MissingItem] = []
    for c in data.clauses:
        verdict, remark = _evaluate(c, data.captured_specs)
        rows.append({"reference": c.reference, "text": c.text,
                     "verdict": verdict, "remark": remark})
        if (c.parameter is not None and c.operator is not None
                and c.value is not None and c.parameter not in data.captured_specs):
            missing.append(MissingItem(
                field=c.parameter,
                record=f"product_model:{data.product_model}",
                note=f"Clause {c.reference} requires {c.parameter} "
                     f"{c.operator} {c.value}{' ' + c.unit if c.unit else ''}, and "
                     "no value is captured for this model. Capture it from the "
                     "datasheet. The clause will not be marked Comply on the "
                     "basis that nothing contradicts it."))

    counts = {v: sum(1 for r in rows if r["verdict"] == v)
              for v in ("Comply", "Deviate", "Clarify")}
    res.outputs = {"rows": rows, "counts": counts,
                   "clause_count": len(rows),
                   "product_model": data.product_model}

    if missing:
        # No file. A half-assessed sheet circulates as if it were finished.
        res.status = "missing_data"
        res.missing = missing
        res.duration_ms = int((time.perf_counter() - started) * 1000)
        return res

    doc = docx.Document()
    doc.add_heading("Compliance Statement", level=1)
    meta = doc.add_paragraph()
    meta.add_run(f"Project: {data.project_name}\n").bold = True
    meta.add_run(f"Product: {data.product_model}\n")
    meta.add_run(f"Specification values taken from: {data.spec_source}")

    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    for cell, head in zip(table.rows[0].cells,
                          ("Clause", "Requirement", "Status", "Remark")):
        cell.text = head
        cell.paragraphs[0].runs[0].bold = True
    for r in rows:
        cells = table.add_row().cells
        cells[0].text = r["reference"]
        cells[1].text = r["text"]
        cells[2].text = r["verdict"]
        cells[3].text = r["remark"]

    summary = doc.add_paragraph()
    summary.add_run(
        f"\n{counts['Comply']} comply, {counts['Deviate']} deviate, "
        f"{counts['Clarify']} to clarify, of {len(rows)} clauses.")
    note = doc.add_paragraph()
    note.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = note.add_run(
        "Generated by SmartPage Intelligence from captured specification values. "
        "A proposal for engineering review; not a submittal until signed.")
    run.italic = True
    run.font.size = Pt(8)

    buf = io.BytesIO()
    doc.save(buf)
    payload = buf.getvalue()
    key = data.output_key or f"craft/documents/{data.output_name}"
    storage.write(key, payload)

    res.files = [OutputFile(name=data.output_name, mime=DOCX_MIME, storage_key=key,
                            byte_size=len(payload), sha256=sha256(payload))]
    res.provenance = [
        Provenance(value_ref=f"clause:{r['reference']}={r['verdict']}",
                   source=data.spec_source)
        for r in rows if r["verdict"] in ("Comply", "Deviate")
    ]
    res.duration_ms = int((time.perf_counter() - started) * 1000)
    return res
