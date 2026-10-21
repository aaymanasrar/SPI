"""PLACEHOLDER .docx templates.

SmartPage's real templates have not been supplied (docs/data-requests/
craft-engines.md 1-3). These exist so the engine is testable and demonstrable,
and every one of them says PLACEHOLDER on its face so a generated document
cannot be mistaken for a company document and sent.

Delete this module once the real templates land; nothing else imports it.
"""
from __future__ import annotations

import io

import docx
from docx.shared import Pt

BANNER = ("PLACEHOLDER TEMPLATE - NOT A SMARTPAGE DOCUMENT. "
          "Replace with the approved template before issuing anything.")

SPECS = {
    "transmittal": [
        ("Transmittal", 1),
        ("To: {{recipient}}", 0),
        ("Attention: {{attention}}", 0),
        ("Project: {{project_name}}  ({{project_number}})", 0),
        ("Date: {{date}}        Revision: {{revision}}", 0),
        ("We enclose the following for {{purpose}}:", 0),
        ("{{contents}}", 0),
        ("Issued by: {{issued_by}}", 0),
    ],
    "submittal_cover": [
        ("Material Submittal", 1),
        ("Project: {{project_name}}", 0),
        ("Project number: {{project_number}}", 0),
        ("Package: {{package}}", 0),
        ("Specification section: {{spec_section}}", 0),
        ("Manufacturer: {{manufacturer}}", 0),
        ("Model: {{product_model}}", 0),
        ("Revision: {{revision}}        Date: {{date}}", 0),
        ("Prepared by: {{prepared_by}}", 0),
    ],
    "compliance": [
        ("Compliance Statement", 1),
        ("Project: {{project_name}}", 0),
        ("Product: {{product_model}}", 0),
        ("Specification values taken from: {{spec_source}}", 0),
    ],
}


def build(kind: str) -> bytes:
    """Return a PLACEHOLDER .docx as bytes."""
    if kind not in SPECS:
        raise KeyError(f"No placeholder template named {kind!r}. "
                       f"Known: {', '.join(sorted(SPECS))}")
    doc = docx.Document()
    warn = doc.add_paragraph()
    run = warn.add_run(BANNER)
    run.bold = True
    run.font.size = Pt(9)

    for text, level in SPECS[kind]:
        if level:
            doc.add_heading(text, level=level)
        else:
            doc.add_paragraph(text)

    # A footer placeholder, because that is where a project number usually sits
    # and it is the one most often left unfilled.
    doc.sections[0].footer.paragraphs[0].text = (
        "{{project_number}} - {{revision}} - PLACEHOLDER TEMPLATE")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
