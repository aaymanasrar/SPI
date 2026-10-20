"""PDFCraft: merge a submittal pack and stamp it.

Originals are never modified (ARCHITECTURE.md 7). This reads them and writes one
new file.
"""
from __future__ import annotations

import io
import time
from typing import Literal

from pypdf import PdfReader, PdfWriter
from pydantic import BaseModel, Field
from reportlab.lib.colors import Color
from reportlab.pdfgen import canvas

from ..core import (ENGINE_VERSION, InvalidInput, OutputFile, Storage,
                    ToolResult, register, sha256)

PDF_MIME = "application/pdf"
Position = Literal["bottom-right", "bottom-center", "top-right"]


class StampSpec(BaseModel):
    text: str | None = Field(None, description="e.g. 'Rev 03 — For Approval'")
    page_numbers: bool = True
    position: Position = "bottom-right"
    font_size: int = 8


class PackInput(BaseModel):
    document_ids: list[str] = Field(default_factory=list)
    storage_keys: list[str]
    stamp: StampSpec | None = None
    output_key: str | None = None
    output_name: str = "Submittal_Pack.pdf"


def _overlay(width: float, height: float, text: str, pos: Position, size: int) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))
    c.setFont("Helvetica", size)
    c.setFillColor(Color(0.25, 0.25, 0.25))
    margin = 18
    if pos == "bottom-right":
        c.drawRightString(width - margin, margin, text)
    elif pos == "bottom-center":
        c.drawCentredString(width / 2, margin, text)
    else:
        c.drawRightString(width - margin, height - margin - size, text)
    c.save()
    return buf.getvalue()


@register("pdf.pack", "pdf", PackInput,
          "Merge PDFs into one submittal pack and stamp page numbers / revision")
def pack(data: PackInput, storage: Storage | None = None) -> ToolResult:
    started = time.perf_counter()
    res = ToolResult(tool="pdf.pack", engine_version=ENGINE_VERSION)
    if storage is None:
        raise InvalidInput("pdf.pack needs storage to fetch the documents")
    if not data.storage_keys:
        res.status = "invalid_input"
        res.warnings.append("No source documents given")
        return res

    writer = PdfWriter()
    per_source: list[dict] = []
    for key in data.storage_keys:
        reader = PdfReader(io.BytesIO(storage.read(key)))
        if reader.is_encrypted:
            raise InvalidInput(
                f"{key} is encrypted. Decrypt it before packing — this engine will "
                "not attempt to bypass document protection.")
        for page in reader.pages:
            writer.add_page(page)
        per_source.append({"storage_key": key, "pages": len(reader.pages)})

    total = len(writer.pages)
    if data.stamp:
        for i, page in enumerate(writer.pages, start=1):
            bits = []
            if data.stamp.text:
                bits.append(data.stamp.text)
            if data.stamp.page_numbers:
                bits.append(f"Page {i} of {total}")
            if not bits:
                continue
            w = float(page.mediabox.width)
            h = float(page.mediabox.height)
            ov = PdfReader(io.BytesIO(_overlay(w, h, "   ·   ".join(bits),
                                               data.stamp.position,
                                               data.stamp.font_size)))
            page.merge_page(ov.pages[0])

    buf = io.BytesIO()
    writer.write(buf)
    payload = buf.getvalue()

    key = data.output_key or f"craft/packs/{data.output_name}"
    if storage is not None:
        storage.write(key, payload)

    res.files = [OutputFile(name=data.output_name, mime=PDF_MIME, storage_key=key,
                            byte_size=len(payload), sha256=sha256(payload))]
    res.outputs = {
        "page_count": total,
        "source_count": len(data.storage_keys),
        "sources": per_source,
        "stamped": bool(data.stamp),
    }
    res.duration_ms = int((time.perf_counter() - started) * 1000)
    return res
