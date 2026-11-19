"""A two-storey office drawn three ways — DXF, PDF sheet, scanned image — with
the true rooms and openings alongside, so the prototype pipeline can be scored.

No client drawings have been supplied. These are drawn the way architects
draw: walls as double lines on A-WALL (DXF) or solid fill (PDF), doors as a
leaf and a swing arc, windows as three lines across the gap, room names in the
middle of each room, furniture and dimensions on their own layers, and on the
PDF a border, a title block and "SCALE 1:100". The scan is the PDF printed,
blurred, speckled and fed through a scanner a little crooked.

    python fixtures/floor_plans.py OUT_DIR
"""
from __future__ import annotations

import io
import math
import sys
from pathlib import Path

EXT, INT = 0.30, 0.15              # wall thicknesses, m

# Walls as centrelines (x1, y1, x2, y2, thickness) and openings on them as
# (distance from the wall's start to the opening centre, width, kind).
LEVELS = {
    "Ground floor": {
        "walls": [
            ((0, 0, 20, 0, EXT), [(4, 1.8, "door"), (11, 1.5, "window"), (17, 1.5, "window")]),
            ((20, 0, 20, 12, EXT), [(3, 1.2, "window"), (10, 1.2, "window")]),
            ((20, 12, 0, 12, EXT), [(3.5, 1.2, "window"), (16.5, 1.5, "window")]),
            ((0, 12, 0, 0, EXT), [(2, 1.2, "window"), (9, 1.2, "window")]),
            ((8, 0, 8, 6, INT), []),
            ((14, 0, 14, 6, INT), []),
            ((0, 6, 20, 6, INT), [(4, 1.2, "door"), (11, 0.9, "door"), (17, 0.9, "door")]),
            ((0, 8, 20, 8, INT), [(3.5, 0.9, "door"), (8.5, 0.9, "door"), (11.5, 1.2, "opening"),
                                  (14, 0.9, "door"), (17.5, 0.9, "door")]),
            ((7, 8, 7, 12, INT), []),
            ((10, 8, 10, 12, INT), []),
            ((13, 8, 13, 12, INT), []),
            ((15, 8, 15, 12, INT), []),
        ],
        "rooms": [("Reception", 0, 0, 8, 6), ("Office 1", 8, 0, 14, 6), ("Office 2", 14, 0, 20, 6),
                  ("Corridor", 0, 6, 20, 8), ("Meeting", 0, 8, 7, 12), ("Toilets", 7, 8, 10, 12),
                  ("Stair", 10, 8, 13, 12), ("Store", 13, 8, 15, 12), ("Kitchen", 15, 8, 20, 12)],
    },
    "First floor": {
        "walls": [
            ((0, 0, 20, 0, EXT), [(4, 1.5, "window"), (11, 1.5, "window"), (17, 1.5, "window")]),
            ((20, 0, 20, 12, EXT), [(3, 1.2, "window"), (10, 1.2, "window")]),
            ((20, 12, 0, 12, EXT), [(3.5, 1.2, "window"), (16.5, 1.5, "window")]),
            ((0, 12, 0, 0, EXT), [(2, 1.2, "window"), (9, 1.2, "window")]),
            ((10, 0, 10, 6, INT), []),
            ((0, 6, 20, 6, INT), [(5, 0.9, "door"), (15, 0.9, "door")]),
            ((0, 8, 20, 8, INT), [(3.5, 0.9, "door"), (11.5, 1.2, "opening"), (16, 0.9, "door")]),
            ((7, 8, 7, 12, INT), []),
            ((10, 8, 10, 12, INT), []),
            ((13, 8, 13, 12, INT), []),
        ],
        "rooms": [("Office 3", 0, 0, 10, 6), ("Office 4", 10, 0, 20, 6), ("Corridor", 0, 6, 20, 8),
                  ("Boardroom", 0, 8, 7, 12), ("Toilets", 7, 8, 10, 12), ("Stair", 10, 8, 13, 12),
                  ("Open Office", 13, 8, 20, 12)],
    },
}


def truth(level: str) -> dict:
    """Net room areas (inside the walls) and opening counts, for scoring."""
    lv = LEVELS[level]
    walls = [w for w, _ in lv["walls"]]

    def net(name, x0, y0, x1, y1):
        # Shrink each side by half the thickness of the wall on it (or 0 if open).
        def half(x, y, vertical):
            for (ax, ay, bx, by, t) in walls:
                if vertical and ax == bx == x and min(ay, by) <= y <= max(ay, by):
                    return t / 2
                if not vertical and ay == by == y and min(ax, bx) <= x <= max(ax, bx):
                    return t / 2
            return 0.0
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        w = (x1 - x0) - half(x0, cy, True) - half(x1, cy, True)
        h = (y1 - y0) - half(cx, y0, False) - half(cx, y1, False)
        return round(w * h, 2)

    kinds = {}
    for _, ops in lv["walls"]:
        for _, _, k in ops:
            kinds[k] = kinds.get(k, 0) + 1
    return {"rooms": {r[0]: net(*r) for r in lv["rooms"]}, "openings": kinds}


def _pieces(level):
    """Wall rectangles with the openings cut out, and the openings themselves."""
    pieces, openings = [], []
    for (x1, y1, x2, y2, t), ops in LEVELS[level]["walls"]:
        L = math.hypot(x2 - x1, y2 - y1)
        ux, uy = (x2 - x1) / L, (y2 - y1) / L
        nx, ny = -uy, ux
        # Extend walls by half the outer thickness so corners close.
        cuts = sorted((d - w / 2, d + w / 2, k, w, d) for d, w, k in ops)
        # Outside walls run past their ends to close the corners; inside walls
        # stop at the centre of the wall they meet, as drawn.
        ext = EXT / 2 if t == EXT else 0.0
        start = -ext
        for a, b, k, w, d in cuts:
            pieces.append((x1, y1, ux, uy, nx, ny, t, start, a))
            openings.append({"kind": k, "x": x1 + ux * d, "y": y1 + uy * d, "ux": ux, "uy": uy,
                             "nx": nx, "ny": ny, "w": w, "t": t})
            start = b
        pieces.append((x1, y1, ux, uy, nx, ny, t, start, L + ext))
    rects = []
    for x1, y1, ux, uy, nx, ny, t, a, b in pieces:
        if b - a < 1e-6:
            continue
        p = lambda s, o: (x1 + ux * s + nx * o, y1 + uy * s + ny * o)  # noqa: E731
        rects.append([p(a, -t / 2), p(b, -t / 2), p(b, t / 2), p(a, t / 2)])
    return rects, openings


def build_dxf(level: str) -> bytes:
    import ezdxf
    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = 4                  # millimetres
    for name in ("A-WALL", "A-DOOR", "A-GLAZ", "A-ANNO-TEXT", "A-FURN", "A-DIMS"):
        doc.layers.add(name)
    door = doc.blocks.new("DOOR-SINGLE")
    door.add_line((0, 0), (0, 1000), dxfattribs={"layer": "0"})
    door.add_arc((0, 0), 1000, 0, 90, dxfattribs={"layer": "0"})
    win = doc.blocks.new("WINDOW-3L")
    for off in (-0.25, 0, 0.25):
        win.add_line((-500, off * 1000 * 0.4), (500, off * 1000 * 0.4), dxfattribs={"layer": "0"})
    m = doc.modelspace()
    mm = lambda v: v * 1000  # noqa: E731
    rects, openings = _pieces(level)
    for r in rects:
        m.add_lwpolyline([(mm(x), mm(y)) for x, y in r], close=True, dxfattribs={"layer": "A-WALL"})
    for o in openings:
        ang = math.degrees(math.atan2(o["uy"], o["ux"]))
        if o["kind"] == "door":
            # Hinge at one jamb, leaf swinging to the inside normal.
            hx, hy = o["x"] - o["ux"] * o["w"] / 2, o["y"] - o["uy"] * o["w"] / 2
            m.add_blockref("DOOR-SINGLE", (mm(hx), mm(hy)), dxfattribs={
                "layer": "A-DOOR", "rotation": ang - 90, "xscale": o["w"], "yscale": o["w"]}).dxf.rotation = ang
        elif o["kind"] == "window":
            m.add_blockref("WINDOW-3L", (mm(o["x"]), mm(o["y"])), dxfattribs={
                "layer": "A-GLAZ", "rotation": ang, "xscale": o["w"], "yscale": o["t"] / 0.1 * 0.25})
    for name, x0, y0, x1, y1 in LEVELS[level]["rooms"]:
        m.add_text(name.upper(), height=250, dxfattribs={"layer": "A-ANNO-TEXT"}).set_placement(
            (mm((x0 + x1) / 2), mm((y0 + y1) / 2)), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
        if name.startswith("Office"):
            for i in range(2):
                cx, cy = x0 + 1.5 + i * 2.2, y0 + 1.5
                m.add_lwpolyline([(mm(cx), mm(cy)), (mm(cx + 1.6), mm(cy)), (mm(cx + 1.6), mm(cy + 0.8)),
                                  (mm(cx), mm(cy + 0.8))], close=True, dxfattribs={"layer": "A-FURN"})
    m.add_line((0, -1500), (20000, -1500), dxfattribs={"layer": "A-DIMS"})
    m.add_text("20000", height=200, dxfattribs={"layer": "A-DIMS"}).set_placement((10000, -1300))
    s = io.StringIO()
    doc.write(s)
    return s.getvalue().encode()


def build_pdf(levels: list[str]) -> bytes:
    from reportlab.lib.pagesizes import A3, landscape
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(A3))
    pw, ph = landscape(A3)
    k = 72 / 25.4 * 1000 / 100              # 1:100: metres to points
    for level in levels:
        ox, oy = 60, 120
        P = lambda x, y: (ox + x * k, oy + y * k)  # noqa: E731
        c.setLineWidth(1.6)
        c.rect(20, 20, pw - 40, ph - 40)                     # sheet border
        c.setLineWidth(0.6)
        c.rect(pw - 300, 20, 280, 110)                       # title block
        c.setFont("Helvetica-Bold", 12)
        c.drawString(pw - 290, 100, "SPT DEMO OFFICE")
        c.setFont("Helvetica", 9)
        c.drawString(pw - 290, 82, f"{level.upper()} PLAN")
        c.drawString(pw - 290, 64, "SCALE 1:100 @ A3")
        c.drawString(pw - 290, 46, "DRG No. A-10" + str(levels.index(level) + 1))
        rects, openings = _pieces(level)
        c.setFillGray(0)
        for r in rects:
            path = c.beginPath()
            path.moveTo(*P(*r[0]))
            for pt in r[1:]:
                path.lineTo(*P(*pt))
            path.close()
            c.drawPath(path, stroke=0, fill=1)
        c.setLineWidth(0.35)
        for o in openings:
            if o["kind"] == "door":
                hx, hy = o["x"] - o["ux"] * o["w"] / 2, o["y"] - o["uy"] * o["w"] / 2
                tx, ty = hx + o["nx"] * o["w"], hy + o["ny"] * o["w"]
                c.line(*P(hx, hy), *P(tx, ty))
                a0 = math.degrees(math.atan2(o["uy"], o["ux"]))
                cx, cy = P(hx, hy)
                r = o["w"] * k
                c.arc(cx - r, cy - r, cx + r, cy + r, startAng=a0, extent=90)
            elif o["kind"] == "window":
                for off in (-0.3, 0, 0.3):
                    a = (o["x"] - o["ux"] * o["w"] / 2 + o["nx"] * o["t"] * off,
                         o["y"] - o["uy"] * o["w"] / 2 + o["ny"] * o["t"] * off)
                    b = (a[0] + o["ux"] * o["w"], a[1] + o["uy"] * o["w"])
                    c.line(*P(*a), *P(*b))
        c.setFont("Helvetica", 8)
        for name, x0, y0, x1, y1 in LEVELS[level]["rooms"]:
            x, y = P((x0 + x1) / 2, (y0 + y1) / 2)
            c.drawCentredString(x, y - 3, name.upper())
            if name.startswith("Office"):
                for i in range(2):
                    c.rect(*P(x0 + 1.5 + i * 2.2, y0 + 1.5), 1.6 * k, 0.8 * k)
        # A detail at another scale, which must not be taken for the building.
        c.rect(pw - 300, ph - 200, 120, 90)
        c.drawString(pw - 300, ph - 215, "DETAIL 1  SCALE 1:20")
        c.line(*P(0, -1.5), *P(20, -1.5))
        c.drawCentredString(*P(10, -1.3), "20000")
        c.showPage()
    c.save()
    return buf.getvalue()


def build_scan(pdf: bytes, page: int = 1, dpi: int = 150) -> bytes:
    """The sheet printed, scanned crooked, with blur and speckle, saved as JPEG."""
    import numpy as np
    import pypdfium2 as pdfium
    from PIL import Image, ImageFilter

    img = pdfium.PdfDocument(pdf)[page - 1].render(scale=dpi / 72, grayscale=True).to_pil().convert("L")
    img = img.rotate(0.6, resample=Image.BICUBIC, fillcolor=255, expand=False)
    img = img.filter(ImageFilter.GaussianBlur(0.8))
    a = np.asarray(img).astype(np.int16)
    rng = np.random.default_rng(7)
    a = a + rng.normal(0, 14, a.shape).astype(np.int16)
    speck = rng.random(a.shape) < 0.0015
    a[speck] = 40
    a = np.clip(a * 0.92 + 18, 0, 255).astype(np.uint8)       # grey paper
    out = io.BytesIO()
    Image.fromarray(a).save(out, "JPEG", quality=70, dpi=(dpi, dpi))
    return out.getvalue()


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out.mkdir(parents=True, exist_ok=True)
    names = list(LEVELS)
    for i, name in enumerate(names):
        (out / f"plan-L{i}.dxf").write_bytes(build_dxf(name))
    pdf = build_pdf(names)
    (out / "plans.pdf").write_bytes(pdf)
    (out / "plan-L0-scan.jpg").write_bytes(build_scan(pdf, 1))
    print("wrote", sorted(p.name for p in out.iterdir()))
