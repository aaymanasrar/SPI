"""The default .docx templates.

These are real, usable templates, not stand-ins. They are deliberately plain:
no logo, no letterhead, no colour. That is not laziness — a company letterhead
is SmartPage's own artwork and typography, and inventing one would put a
made-up identity on a document sent to a client.

To override any of them, put your own .docx in storage and point
`word.fill_template` at it. The substitution works on any .docx, so a template
exported from Word with `{{placeholders}}` typed into it needs nothing else.

**Every placeholder here is mandatory.** `word.fill_template` writes no file
while one is unfilled, so the field set is kept to what a document of that kind
genuinely cannot go out without.
"""
from __future__ import annotations

import io

from . import style

FOOTER = "{{project_name}}  ·  {{project_number}}  ·  Rev {{revision}}  ·  {{date}}"

#: template name -> (title, metadata labels/placeholders, body sections)
TEMPLATES: dict[str, dict] = {
    "transmittal": {
        "title": "Document Transmittal",
        "meta": [
            ("To", "{{to}}"),
            ("Project", "{{project_name}}"),
            ("Project number", "{{project_number}}"),
            ("Date", "{{date}}"),
            ("Revision", "{{revision}}"),
            ("Issued for", "{{purpose}}"),
        ],
        "body": [("Contents", "{{contents}}"),
                 ("Issued by", "{{issued_by}}")],
        "note": False,
    },
    "submittal_cover": {
        "title": "Material Submittal",
        "meta": [
            ("Project", "{{project_name}}"),
            ("Project number", "{{project_number}}"),
            ("Package", "{{package}}"),
            ("Specification section", "{{spec_section}}"),
            ("Date", "{{date}}"),
            ("Revision", "{{revision}}"),
        ],
        "body": [("Manufacturer", "{{manufacturer}}"),
                 ("Model", "{{product_model}}"),
                 ("Prepared by", "{{prepared_by}}")],
        "note": True,
    },
    "compliance": {
        "title": "Compliance Statement",
        "meta": [
            ("Project", "{{project_name}}"),
            ("Project number", "{{project_number}}"),
            ("Product", "{{product_model}}"),
            ("Date", "{{date}}"),
            ("Revision", "{{revision}}"),
        ],
        "body": [("Specification values taken from", "{{spec_source}}")],
        "note": True,
    },
}


def names() -> list[str]:
    return sorted(TEMPLATES)


def build(kind: str) -> bytes:
    """Return one default template as .docx bytes."""
    spec = TEMPLATES.get(kind)
    if spec is None:
        raise KeyError(f"No default template named {kind!r}. "
                       f"Known: {', '.join(names())}")

    doc = style.new_document()
    style.add_title(doc, spec["title"])
    style.add_meta(doc, spec["meta"])
    for heading, text in spec["body"]:
        style.add_heading(doc, heading)
        doc.add_paragraph(text)
    if spec["note"]:
        style.add_note(doc)
    style.add_footer(doc, FOOTER)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def placeholders(kind: str) -> set[str]:
    """Which values a caller must supply for this template. Useful for a form."""
    import re
    spec = TEMPLATES[kind]
    text = " ".join(
        [v for _, v in spec["meta"]] + [t for _, t in spec["body"]] + [FOOTER])
    return set(re.findall(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}", text))
