"""CADCraft: write review markup to a NEW DXF.

The original is opened read-only and copied. Everything this adds goes on a
dedicated `SPI_MARKUP` layer so a recipient can freeze or delete it in one
action and get their drawing back.
"""
from __future__ import annotations

import io
import time

from ezdxf.enums import TextEntityAlignment
from pydantic import BaseModel, Field

from ..core import (ENGINE_VERSION, InvalidInput, OutputFile, Storage,
                    ToolResult, register, sha256)
from .read_dxf import open_dxf

MARKUP_LAYER = "SPI_MARKUP"
DXF_MIME = "application/dxf"


class Note(BaseModel):
    x: float
    y: float
    text: str
    circle_radius: float | None = Field(
        None, description="drawing units; omitted means text only")


class MarkupInput(BaseModel):
    document_id: str
    storage_key: str
    notes: list[Note]
    text_height: float = Field(
        250.0, description="drawing units — depends on drawing scale, so it is an "
                           "input, not a constant")
    output_key: str | None = None
    output_name: str = "markup.dxf"


@register("cad.markup", "cad", MarkupInput,
          "Add review notes to a copy of a DXF on a dedicated SPI_MARKUP layer")
def markup(data: MarkupInput, storage: Storage | None = None) -> ToolResult:
    started = time.perf_counter()
    res = ToolResult(tool="cad.markup", engine_version=ENGINE_VERSION)
    if storage is None:
        raise InvalidInput("cad.markup needs storage to fetch the document")
    if not data.notes:
        res.status = "invalid_input"
        res.warnings.append("No notes given; nothing to mark up")
        return res

    doc = open_dxf(storage.read(data.storage_key), data.storage_key)
    if MARKUP_LAYER not in doc.layers:
        doc.layers.add(MARKUP_LAYER, color=1)   # 1 = red, the ACI convention
    msp = doc.modelspace()

    for note in data.notes:
        if note.circle_radius:
            msp.add_circle((note.x, note.y), note.circle_radius,
                           dxfattribs={"layer": MARKUP_LAYER})
        t = msp.add_text(note.text, dxfattribs={"layer": MARKUP_LAYER,
                                                "height": data.text_height})
        t.set_placement((note.x, note.y), align=TextEntityAlignment.LEFT)

    out = io.StringIO()
    doc.write(out)
    payload = out.getvalue().encode("utf-8")

    key = data.output_key or f"craft/markup/{data.output_name}"
    storage.write(key, payload)

    res.files = [OutputFile(name=data.output_name, mime=DXF_MIME, storage_key=key,
                            byte_size=len(payload), sha256=sha256(payload))]
    res.outputs = {"note_count": len(data.notes), "layer": MARKUP_LAYER,
                   "source_storage_key": data.storage_key}
    res.duration_ms = int((time.perf_counter() - started) * 1000)
    return res
