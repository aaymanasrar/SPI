"""CADCraft: put a drawing on a sheet — frame, title block, scale bar, north arrow.

Layout follows ISO 5457 (sheet sizes, 20 mm filing margin on the left and 10 mm
elsewhere, centring marks, grid reference zones) and ISO 7200 (title block
fields, 180 mm wide, bottom right). Everything is drawn in model space at the
stated scale on one `SPI_SHEET` layer, so it can be frozen or deleted in one
action and the original drawing comes back untouched.

What it refuses to make up:
  * **Scale needs units.** A unitless DXF cannot be put on paper at 1:100,
    because nobody knows what one drawing unit is. That is `missing_data`, and
    no file is written.
  * **North needs a bearing.** The arrow is drawn only when `north_angle_deg`
    is given; a north arrow pointing the default way is a wrong arrow.
  * **ISO 7200 fields are mandatory.** A missing one is drawn as a red MISSING
    in its cell and returned as `missing_data`, so a draft sheet cannot pass for
    an issued one.
"""
from __future__ import annotations

import io
import math
import string
import time
from typing import Literal

from ezdxf import bbox
from ezdxf.enums import TextEntityAlignment
from pydantic import BaseModel, Field

from ..core import (ENGINE_VERSION, Finding, InvalidInput, MissingItem,
                    OutputFile, Storage, ToolResult, register, sha256)
from .read_dxf import open_dxf
from .units import describe

SHEET_LAYER = "SPI_SHEET"
DXF_MIME = "application/dxf"

#: Landscape (width, height) in millimetres. ISO 216 A-series and ANSI Y14.1.
PAPER_MM: dict[str, tuple[float, float]] = {
    "A0": (1189, 841), "A1": (841, 594), "A2": (594, 420), "A3": (420, 297),
    "A4": (297, 210),
    "ANSI_B": (431.8, 279.4), "ANSI_C": (558.8, 431.8), "ANSI_D": (863.6, 558.8),
    "ANSI_E": (1117.6, 863.6),
}
Paper = Literal["A0", "A1", "A2", "A3", "A4", "ANSI_B", "ANSI_C", "ANSI_D", "ANSI_E"]

#: Preferred scales (ISO 5455), used only to suggest a fit, never to choose one.
PREFERRED_SCALES = (1, 2, 5, 10, 20, 25, 50, 75, 100, 125, 200, 250, 500, 1000,
                    1250, 2000, 2500, 5000)

LEFT_MARGIN, MARGIN = 20.0, 10.0
TB_W, TB_ROW = 180.0, 9.0
TB_H = 4 * TB_ROW

ISO7200_REQUIRED = ("legal_owner", "title", "drawing_number", "date_of_issue",
                    "document_type", "created_by", "approved_by")


class TitleBlock(BaseModel):
    legal_owner: str | None = Field(None, description="ISO 7200: owner of the document (company)")
    title: str | None = None
    drawing_number: str | None = Field(None, description="ISO 7200 identification number")
    revision: str | None = None
    date_of_issue: str | None = Field(None, description="as it should print, e.g. 2026-11-19")
    document_type: str | None = Field(None, description="e.g. 'Shop drawing', 'Fire alarm layout'")
    created_by: str | None = None
    approved_by: str | None = None
    project: str | None = None
    client: str | None = None
    sheet: str | None = Field(None, description="e.g. '1/3'")


class SheetSetupInput(BaseModel):
    document_id: str
    storage_key: str
    paper: Paper
    orientation: Literal["landscape", "portrait"] = "landscape"
    scale: int = Field(gt=0, description="the denominator: 100 means 1:100")
    title_block: TitleBlock
    north_angle_deg: float | None = Field(
        None, description="bearing of north, degrees anticlockwise from straight up "
                          "the sheet. Omitted means no north arrow is drawn.")
    scale_bar: bool = True
    output_key: str | None = None
    output_name: str = "sheet.dxf"


def _nice_length(max_m: float) -> float:
    """Largest 1/2/5 x 10^n not above max_m."""
    if max_m <= 0:
        return 1.0
    p = 10 ** math.floor(math.log10(max_m))
    for m in (5, 2, 1):
        if m * p <= max_m:
            return m * p
    return p


def _fits(ext_w: float, ext_h: float, k: float, pw: float, ph: float) -> bool:
    return ext_w / k <= pw - LEFT_MARGIN - MARGIN and ext_h / k <= ph - 2 * MARGIN - TB_H


@register("cad.sheet_setup", "cad", SheetSetupInput,
          "Put a DXF on a sheet: ISO 5457 frame and zones, ISO 7200 title block, "
          "scale bar and north arrow, on a separate SPI_SHEET layer")
def sheet_setup(data: SheetSetupInput, storage: Storage | None = None) -> ToolResult:
    started = time.perf_counter()
    res = ToolResult(tool="cad.sheet_setup", engine_version=ENGINE_VERSION)
    if storage is None:
        raise InvalidInput("cad.sheet_setup needs storage to fetch the document")

    doc = open_dxf(storage.read(data.storage_key), data.storage_key)
    msp = doc.modelspace()
    insunits = int(doc.header.get("$INSUNITS", 0))
    unit_name, mpu = describe(insunits)
    if mpu is None:
        res.status = "missing_data"
        res.missing = [MissingItem(
            field="drawing_units", record=f"document:{data.document_id}",
            note=f"$INSUNITS is {insunits} ({unit_name}). Without a real length per "
                 f"drawing unit the drawing cannot be placed at 1:{data.scale}. Set "
                 "the units in the DXF and re-run. No file was written.")]
        res.duration_ms = int((time.perf_counter() - started) * 1000)
        return res

    ext = bbox.extents(msp, fast=True)
    if not ext.has_data:
        raise InvalidInput(f"{data.storage_key} has no model-space geometry to put on a sheet")

    pw, ph = PAPER_MM[data.paper]
    if data.orientation == "portrait":
        pw, ph = ph, pw
    if pw - LEFT_MARGIN - MARGIN < TB_W:
        raise InvalidInput(f"{data.paper} {data.orientation} is narrower than an "
                           f"ISO 7200 title block ({TB_W:.0f} mm)")

    # k = drawing units per paper millimetre at this scale.
    k = data.scale / (mpu * 1000.0)
    fits = _fits(ext.size.x, ext.size.y, k, pw, ph)
    suggestion = None
    if not fits:
        smallest = next((s for s in PREFERRED_SCALES
                         if _fits(ext.size.x, ext.size.y, s / (mpu * 1000.0), pw, ph)), None)
        bigger = next((p for p in ("A3", "A2", "A1", "A0")
                       if _fits(ext.size.x, ext.size.y, k, *PAPER_MM[p])), None)
        suggestion = {"scale": smallest, "paper_at_this_scale": bigger}
        res.findings.append(Finding(
            code="SHEET-DOES-NOT-FIT", severity="review",
            subject=f"document:{data.document_id}",
            detail=f"At 1:{data.scale} the drawing is {ext.size.x / k:.0f} × "
                   f"{ext.size.y / k:.0f} mm; the usable area of {data.paper} "
                   f"{data.orientation} above the title block is "
                   f"{pw - LEFT_MARGIN - MARGIN:.0f} × {ph - 2 * MARGIN - TB_H:.0f} mm.",
            action=("Use " + (f"1:{smallest}" if smallest else "a smaller scale")
                    + (f", or {bigger} at 1:{data.scale}" if bigger else "")
                    + ", or split the drawing across sheets.")))

    # Centre the drawing in the area above the title block band.
    cx_paper = (LEFT_MARGIN + pw - MARGIN) / 2
    cy_paper = (MARGIN + TB_H + ph - MARGIN) / 2
    ox = ext.center.x - cx_paper * k
    oy = ext.center.y - cy_paper * k

    def P(x: float, y: float) -> tuple[float, float]:
        return (ox + x * k, oy + y * k)

    if SHEET_LAYER not in doc.layers:
        doc.layers.add(SHEET_LAYER, color=7)

    def line(a, b, lw=25, colour=None):
        attrs = {"layer": SHEET_LAYER, "lineweight": lw}
        if colour is not None:
            attrs["color"] = colour
        msp.add_line(P(*a), P(*b), dxfattribs=attrs)

    def rect(x0, y0, x1, y1, lw=25):
        msp.add_lwpolyline([P(x0, y0), P(x1, y0), P(x1, y1), P(x0, y1)], close=True,
                           dxfattribs={"layer": SHEET_LAYER, "lineweight": lw})

    def text(s, x, y, size_mm, align=TextEntityAlignment.BOTTOM_LEFT, colour=None):
        attrs = {"layer": SHEET_LAYER, "height": size_mm * k}
        if colour is not None:
            attrs["color"] = colour
        msp.add_text(s, dxfattribs=attrs).set_placement(P(x, y), align=align)

    # ---- frame, centring marks and zones (ISO 5457) ---------------------------
    fx0, fy0, fx1, fy1 = LEFT_MARGIN, MARGIN, pw - MARGIN, ph - MARGIN
    rect(0, 0, pw, ph, lw=13)          # trimmed edge
    rect(fx0, fy0, fx1, fy1, lw=70)    # frame
    for a, b in (((pw / 2, 0), (pw / 2, fy0 + 5)), ((pw / 2, ph), (pw / 2, fy1 - 5)),
                 ((0, ph / 2), (fx0 + 5, ph / 2)), ((pw, ph / 2), (fx1 - 5, ph / 2))):
        line(a, b, lw=70)

    def zones(length: float) -> int:
        n = max(2, round(length / 50))
        return n + (n % 2)

    nx, ny = zones(fx1 - fx0), zones(fy1 - fy0)
    zw, zh = (fx1 - fx0) / nx, (fy1 - fy0) / ny
    letters = [c for c in string.ascii_uppercase if c not in "IO"]
    for i in range(nx):
        x = fx0 + i * zw
        if i:
            line((x, fy0), (x, fy0 - 5)); line((x, fy1), (x, fy1 + 5))
        for y in (fy0 - MARGIN / 2, fy1 + MARGIN / 2):
            text(str(i + 1), x + zw / 2, y, 3.5, TextEntityAlignment.MIDDLE_CENTER)
    for j in range(ny):
        y = fy1 - j * zh
        if j:
            line((fx0, y), (fx0 - 5, y)); line((fx1, y), (fx1 + 5, y))
        for x in (fx0 - 5, fx1 + MARGIN / 2):
            text(letters[j % len(letters)], x, y - zh / 2, 3.5, TextEntityAlignment.MIDDLE_CENTER)

    # ---- title block (ISO 7200), bottom right ----------------------------------
    tb = data.title_block
    x0, y0 = fx1 - TB_W, fy0
    rect(x0, y0, fx1, y0 + TB_H, lw=50)
    missing = [f for f in ISO7200_REQUIRED if not (getattr(tb, f) or "").strip()]

    def cell(xa, xb, ra, rb, label, field, size=3.0):
        """Cell spanning rows ra..rb (0 = bottom row), label top-left, value below."""
        ya, yb = y0 + ra * TB_ROW, y0 + (rb + 1) * TB_ROW
        rect(x0 + xa, ya, x0 + xb, yb)
        text(label, x0 + xa + 1.2, yb - 2.6, 1.8)
        value = (getattr(tb, field) or "").strip() if field else ""
        if field in missing:
            text("MISSING", x0 + xa + 1.2, ya + 1.6, 2.5, colour=1)
            return
        if value:
            # Shrink to fit before truncating; never below 2 mm, which still plots.
            size = max(min(size, (xb - xa - 2.4) / (0.62 * len(value))), 2.0)
        max_chars = max(int((xb - xa - 2.4) / (0.62 * size)), 3)
        if len(value) > max_chars:
            value = value[: max_chars - 1] + "…"
        vy = ya + 1.6 if rb == ra else (ya + yb) / 2 - size / 2
        text(value, x0 + xa + 1.2, vy, size)

    cell(0, 90, 3, 3, "PROJECT", "project")
    cell(90, 150, 3, 3, "DOCUMENT TYPE", "document_type")
    rect(x0 + 150, y0 + 3 * TB_ROW, x0 + 180, y0 + 4 * TB_ROW)
    text("SCALE", x0 + 151.2, y0 + 4 * TB_ROW - 2.6, 1.8)
    text(f"1:{data.scale}", x0 + 151.2, y0 + 3 * TB_ROW + 1.6, 3.0)
    cell(0, 90, 2, 2, "CLIENT", "client")
    cell(90, 180, 1, 2, "TITLE", "title", size=5.0)
    cell(0, 45, 1, 1, "CREATED BY", "created_by", size=2.5)
    cell(45, 90, 1, 1, "APPROVED BY", "approved_by", size=2.5)
    cell(0, 90, 0, 0, "LEGAL OWNER", "legal_owner")
    cell(90, 130, 0, 0, "DRAWING NO.", "drawing_number")
    cell(130, 142, 0, 0, "REV", "revision", size=2.5)
    cell(142, 165, 0, 0, "DATE OF ISSUE", "date_of_issue", size=2.5)
    cell(165, 180, 0, 0, "SHEET", "sheet", size=2.5)
    text(f"{data.paper} · ISO 5457 / ISO 7200", fx1, y0 + TB_H + 1.5, 2.0,
         TextEntityAlignment.BOTTOM_RIGHT)

    # ---- scale bar ---------------------------------------------------------------
    bar = None
    if data.scale_bar:
        length_m = _nice_length(60.0 * data.scale / 1000.0)   # about 60 mm on paper
        seg_mm = length_m * 1000.0 / data.scale / 4
        bx, by = fx0 + 8, fy0 + 10
        for i in range(4):
            xa = bx + i * seg_mm
            pts = [P(xa, by), P(xa + seg_mm, by), P(xa + seg_mm, by + 2.5), P(xa, by + 2.5)]
            msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": SHEET_LAYER})
            if i % 2 == 0:
                h = msp.add_hatch(color=7, dxfattribs={"layer": SHEET_LAYER})
                h.paths.add_polyline_path(pts, is_closed=True)
        for i, frac in ((0, 0), (2, 0.5), (4, 1)):
            text(f"{length_m * frac:g}", bx + i * seg_mm, by - 4, 2.5,
                 TextEntityAlignment.BOTTOM_CENTER)
        text("m", bx + 4 * seg_mm + 2, by - 4, 2.5)
        text(f"SCALE 1:{data.scale}", bx, by + 4.5, 2.5)
        bar = {"length_m": length_m, "segments": 4}

    # ---- north arrow ---------------------------------------------------------------
    if data.north_angle_deg is not None:
        a = math.radians(data.north_angle_deg)
        cx, cy, r = x0 - 18, y0 + TB_H / 2, 10.0

        def rot(dx, dy):
            return (cx + dx * math.cos(a) - dy * math.sin(a),
                    cy + dx * math.sin(a) + dy * math.cos(a))

        msp.add_circle(P(cx, cy), r * k, dxfattribs={"layer": SHEET_LAYER})
        tip, left, right, tail = rot(0, r), rot(-r * 0.35, -r * 0.7), rot(r * 0.35, -r * 0.7), rot(0, -r * 0.35)
        msp.add_lwpolyline([P(*tip), P(*left), P(*tail), P(*right)], close=True,
                           dxfattribs={"layer": SHEET_LAYER})
        h = msp.add_hatch(color=7, dxfattribs={"layer": SHEET_LAYER})
        h.paths.add_polyline_path([P(*tip), P(*left), P(*tail)], is_closed=True)
        n = rot(0, r + 4)
        text("N", n[0], n[1], 4.0, TextEntityAlignment.MIDDLE_CENTER)
    else:
        res.findings.append(Finding(
            code="SHEET-NO-NORTH", severity="info", subject=f"document:{data.document_id}",
            detail="No north bearing was supplied, so no north arrow was drawn.",
            action="Supply north_angle_deg from the site plan if the sheet needs one."))

    out = io.StringIO()
    doc.write(out)
    payload = out.getvalue().encode("utf-8")
    key = data.output_key or f"craft/sheet/{data.output_name}"
    storage.write(key, payload)

    res.files = [OutputFile(name=data.output_name, mime=DXF_MIME, storage_key=key,
                            byte_size=len(payload), sha256=sha256(payload))]
    res.outputs = {
        "paper": data.paper, "orientation": data.orientation,
        "paper_mm": [pw, ph], "scale": f"1:{data.scale}",
        "fits": fits, "suggestion": suggestion,
        "drawing_size_on_paper_mm": [round(ext.size.x / k, 1), round(ext.size.y / k, 1)],
        "sheet_origin_model": [round(ox, 3), round(oy, 3)],
        "zones": {"columns": nx, "rows": ny},
        "scale_bar": bar,
        "north_arrow": data.north_angle_deg is not None,
        "title_block": tb.model_dump(),
        "layer": SHEET_LAYER,
        "units": {"insunits": insunits, "name": unit_name, "metres_per_unit": mpu},
        "source_storage_key": data.storage_key,
    }
    if missing:
        res.status = "missing_data"
        res.missing = [MissingItem(
            field=f"title_block.{f}", record=f"document:{data.document_id}",
            note="Mandatory in ISO 7200. Drawn as a red MISSING so the sheet cannot "
                 "be mistaken for an issued one.") for f in missing]

    res.duration_ms = int((time.perf_counter() - started) * 1000)
    return res
