"""PDFCraft: read text, tables and vector paths out of a PDF.

Vector PDFs only. A scanned page has no text layer, and this module will not
pretend otherwise: it reports the page as needing OCR rather than returning an
empty string that reads like "there was nothing there".
"""
from __future__ import annotations

import io
import time

import pdfplumber
from pydantic import BaseModel, Field

from ..core import (ENGINE_VERSION, InvalidInput, MissingItem, Storage,
                    ToolResult, register)


class ExtractInput(BaseModel):
    document_id: str
    storage_key: str
    pages: list[int] | None = Field(None, description="1-indexed page numbers; default all")
    include_tables: bool = True
    include_vectors: bool = Field(False, description="lines/rects/curves — large on drawings")
    max_pages: int = 50


def _page_vectors(page) -> dict:
    def pt(o):
        return {"x0": round(o["x0"], 2), "y0": round(o["top"], 2),
                "x1": round(o["x1"], 2), "y1": round(o["bottom"], 2)}
    return {
        "lines": [pt(o) for o in page.lines],
        "rects": [pt(o) for o in page.rects],
        "curves": len(page.curves),
    }


@register("pdf.extract", "pdf", ExtractInput,
          "Extract text, tables and vector paths from a vector PDF",
          modes=("preview",))
def extract(data: ExtractInput, storage: Storage | None = None) -> ToolResult:
    started = time.perf_counter()
    res = ToolResult(tool="pdf.extract", engine_version=ENGINE_VERSION)
    if storage is None:
        raise InvalidInput("pdf.extract needs storage to fetch the document")

    raw = storage.read(data.storage_key)
    pages_out: list[dict] = []
    no_text: list[int] = []

    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        total = len(pdf.pages)
        wanted = data.pages or list(range(1, total + 1))
        bad = [p for p in wanted if p < 1 or p > total]
        if bad:
            raise InvalidInput(f"Document has {total} page(s); asked for {bad}")
        wanted = wanted[: data.max_pages]

        for n in wanted:
            page = pdf.pages[n - 1]
            text = page.extract_text() or ""
            entry: dict = {
                "page": n,
                "width": round(page.width, 2),
                "height": round(page.height, 2),
                "text": text,
                "char_count": len(text),
            }
            if not text.strip():
                no_text.append(n)
            if data.include_tables:
                tables = page.extract_tables() or []
                entry["tables"] = [
                    {"rows": len(t), "cols": max((len(r) for r in t), default=0), "data": t}
                    for t in tables
                ]
            if data.include_vectors:
                entry["vectors"] = _page_vectors(page)
            pages_out.append(entry)

    res.outputs = {
        "page_count": total,
        "pages_read": len(pages_out),
        "pages": pages_out,
        "pages_without_text_layer": no_text,
        "table_count": sum(len(p.get("tables", [])) for p in pages_out),
    }

    # Every requested page is an image. Returning "" here would be read as
    # "this datasheet says nothing", which is a different and wrong claim.
    if no_text and len(no_text) == len(pages_out):
        res.status = "missing_data"
        res.missing = [
            MissingItem(field="text_layer", record=f"document:{data.document_id}",
                        note=f"Pages {no_text} are images with no text layer. OCR them "
                             "first; this engine does not guess at pixels.")
        ]
    elif no_text:
        res.warnings.append(
            f"{len(no_text)} of {len(pages_out)} pages have no text layer "
            f"(pages {no_text}) — those pages returned no text, not empty content.")

    res.duration_ms = int((time.perf_counter() - started) * 1000)
    return res
