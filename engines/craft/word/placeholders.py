"""Placeholder substitution for .docx.

Why this is not a string replace: Word splits a paragraph into runs wherever
formatting changes, and it also splits for reasons of its own — a spell-check
boundary is enough. `{{client_name}}` typed in one go routinely arrives as
`{{client`, `_na`, `me}}` across three runs, so a per-run replace finds nothing
and silently leaves the placeholder in an issued document.

docxtpl solves this, but it is LGPL-2.1 and not on the allowed licence list, so
this does the run merging itself with python-docx (MIT).
"""
from __future__ import annotations

import re

PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")


def find_in_text(text: str) -> set[str]:
    return set(PLACEHOLDER.findall(text))


def _fill_paragraph(par, values: dict[str, str], used: set[str]) -> None:
    text = par.text
    if not PLACEHOLDER.search(text):
        return

    def sub(m: re.Match) -> str:
        key = m.group(1)
        if key in values:
            used.add(key)
            return str(values[key])
        return m.group(0)          # unknown key is left alone and reported later

    new = PLACEHOLDER.sub(sub, text)
    if new == text:
        return

    runs = par.runs
    if not runs:
        return
    # Collapse into the first run, which keeps the paragraph's style and the
    # first run's character formatting. Formatting that varied mid-placeholder
    # cannot be preserved -- there is no longer a boundary to hang it on.
    runs[0].text = new
    for r in runs[1:]:
        r.text = ""


def _iter_paragraphs(container):
    """Paragraphs in body order, including inside tables, nested tables and cells."""
    for par in container.paragraphs:
        yield par
    for table in container.tables:
        for row in table.rows:
            for cell in row.cells:
                yield from _iter_paragraphs(cell)


def iter_all_paragraphs(doc):
    """Body, plus every header and footer of every section.

    A project number lives in the footer as often as in the body, and a
    placeholder left unfilled there is just as visible to the client.
    """
    yield from _iter_paragraphs(doc)
    for section in doc.sections:
        for part in (section.header, section.footer,
                     section.first_page_header, section.first_page_footer,
                     section.even_page_header, section.even_page_footer):
            if part is not None:
                yield from _iter_paragraphs(part)


def scan(doc) -> set[str]:
    """Every placeholder key the document contains."""
    found: set[str] = set()
    for par in iter_all_paragraphs(doc):
        found |= find_in_text(par.text)
    return found


def fill(doc, values: dict[str, str]) -> tuple[set[str], set[str]]:
    """Substitute in place. Returns (keys used, keys still unfilled)."""
    used: set[str] = set()
    for par in iter_all_paragraphs(doc):
        _fill_paragraph(par, values, used)
    remaining: set[str] = set()
    for par in iter_all_paragraphs(doc):
        remaining |= find_in_text(par.text)
    return used, remaining
