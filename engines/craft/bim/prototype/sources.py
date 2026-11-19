"""Turn a submitted drawing into a Plan: an ink image plus what is known about it.

Three kinds of submission, one result, so everything after this point is the
same whatever was uploaded:

* DXF — vectors with layers and units. Wall layers, door and window blocks and
  room-name text are read directly; the plan is drawn at a known scale.
* PDF — a vector or scanned sheet. Rendered to an image; the scale comes from
  the sheet's own "SCALE 1:100" when it has one; room names from its text.
* Image — a scan or photo of a plan. Pixels only; the scale has to be supplied
  or estimated later from the plan itself.

Pixel coordinates are (col, row) with row 0 at the top. `res` is metres per
pixel when known. World coordinates: x = x0 + col * res, y = y_top - row * res.
"""
from __future__ import annotations

import io
import math
import re
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from ...core import InvalidInput
from . import raster as R

TARGET_RES = 0.025             # 25 mm per pixel: a 100 mm wall is four pixels wide
MAX_PIXELS = 14_000_000

WALL_LAYER = re.compile(r"wall|mur|wand|partition|blockwork|masonry|a-?wall|core|colu?mn|\bcol\b|struct|conc", re.I)
DOOR_LAYER = re.compile(r"door|\bdr\b|a-?door|porte", re.I)
WINDOW_LAYER = re.compile(r"window|glaz|\bwin\b|wdw|a-?glaz|fenetre", re.I)
SKIP_LAYER = re.compile(r"dim|text|anno|title|border|frame|furn|grid|axis|hatch.?floor|vport|defpoints", re.I)
SCALE_TEXT = re.compile(r"(?:scale|sc\.?)\s*[:=]?\s*1\s*[:/]\s*(\d{1,4})|\b1\s*:\s*(50|75|100|125|150|200|250|300|500)\b", re.I)


@dataclass
class Plan:
    ink: np.ndarray                         # every drawn line, bool [row, col]
    faint: np.ndarray | None = None         # light lines too (blurred hairlines), for evidence only
    gray: np.ndarray | None = None          # the page itself, so wall extraction can try thresholds
    ink_used: np.ndarray | None = None      # the ink at the threshold the wall search chose
    walls_hint: np.ndarray | None = None    # geometry known to be wall (DXF wall layers)
    res: float | None = None                # metres per pixel, when known
    x0: float = 0.0
    y_top: float = 0.0
    texts: list[tuple[str, float, float]] = field(default_factory=list)      # (text, col, row)
    marks: list[dict] = field(default_factory=list)                          # door/window blocks
    kind: str = "image"
    scale_basis: str | None = None
    notes: list[str] = field(default_factory=list)
    assumptions: list[dict] = field(default_factory=list)
    world_aligned: bool = False             # True when coordinates are the drawing's own


def load(raw: bytes, filename: str, *, page: int = 1, scale: str | None = None,
         metres_per_unit: float | None = None, dpi: float | None = None,
         wall_layers: list[str] | None = None, door_layers: list[str] | None = None,
         window_layers: list[str] | None = None) -> Plan:
    name = filename.lower()
    head = raw[:8]
    if name.endswith(".dwg") or head.startswith(b"AC10"):
        raise InvalidInput(
            f"{filename} is a DWG. Save it as DXF (in AutoCAD: Save As → AutoCAD DXF, "
            "or the free ODA File Converter) and upload the DXF — no licence-compatible "
            "DWG reader exists.")
    if name.endswith(".dxf"):
        return _dxf(raw, filename, metres_per_unit, wall_layers, door_layers, window_layers)
    if name.endswith(".pdf") or head.startswith(b"%PDF"):
        return _pdf(raw, filename, page, scale, metres_per_unit)
    if name.endswith((".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp")):
        return _image(raw, filename, scale, metres_per_unit, dpi)
    raise InvalidInput(f"{filename}: upload a DXF, PDF or image (PNG/JPG/TIFF) of a floor plan.")


def parse_scale(text: str | None) -> int | None:
    if not text:
        return None
    m = re.search(r"1\s*[:/]\s*(\d{1,4})", text)
    return int(m.group(1)) if m else None


# -- DXF ----------------------------------------------------------------------------

def _dxf(raw, filename, metres_per_unit, wall_layers, door_layers, window_layers) -> Plan:
    from ezdxf import disassemble
    from ezdxf.bbox import extents
    from ...cad.read_dxf import open_dxf
    from ...cad.units import describe

    doc = open_dxf(raw, filename)
    msp = doc.modelspace()
    insunits = int(doc.header.get("$INSUNITS", 0))
    unit_name, mpu = describe(insunits)
    assumptions: list[dict] = []
    if metres_per_unit:
        mpu = metres_per_unit
    layers = {l.dxf.name for l in doc.layers}

    def pick(given, pattern):
        if given:
            wanted = {g.casefold() for g in given}
            return {l for l in layers if l.casefold() in wanted}
        return {l for l in layers if pattern.search(l) and not SKIP_LAYER.search(l)}

    wall_set = pick(wall_layers, WALL_LAYER)
    door_set = pick(door_layers, DOOR_LAYER)
    win_set = pick(window_layers, WINDOW_LAYER)

    segs_all, segs_wall, fills_wall, texts, marks = [], [], [], [], []
    for e in msp:
        layer = str(getattr(e.dxf, "layer", ""))
        kind = e.dxftype()
        if kind in ("TEXT", "MTEXT", "ATTRIB"):
            try:
                content = e.plain_text() if kind == "MTEXT" else str(e.dxf.text)
                p = e.dxf.insert
                texts.append((content.strip(), float(p[0]), float(p[1])))
            except Exception:
                pass
            continue
        if kind in ("DIMENSION", "LEADER", "MULTILEADER", "VIEWPORT") or SKIP_LAYER.search(layer):
            continue
        if kind == "INSERT":
            block = str(e.dxf.name)
            is_door = layer in door_set or DOOR_LAYER.search(block)
            is_win = layer in win_set or WINDOW_LAYER.search(block)
            if is_door or is_win:
                try:
                    bb = extents([e])
                    if bb.has_data:
                        c = bb.center
                        marks.append({"kind": "door" if is_door else "window",
                                      "x": float(c.x), "y": float(c.y),
                                      "size": float(max(bb.size.x, bb.size.y)), "block": block})
                except Exception:
                    pass
        on_wall = layer in wall_set
        try:
            for prim in disassemble.to_primitives(disassemble.recursive_decompose([e])):
                verts = [(float(v.x), float(v.y)) for v in prim.vertices()]
                if len(verts) < 2:
                    continue
                # Entities inside a block on layer "0" take the insert's layer.
                sub = str(prim.entity.dxf.layer) if prim.entity is not None else layer
                wall = sub in wall_set or (sub == "0" and on_wall)
                closed = math.dist(verts[0], verts[-1]) < 1e-9
                if prim.entity is not None and prim.entity.dxftype() in ("HATCH", "SOLID", "TRACE") and wall:
                    fills_wall.append(verts)
                segs_all.append(verts)
                if wall:
                    segs_wall.append(verts)
                if closed and wall and prim.entity is not None and prim.entity.dxftype() == "LWPOLYLINE" \
                        and getattr(prim.entity.dxf, "const_width", 0):
                    fills_wall.append(verts)
        except Exception:
            continue

    pts = np.array([p for s in (segs_wall or segs_all) for p in s]) if (segs_wall or segs_all) else None
    if pts is None:
        raise InvalidInput(f"{filename} has no linework in model space.")
    # Robust extent: ignore stray far-away entities.
    lo = np.percentile(pts, 0.2, axis=0)
    hi = np.percentile(pts, 99.8, axis=0)
    span = float(max(hi - lo))
    if mpu is None:
        if 2_000 < span < 2_000_000:
            mpu = 0.001
            assumptions.append({"key": "drawing_units", "value": "millimetres",
                                "basis": f"$INSUNITS is {insunits} ({unit_name}); the drawing is "
                                         f"{span:,.0f} units across, which is a building in millimetres",
                                "verify_from": "the drawing's dimension strings"})
        elif 2 < span < 2_000:
            mpu = 1.0
            assumptions.append({"key": "drawing_units", "value": "metres",
                                "basis": f"$INSUNITS is {insunits}; {span:,.1f} units across reads as metres",
                                "verify_from": "the drawing's dimension strings"})
        else:
            raise InvalidInput(f"{filename} declares no units and its size ({span:g}) does not "
                               "say which; set metres_per_unit.")
    margin = 2.0 / mpu
    lo, hi = lo - margin, hi + margin
    w_m, h_m = (hi - lo) * mpu
    res = max(TARGET_RES, math.sqrt(w_m * h_m / MAX_PIXELS))
    W, H = int(math.ceil(w_m / res)), int(math.ceil(h_m / res))
    f = mpu / res

    def to_px(x, y):
        return ((x - lo[0]) * f, (hi[1] - y) * f)

    ink_img = Image.new("1", (W, H), 0)
    wall_img = Image.new("1", (W, H), 0)
    di, dw = ImageDraw.Draw(ink_img), ImageDraw.Draw(wall_img)
    wall_ids = {id(s) for s in segs_wall}
    for s in segs_all:
        p = [to_px(*v) for v in s]
        di.line(p, fill=1, width=1)
        if id(s) in wall_ids:
            dw.line(p, fill=1, width=1)
    for s in fills_wall:
        p = [to_px(*v) for v in s]
        if len(p) >= 3:
            dw.polygon(p, fill=1)
            di.polygon(p, fill=1)

    plan = Plan(ink=np.array(ink_img, dtype=bool),
                walls_hint=np.array(wall_img, dtype=bool) if segs_wall else None,
                res=res, x0=float(lo[0] * mpu), y_top=float(hi[1] * mpu), kind="dxf",
                scale_basis=f"drawing units ({'stated' if not assumptions else 'inferred'}: {mpu:g} m per unit)",
                assumptions=assumptions, world_aligned=True)
    plan.texts = [(t, *to_px(x, y)) for t, x, y in texts if t]
    plan.marks = [dict(m, col=to_px(m["x"], m["y"])[0], row=to_px(m["x"], m["y"])[1], size_px=m["size"] * f)
                  for m in marks]
    plan.notes.append(f"wall layers: {', '.join(sorted(wall_set)) or 'none recognised — walls found by line weight'}")
    if door_set or win_set:
        plan.notes.append(f"door/window layers: {', '.join(sorted(door_set | win_set))}")
    return plan


# -- PDF -------------------------------------------------------------------------------

def _pdf(raw, filename, page, scale, metres_per_unit) -> Plan:
    import pdfplumber
    import pypdfium2 as pdfium

    try:
        pdf = pdfium.PdfDocument(raw)
    except Exception as e:
        raise InvalidInput(f"{filename} is not a readable PDF: {e}") from e
    if not 1 <= page <= len(pdf):
        raise InvalidInput(f"{filename} has {len(pdf)} page(s); page {page} does not exist.")

    words, sheet_scale, scale_src = [], None, None
    with pdfplumber.open(io.BytesIO(raw)) as doc:
        pg = doc.pages[page - 1]
        try:
            # keep_blank_chars joins "OFFICE 1" into one label instead of two words.
            words = pg.extract_words(keep_blank_chars=True, use_text_flow=False)
        except Exception:
            words = []
        text = pg.extract_text() or ""
    n_given = parse_scale(scale)
    if n_given:
        sheet_scale, scale_src = n_given, f"supplied: 1:{n_given}"
    else:
        found = [int(a or b) for a, b in SCALE_TEXT.findall(text)]
        if found:
            # The scale of the main view is the one stated most often.
            sheet_scale = max(set(found), key=found.count)
            scale_src = f"sheet text: 1:{sheet_scale}" + (" (other scales on the sheet ignored)" if len(set(found)) > 1 else "")

    pt_m = 0.0254 / 72                      # one PDF point on paper, in metres
    if metres_per_unit:
        m_per_pt = metres_per_unit
        scale_src = f"supplied: {metres_per_unit:g} m per point"
    elif sheet_scale:
        m_per_pt = pt_m * sheet_scale
    else:
        m_per_pt = None
    pdf_page = pdf[page - 1]
    pw, ph = pdf_page.get_size()
    if m_per_pt:
        px_per_pt = m_per_pt / TARGET_RES
    else:
        px_per_pt = 3.0                     # 216 dpi; the scale is settled later
    px_per_pt = min(px_per_pt, math.sqrt(MAX_PIXELS / (pw * ph)))
    bitmap = pdf_page.render(scale=px_per_pt, grayscale=True)
    gray = np.asarray(bitmap.to_pil().convert("L"))
    ink = gray < min(200.0, R.otsu(gray) + 10)
    plan = Plan(ink=ink, faint=gray < 232, gray=gray, res=(m_per_pt / px_per_pt) if m_per_pt else None, kind="pdf",
                scale_basis=scale_src)
    plan.texts = [(w["text"], (w["x0"] + w["x1"]) / 2 * px_per_pt, (w["top"] + w["bottom"]) / 2 * px_per_pt)
                  for w in words if w.get("text")]
    plan.notes.append(f"page {page} of {len(pdf)}, rendered at {px_per_pt * 72:.0f} dpi")
    if not words:
        plan.notes.append("no text layer: a scanned sheet; room names are not read")
    return plan


# -- images ----------------------------------------------------------------------------

def _image(raw, filename, scale, metres_per_unit, dpi) -> Plan:
    try:
        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img)
    except Exception as e:
        raise InvalidInput(f"{filename} is not a readable image: {e}") from e
    if dpi is None:
        info_dpi = img.info.get("dpi")
        if info_dpi and info_dpi[0] and 70 <= float(info_dpi[0]) <= 2400:
            dpi = float(info_dpi[0])
    img = img.convert("L")
    w, h = img.size
    shrink = math.sqrt(MAX_PIXELS / (w * h))
    if shrink < 1:
        img = img.resize((int(w * shrink), int(h * shrink)), Image.LANCZOS)
        if dpi:
            dpi *= shrink
    gray = np.asarray(img)
    ink = gray < min(200.0, R.otsu(gray) + 10)
    # Hairlines on a scan blur to light grey. Paper noise sits close to white,
    # so the faint threshold stays a little under the paper's own level.
    paper = float(np.percentile(gray, 90))
    faint = gray < min(paper - 30, 225)
    res, basis = None, None
    n = parse_scale(scale)
    if metres_per_unit:
        res, basis = metres_per_unit / (shrink if shrink < 1 else 1), f"supplied: {metres_per_unit:g} m per pixel"
    elif n and dpi:
        res, basis = 0.0254 / dpi * n, f"supplied scale 1:{n} at {dpi:.0f} dpi"
    plan = Plan(ink=ink, faint=faint, gray=gray, res=res, kind="image", scale_basis=basis)
    plan.notes.append("a scanned or photographed plan: no text is read, so rooms are named by type")
    return plan
