"""CADCraft: render a DXF to an SVG picture, so a browser can show the drawing.

A preview, not a drawing: the SVG is for looking at, and every quantity still
comes from the DXF it was made from. The DXF is never changed; the picture is
written as a new file under its own key.

The page is sized from the model-space extents at a fixed width (A3 landscape
width by default) so line weights and text read the same whatever unit the
drawing is in.
"""
from __future__ import annotations

import time
from typing import Literal

from ezdxf import bbox
from ezdxf.addons.drawing import Frontend, RenderContext, config, layout, svg
from pydantic import BaseModel, Field

from ..core import (ENGINE_VERSION, InvalidInput, OutputFile, Storage, ToolResult,
                    register, sha256)
from .read_dxf import open_dxf

SVG_MIME = "image/svg+xml"


class RenderSvgInput(BaseModel):
    document_id: str
    storage_key: str
    width_mm: float = Field(420, ge=50, le=2000,
                            description="width of the picture; height follows the drawing")
    background: Literal["white", "black"] = "white"
    output_key: str | None = None
    output_name: str = Field("preview.svg", pattern=r"^[\w.-]+\.svg$")


@register("cad.render_svg", "cad", RenderSvgInput,
          "Render a DXF's model space to an SVG picture for viewing in a browser; "
          "the DXF itself is not changed", modes=("commit",))
def render_svg(data: RenderSvgInput, storage: Storage | None = None) -> ToolResult:
    started = time.perf_counter()
    res = ToolResult(tool="cad.render_svg", engine_version=ENGINE_VERSION)
    if storage is None:
        raise InvalidInput("cad.render_svg needs storage to fetch the document")

    doc = open_dxf(storage.read(data.storage_key), data.storage_key)
    msp = doc.modelspace()
    ext = bbox.extents(msp, fast=True)
    if not ext.has_data or ext.size.x <= 0 or ext.size.y <= 0:
        raise InvalidInput(f"{data.storage_key} has no model-space geometry to render")

    width = data.width_mm
    height = round(width * ext.size.y / ext.size.x, 2)
    backend = svg.SVGBackend()
    cfg = config.Configuration(
        background_policy=(config.BackgroundPolicy.WHITE if data.background == "white"
                           else config.BackgroundPolicy.BLACK),
        color_policy=config.ColorPolicy.COLOR,
        # Thinner than this disappears at screen size; real weights are kept above it.
        min_lineweight=0.18,
    )
    Frontend(RenderContext(doc), backend, config=cfg).draw_layout(msp)
    page = layout.Page(width, height, layout.Units.mm, margins=layout.Margins.all(0))
    payload = backend.get_string(page, settings=layout.Settings(fit_page=True)).encode("utf-8")

    key = data.output_key or f"craft/render/{data.output_name}"
    storage.write(key, payload)
    res.files = [OutputFile(name=data.output_name, mime=SVG_MIME, storage_key=key,
                            byte_size=len(payload), sha256=sha256(payload))]
    res.outputs = {
        "width_mm": width,
        "height_mm": height,
        "extents_model": [[round(ext.extmin.x, 3), round(ext.extmin.y, 3)],
                          [round(ext.extmax.x, 3), round(ext.extmax.y, 3)]],
        "source_storage_key": data.storage_key,
    }
    res.duration_ms = int((time.perf_counter() - started) * 1000)
    return res
