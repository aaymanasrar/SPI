"""BIMCraft: a 3D prototype of a building from its floor plans.

Reads one floor plan per level — DXF, PDF or a scanned image — and proposes
the building it describes: walls with their real thickness, door and window
openings, rooms with names, the slab outline, a roof. It is a prototype: a
plan has no heights in it, so every height is an assumption, recorded as one
and shown as one, and anything traced from pixels is a proposal for review.

How a plan becomes a building:

1. Walls are the thick strokes. On a DXF they are the wall layers; on a PDF or
   scan they are what survives removing every stroke thinner than ~70 mm,
   which takes text, dimensions, furniture and door swings with it.
2. The building is the largest cluster of walls; sheet frames, title blocks
   and other views on the same sheet are dropped and reported.
3. Openings are two wall ends facing each other across a door-sized gap. What
   kind is decided by evidence: a door or window block on a DXF, a swing arc
   beside the gap, glazing lines inside it, and which side is outdoors.
4. Rooms are the enclosed spaces once openings are closed, named by the text
   inside them.
"""
from __future__ import annotations

import math
import re
import time

import numpy as np
from PIL import Image, ImageDraw
from pydantic import BaseModel, Field

from ...core import (ENGINE_VERSION, Assumption, Finding, InvalidInput, Provenance,
                     Storage, ToolResult, register)
from . import raster as R
from .sources import Plan, load

# -- prototype heights: assumptions, never facts ------------------------------------
DEFAULTS = {
    "storey_height_m": (3.6, "floor-to-floor typical of an office building"),
    "ceiling_height_m": (3.0, "a finished ceiling typical of an office"),
    "slab_thickness_m": (0.25, "a typical reinforced concrete floor slab"),
    "door_head_m": (2.1, "a standard door height"),
    "window_sill_m": (0.9, "a typical office sill"),
    "window_head_m": (2.1, "window heads aligned with door heads"),
    "parapet_height_m": (1.1, "a guarded flat roof"),
}
ASSUMED_WALL_M = 0.2          # thickness used when a plan's walls are single lines
ASSUMED_DOOR_M = 0.9          # door width used when only the doors can give a scale

ROOM_TYPES = [
    ("stair", r"stair|staircase|\bstr\b|escalier|درج"),
    ("lift", r"\blift\b|elevator|ascenseur|مصعد"),
    ("toilet", r"toilet|\bwc\b|w\.c|lavatory|washroom|restroom|bath|shower|\bgents?\b|ladies|حمام|دورة"),
    ("kitchen", r"kitchen|pantry|kitchenette|tea|مطبخ"),
    ("meeting", r"meeting|conference|board|seminar|اجتماع"),
    ("office", r"office|manager|admin|work|study|مكتب"),
    ("open_office", r"open.?(plan|office)|workspace|cowork"),
    ("reception", r"reception|lobby|foyer|entrance|waiting|استقبال"),
    ("corridor", r"corridor|passage|hall(way)?|circulation|ممر"),
    ("classroom", r"class|school|lab|lecture|فصل"),
    ("store", r"store|storage|archive|\bstr\.?\b|cleaner|janitor|مخزن"),
    ("server", r"server|\bit\b|comms|data|\bmdf\b|\bidf\b|خوادم"),
    ("plant", r"plant|mech|elec|electrical|ups|\bmep\b|pump|generator|riser|كهرباء"),
    ("bedroom", r"bed(room)?|sleep|غرفة نوم"),
    ("living", r"living|lounge|majlis|family|sitting|مجلس"),
    ("dining", r"dining"),
    ("prayer", r"prayer|musall|مصلى"),
]


class LevelSource(BaseModel):
    document_id: str
    storage_key: str
    name: str | None = Field(None, description="level name, e.g. 'Ground Floor'")
    page: int = Field(1, ge=1, description="PDF page holding this level's plan")
    elevation_m: float | None = Field(None, description="finished floor level; default stacks the levels")
    scale: str | None = Field(None, description="drawing scale, e.g. '1:100' (PDF, or image with dpi)")
    dpi: float | None = Field(None, gt=0, description="scan resolution, for an image with a scale")
    metres_per_unit: float | None = Field(None, gt=0, description="DXF without units: metres per drawing unit; image: metres per pixel")
    known_length_m: float | None = Field(None, gt=0, description="the building's overall length west to east, as dimensioned on the drawing — calibrates a plan with no scale")
    wall_layers: list[str] | None = None
    door_layers: list[str] | None = None
    window_layers: list[str] | None = None


class PrototypeInput(BaseModel):
    document_id: str
    name: str | None = Field(None, description="building name")
    levels: list[LevelSource] = Field(min_length=1, max_length=40, description="lowest level first")
    storey_height_m: float | None = Field(None, gt=1.5, lt=20)
    ceiling_height_m: float | None = Field(None, gt=1.5, lt=20)
    slab_thickness_m: float | None = Field(None, gt=0, lt=2)
    door_head_m: float | None = Field(None, gt=1, lt=10)
    window_sill_m: float | None = Field(None, ge=0, lt=10)
    window_head_m: float | None = Field(None, gt=0.5, lt=20)
    parapet_height_m: float | None = Field(None, ge=0, lt=5)
    heights_verified_from: str | None = Field(
        None, description="the section or elevation the supplied heights were read from")
    device_rules: dict | None = Field(
        None, description="rules to propose an ELV layout with, as data from the rules "
                          "library — see prototype/devices.py. Omitted: no devices proposed.")


# -- one level ------------------------------------------------------------------------

def _rect_mask(shape, poly):
    img = Image.new("1", (shape[1], shape[0]), 0)
    if len(poly) >= 3:
        ImageDraw.Draw(img).polygon([(float(x), float(y)) for x, y in poly], fill=1)
    return np.array(img, dtype=bool)


def _stroke_scan(ink: np.ndarray) -> int:
    """The dominant wall thickness in pixels, from how strokes survive ever
    larger squares: thin lines (text, dimensions, hatching) are gone within a
    few pixels; walls survive until the square is about as wide as they are."""
    base = R.opening(ink, 3).sum()
    if base == 0:
        return 3
    lo, hi = 3, 81                       # survives at lo; assume gone by hi
    if R.opening(ink, hi).sum() >= 0.35 * base:
        return hi
    while hi - lo > 2:
        mid = ((lo + hi) // 2) | 1
        if mid in (lo, hi):
            break
        if R.opening(ink, mid).sum() >= 0.35 * base:
            lo = mid
        else:
            hi = mid
    return max(3, lo)


def _walls(plan: Plan, res: float, notes: list[str], assumptions: list[dict]) -> np.ndarray:
    px = lambda m: max(1, int(round(m / res)))  # noqa: E731
    if plan.walls_hint is not None and plan.walls_hint.sum() > 50:
        W = R.closing(plan.walls_hint, px(0.40))        # double wall lines -> solid
        thick = R.opening(W, max(3, px(0.06)))
        if thick.sum() < 0.35 * max(1, W.sum()):
            W = R.dilate(plan.walls_hint, px(ASSUMED_WALL_M))
            assumptions.append({"key": "wall_thickness_m", "value": ASSUMED_WALL_M,
                                "basis": "walls are drawn as single lines, which have no thickness",
                                "verify_from": "the wall types in the specification"})
            notes.append("walls drawn as single lines; given an assumed thickness")
        else:
            W = thick
        return W
    return _search_walls(plan, notes)


def _block_min(a: np.ndarray, f: int) -> np.ndarray:
    """Shrink by f, keeping the darkest pixel of each block so thin lines survive."""
    if f <= 1:
        return a
    h, w = (a.shape[0] // f) * f, (a.shape[1] // f) * f
    return a[:h, :w].reshape(h // f, f, w // f, f).min(axis=(1, 3))


def _enclosed_score(W: np.ndarray, T_ref: float) -> float:
    """How well a wall reading divides the plan into rooms.

    The right reading encloses each room separately. Reading too little loses
    inner walls and merges rooms; reading too much (furniture, filled rooms,
    text) chops rooms into cells or fills them. Summing the square root of each
    room-sized area rewards division into rooms without rewarding slivers.
    """
    # Rooms are measured inside the building's hull, so one wide entrance
    # cannot leak the whole interior to the outside and score nothing.
    hull = R.fill_holes(R.closing(W, max(3, int(14 * T_ref))))
    B = R.closing(W, max(3, int(5 * T_ref)))
    inside = hull & ~B
    lab, n = R.label(inside, 4)
    if not n:
        return 0.0
    sizes = np.bincount(lab.ravel())[1:]
    rooms = sizes[sizes >= (8 * T_ref) ** 2]
    return float(np.sqrt(rooms).sum())


def _search_walls(plan: Plan, notes: list[str]) -> np.ndarray:
    """Read the walls of a raster plan in three explainable steps.

    1. Threshold: start at the page's own dark/light split and step darker only
       while the reading is implausible — too much of the page is ink, or the
       "strokes" are as thick as rooms (a plan with colour-filled rooms).
    2. Hatching: fill between lines only when the plain reading is hollow —
       walls drawn as outlines or hatching leave almost no solid stroke, where
       filling finds plenty. Solid walls are never filled, which keeps the
       glazing lines of a window from closing its gap.
    3. Strokes: keep those at least a third as thick as the dominant wall,
       because inner walls are often half or a third of outer ones.
    """
    gray = plan.gray
    size = gray.size if gray is not None else plan.ink.size
    f = max(1, int(math.ceil(math.sqrt(size / 2.5e6))))
    if gray is None:
        inks = [(None, plan.ink)]
    else:
        t0 = min(225, int(R.otsu(gray)) + 10)
        inks = [(t, gray < t) for t in [t0] + [t for t in (190, 160, 130, 100) if t < t0]]
    chosen = None
    for t, ink in inks:
        small = _block_min((~ink).astype(np.uint8), f) == 0
        frac = float(small.mean())
        if frac > 0.30 or frac < 0.002:
            continue
        T = _stroke_scan(small)
        if T > 0.04 * min(small.shape):
            continue                          # rooms filled with colour read as ink
        chosen = (t, ink, small)
        break
    if chosen is None:
        t, ink = inks[0]
        small = _block_min((~ink).astype(np.uint8), f) == 0
        notes.append("the plan's linework could not be separated cleanly; walls are a best guess")
    else:
        t, ink, small = chosen
    solid = int(R.opening(small, 3).sum())
    filled = int(R.opening(R.closing(small, 5), 5).sum())
    hatched = solid < 0.25 * max(filled, 1)

    def read(fill: bool) -> np.ndarray:
        m = R.closing(ink, 5 * f) if fill else ink
        T_full = _stroke_scan(m)
        return R.closing(R.opening(m, max(3, int(T_full * 0.35) | 1)), 3)

    W = read(hatched)
    T_est = max(3, _stroke_scan(W))
    if _enclosed_score(W, T_est) == 0:
        other = read(not hatched)
        if _enclosed_score(other, max(3, _stroke_scan(other))) > 0:
            W, hatched = other, not hatched
    if hatched:
        notes.append("walls are drawn hatched or as outlines; their lines were filled")
    plan.ink_used = ink
    return W


def _main_cluster(W: np.ndarray, res: float, notes: list[str]) -> np.ndarray:
    k = max(3, int(round(2.5 / res)))
    lab, n = R.label(R.closing(W, k), 8)
    if n <= 1:
        return W
    h, w = W.shape
    best, best_area, others = 0, 0, 0
    for i in range(1, n + 1):
        rows, cols = np.nonzero(lab == i)
        bh, bw = _ptp(rows) + 1, _ptp(cols) + 1
        frame = bw > 0.92 * w or bh > 0.92 * h
        area = int((W & (lab == i)).sum())
        if area * res * res < 0.5:
            continue
        if frame:
            notes.append("a sheet border was ignored")
            continue
        others += 1
        if bh * bw > best_area:
            best, best_area = i, bh * bw
    if best == 0:
        return W
    if others > 1:
        notes.append(f"{others - 1} other drawing(s) on the sheet ignored (title block, details, other views)")
    return W & (lab == best)


def _cross(a, b) -> float:
    return float(a[0] * b[1] - a[1] * b[0])


def _ptp(a) -> int:
    return int(a.max() - a.min()) if len(a) else 0


def _edges(polys):
    """Outline edges, with near-straight runs merged: a pixel jog left by
    anti-aliasing splits a wall end in two, and neither half then looks like one."""
    out = []
    straight = math.cos(math.radians(25))
    for poly in polys:
        for ring in [poly["outer"]] + poly["holes"]:
            pts = [np.array(p, float) for p in ring]
            n = len(pts)
            if n < 3:
                continue
            # Start at a real corner so a merged run never wraps the seam.
            def turn(i):
                a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
                u, v = b - a, c - b
                lu, lv = np.hypot(*u), np.hypot(*v)
                return 1.0 if lu < 1e-9 or lv < 1e-9 else float(np.dot(u, v) / (lu * lv))
            corners = [i for i in range(n) if turn(i) < straight]
            if not corners:
                continue
            for k, i in enumerate(corners):
                j = corners[(k + 1) % len(corners)]
                p, q = pts[i], pts[j]
                d = q - p
                L = float(np.hypot(*d))
                if L < 1e-9:
                    continue
                out.append({"p": p, "q": q, "mid": (p + q) / 2, "dir": d / L, "len": L})
    return out


def _openings(W, polys, res, T):
    """Pairs of wall end faces across a door-sized gap."""
    edges = _edges(polys)
    h, w = W.shape

    def solid(pt):
        x, y = int(pt[0]), int(pt[1])
        return 0 <= x < w and 0 <= y < h and W[y, x]

    for e in edges:
        n = np.array([e["dir"][1], -e["dir"][0]])
        probe = e["mid"] + n * 1.5
        if solid(probe):
            n = -n
        e["n"] = n
    def backed(e):
        # A jamb has wall behind it; a jagged stub or a pixel step does not.
        probes = [e["mid"] - e["n"] * T * s for s in (0.6, 1.0, 1.5, 2.0)]
        return sum(solid(p) for p in probes) >= 3

    ends = [e for e in edges if 0.45 * T <= e["len"] <= 2.0 * T and backed(e)]
    dmin, dmax, dside = 0.5 / res, 2.6 / res, 1.35 / res
    best = {}
    for i, e in enumerate(ends):
        for j, f in enumerate(ends):
            if i == j or float(np.dot(e["n"], f["n"])) > -0.85:
                continue
            v = f["mid"] - e["mid"]
            along = float(np.dot(v, e["n"]))
            lateral = abs(_cross(e["n"], v))
            if dmin <= along <= dmax and lateral < 0.6 * T:
                if i not in best or along < best[i][1]:
                    best[i] = (j, along)
    pairs, used = [], set()
    for i, (j, d) in best.items():
        if best.get(j, (None,))[0] == i and i not in used and j not in used:
            used |= {i, j}
            pairs.append((ends[i], ends[j], d))
    out = []
    for e, f, d in pairs:
        steps = np.linspace(0.15, 0.85, 12)
        if sum(solid(e["mid"] + e["n"] * d * s) for s in steps) > 3:
            continue
        a, b = e["p"], e["q"]
        c = f["p"] if np.linalg.norm(f["p"] - b) < np.linalg.norm(f["q"] - b) else f["q"]
        dd = f["q"] if c is f["p"] else f["p"]
        out.append({"quad": [a, b, c, dd], "axis": e["n"], "width": d,
                    "thick": (e["len"] + f["len"]) / 2, "center": (e["mid"] + f["mid"]) / 2})
    # A wall end facing the side of another wall across a single-door gap.
    taken = {id(e) for e, f, _ in pairs} | {id(f) for e, f, _ in pairs}
    sides = [x for x in edges if x["len"] > 2.0 * T]
    for e in ends:
        if id(e) in taken:
            continue
        hit = None
        for f in sides:
            if float(np.dot(e["n"], f["n"])) > -0.9:
                continue
            t = float(np.dot(f["mid"] - e["mid"], e["n"]))
            if not (dmin <= t <= dside):
                continue
            proj = e["mid"] + e["n"] * t
            u = float(np.dot(proj - f["p"], f["dir"]))
            if 0.2 * T < u < f["len"] - 0.2 * T and (hit is None or t < hit[1]):
                hit = (f, t)
        if hit:
            t = hit[1]
            if sum(solid(e["mid"] + e["n"] * t * s) for s in np.linspace(0.15, 0.85, 10)) > 2:
                continue
            a, b = e["p"], e["q"]
            out.append({"quad": [a, b, b + e["n"] * t, a + e["n"] * t], "axis": e["n"], "width": t,
                        "thick": e["len"], "center": e["mid"] + e["n"] * t / 2})
    return out


def _classify(op, plan, W_thin, F, Wfull, res, marks):
    h, w = F.shape
    axis = op["axis"]
    perp = np.array([-axis[1], axis[0]])
    L = op["width"]

    def inside(pt, m):
        x, y = int(round(pt[0])), int(round(pt[1]))
        return 0 <= x < w and 0 <= y < h and bool(m[y, x])

    reach = op["thick"] * 0.5 + max(3, 0.3 / res)
    side_a = op["center"] + perp * reach
    side_b = op["center"] - perp * reach
    exterior = (not inside(side_a, F)) or (not inside(side_b, F))

    quad_mask = _rect_mask(W_thin.shape, op["quad"])
    glaze = float((W_thin & quad_mask).sum()) / max(L, 1)

    # A door swing is ink along a quarter circle, radius the opening width,
    # hinged at one jamb. Straight clutter — dimension lines, desks — crosses
    # such an arc at a point or two, so the share of the arc that is inked
    # tells a swing from everything else.
    near = R.dilate(W_thin, max(5, int(round(0.04 / res)) * 2 + 1))
    best_arc, hinge_side = 0.0, None
    ja, jb = op["center"] - axis * L / 2, op["center"] + axis * L / 2
    thetas = np.radians(np.linspace(12, 78, 23))
    # The hinge is drawn either at the wall face or on the wall's centre line.
    for hinge, along in ((ja, axis), (jb, -axis)):
        for side in (1, -1):
            for offset in (op["thick"] / 2, 0.0):
                hits = sum(inside(hinge + L * (math.cos(t) * along + math.sin(t) * side * perp)
                                  + side * perp * offset, near) for t in thetas)
                frac = hits / len(thetas)
                if frac > best_arc:
                    best_arc, hinge_side = frac, side

    kind, evidence, leaf, swing_side = None, None, False, None
    best = None
    for m in marks:
        d = math.hypot(m["col"] - op["center"][0], m["row"] - op["center"][1])
        if d < max(1.0 / res, L) and (best is None or d < best[0]):
            best = (d, m)
    if best:
        kind, evidence = best[1]["kind"], f"{best[1]['kind']} block {best[1].get('block', '')}".strip()
        leaf = kind == "door"
        swing_side = hinge_side if leaf else None
    # Glazing lines inside the gap are the stronger sign: a doorway is empty.
    # Only a near-complete arc overrides them.
    if kind is None and glaze >= 1.4 and best_arc < 0.85:
        kind, evidence = "window", "glazing lines drawn in the opening"
    if kind is None and best_arc >= 0.6:
        kind, evidence, leaf, swing_side = "door", "door swing drawn beside the opening", True, hinge_side
    if kind is None:
        kind = "window" if exterior else "opening"
        evidence = "no symbol: " + ("an opening in an outside wall" if exterior else "an opening in an inside wall")
    return {"kind": kind, "exterior": exterior, "evidence": evidence, "leaf": leaf,
            "swing_side": swing_side, "glaze": glaze}


def _thin_outline(plan: Plan, W: np.ndarray, F: np.ndarray, res: float):
    """A closed thin outline around the walls, when the walls themselves do not
    reach the building edge: a curtain wall or a slab edge drawn as a line."""
    if plan.kind == "dxf":
        return None
    ink = plan.ink | W
    closed = R.fill_holes(R.closing(ink, 3))
    lab, n = R.label(closed, 4)
    if not n:
        return None
    h, w = W.shape
    wall_px = int(W.sum())
    best = None
    for i in np.unique(lab[W]):
        if i == 0:
            continue
        m = lab == i
        ys, xs = np.nonzero(m)
        if _ptp(xs) > 0.92 * w or _ptp(ys) > 0.92 * h:
            continue                         # the sheet border
        if (W & m).sum() < 0.8 * wall_px:
            continue
        if best is None or m.sum() > best.sum():
            best = m
    if best is None or best.sum() < 1.3 * F.sum():
        return None
    return best | F


def _name_room(texts):
    """A room's number and name from the text inside it."""
    number, names = None, []
    for t in texts:
        s = t.strip()
        if not s or len(s) > 60:
            continue
        if re.fullmatch(r"[A-Za-z]{0,3}[-.]?\d{1,4}[A-Za-z]?", s) and number is None:
            number = s
            continue
        if re.search(r"\d+(\.\d+)?\s*(m2|m²|sqm|sq\.?\s?m|mm|m\b)", s, re.I):
            continue                       # an area or dimension, not a name
        if re.fullmatch(r"[\d\s.,x×/+-]+", s):
            continue
        letters = sum(ch.isalpha() for ch in s)
        if letters >= 2:
            names.append(s)
    name = " ".join(dict.fromkeys(names))[:60] if names else None
    return number, name


def _room_type(name: str | None) -> str:
    if not name:
        return "room"
    for t, pat in ROOM_TYPES:
        if re.search(pat, name, re.I):
            return t
    return "room"


def analyse(plan: Plan, src: LevelSource) -> dict:
    notes = list(plan.notes)
    assumptions = list(plan.assumptions)
    res = plan.res
    provisional = res is None
    W = _walls(plan, res, notes, assumptions)
    if provisional:
        # Provisional only, settled below. Measured on the walls actually read,
        # not on all the ink: a plan with colour-filled rooms has "strokes" as
        # thick as its rooms.
        res = ASSUMED_WALL_M / max(3, _stroke_scan(W))
    W = _main_cluster(W, res, notes)
    lab, n = R.label(W, 8)
    if n:
        sizes = np.bincount(lab.ravel())
        keep = sizes >= max(4, 0.03 / (res * res))
        # Lettering filled in by hatch filling: small and only partly inked.
        ink = plan.ink_used if plan.ink_used is not None else plan.ink
        inked = np.bincount(lab.ravel(), weights=ink.ravel().astype(np.float64), minlength=len(sizes))
        small = sizes < (0.6 / res) ** 2
        loose = inked < 0.55 * sizes
        keep &= ~(small & loose)
        keep[0] = False
        W = keep[lab]
    if W.sum() == 0:
        raise InvalidInput(f"{src.storage_key}: no walls could be found on this plan.")

    T = 3
    total = W.sum()
    for k in range(3, 99, 2):
        if R.opening(W, k).sum() < 0.5 * total:
            break
        T = k
    polys = R.polygons(W, eps=max(1.0, 0.03 / res), min_area=max(4.0, 0.02 / (res * res)))
    ops = _openings(W, polys, res, T)

    O = np.zeros_like(W)
    for op in ops:
        O |= _rect_mask(W.shape, op["quad"])
    Wc = W | R.dilate(O, 3)
    exact = R.fill_holes(Wc)
    closed = R.fill_holes(R.closing(Wc, max(3, int(round(2.5 / res)))))
    if exact.sum() >= 0.85 * closed.sum():
        F = exact
    else:
        F = closed
        notes.append("some wall gaps were not recognised as openings; the outline was closed across them")

    facade = None
    outline = _thin_outline(plan, W, F, res)
    if outline is not None:
        F = outline
        facade = "glass"
        notes.append("the building edge is drawn as a thin line (curtain wall or slab edge); "
                     "taken as the outline and shown glazed")

    W_thin = (plan.faint if plan.faint is not None else plan.ink) & ~R.dilate(W, 5)
    for op in ops:
        op.update(_classify(op, plan, W_thin, F, W, res, plan.marks))

    # Settle the scale of a plan that did not state one.
    scale_note = plan.scale_basis
    if provisional:
        ys, xs = np.nonzero(F)
        width_px = _ptp(xs) + 1 if len(xs) else 0
        door_widths = [op["width"] for op in ops if op["kind"] == "door" and not op["exterior"]]
        if src.known_length_m and width_px:
            final = src.known_length_m / width_px
            scale_note = f"calibrated: building {src.known_length_m:g} m long, as dimensioned"
        elif len(door_widths) >= 3:
            final = ASSUMED_DOOR_M / float(np.median(door_widths))
            scale_note = f"estimated from {len(door_widths)} inside doors taken as {ASSUMED_DOOR_M} m wide"
            assumptions.append({"key": "scale", "value": f"{final * 1000:.1f} mm per pixel",
                                "basis": scale_note,
                                "verify_from": "a dimension on the drawing — enter the overall length to calibrate"})
        else:
            final = ASSUMED_WALL_M / T
            scale_note = f"estimated from wall thickness taken as {ASSUMED_WALL_M} m"
            assumptions.append({"key": "scale", "value": f"{final * 1000:.1f} mm per pixel",
                                "basis": scale_note,
                                "verify_from": "a dimension on the drawing — enter the overall length to calibrate"})
        res = final

    # 4-connected, so a diagonal pixel gap in a wall cannot join two rooms; no
    # dilation, so rooms keep their full size up to the wall face.
    free = F & ~Wc
    rl, rn = R.label(free, 4)
    rooms = []
    if rn:
        sizes = np.bincount(rl.ravel())
        by_label: dict[int, list[str]] = {}
        h, w = rl.shape
        for text, col, row in plan.texts:
            c, r = int(round(col)), int(round(row))
            if 0 <= r < h and 0 <= c < w and rl[r, c]:
                by_label.setdefault(int(rl[r, c]), []).append(text)
        for i in range(1, rn + 1):
            if sizes[i] * res * res < 0.8:
                continue
            m = rl == i
            ps = R.polygons(m, eps=max(1.0, 0.03 / res), min_area=4.0)
            if not ps:
                continue
            outer = max(ps, key=lambda p: abs(R.signed_area(p["outer"])))
            number, name = _name_room(by_label.get(i, []))
            ys, xs = np.nonzero(m)
            aspect = (max(_ptp(xs), _ptp(ys)) + 1) / (min(_ptp(xs), _ptp(ys)) + 1)
            rtype = _room_type(name)
            if rtype == "room" and not name and aspect > 4.5:
                rtype = "corridor"
            rooms.append({"poly": outer, "area_px": int(sizes[i]), "number": number,
                          "name": name, "type": rtype, "named": bool(name or number)})

    return {"W": W, "polys": polys, "ops": ops, "F": F, "rooms": rooms, "res": res, "facade": facade,
            "T": T, "plan": plan, "notes": notes, "assumptions": assumptions,
            "scale": scale_note}


# -- the building ----------------------------------------------------------------------

def _to_world(pt, a):
    plan = a["plan"]
    return [round(plan.x0 + float(pt[0]) * a["res"] + a["dx"], 3),
            round(plan.y_top - float(pt[1]) * a["res"] + a["dy"], 3)]


def _ring(ring, a):
    pts = [_to_world(p, a) for p in ring]
    # Image axes flip the winding; store outer rings counter-clockwise in world axes.
    s = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))
    return pts if s > 0 else pts[::-1]


def _hole(ring, a):
    return _ring(ring, a)[::-1]


@register("bim.prototype", "bim", PrototypeInput,
          "Propose a 3D building from its floor plans (DXF, PDF or scanned image): walls, "
          "doors, windows, rooms, slabs and roof, with every assumed height recorded",
          modes=("preview",))
def prototype(data: PrototypeInput, storage: Storage | None = None) -> ToolResult:
    started = time.perf_counter()
    res = ToolResult(tool="bim.prototype", engine_version=ENGINE_VERSION)
    if storage is None:
        raise InvalidInput("bim.prototype needs storage to fetch the drawings")

    # Heights: supplied with a source, or assumed and said to be.
    H = {}
    for key, (value, why) in DEFAULTS.items():
        given = getattr(data, key)
        if given is not None:
            H[key] = given
            res.assumptions.append(Assumption(
                key=key, value=given, unit="m",
                basis=f"supplied{' from ' + data.heights_verified_from if data.heights_verified_from else ''}",
                status="verified" if data.heights_verified_from else "assumed",
                verify_from=data.heights_verified_from or "the building sections"))
        else:
            H[key] = value
            res.assumptions.append(Assumption(
                key=key, value=value, unit="m", basis=f"not on a floor plan; {why}",
                verify_from="the building sections and elevations"))
    if H["window_head_m"] <= H["window_sill_m"]:
        raise InvalidInput("window head must be above the window sill")

    analysed = []
    for i, src in enumerate(data.levels):
        raw = storage.read(src.storage_key)
        plan = load(raw, src.storage_key, page=src.page, scale=src.scale,
                    metres_per_unit=src.metres_per_unit, dpi=src.dpi,
                    wall_layers=src.wall_layers, door_layers=src.door_layers,
                    window_layers=src.window_layers)
        a = analyse(plan, src)
        a["src"] = src
        ordinals = ["Ground", "First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth", "Ninth"]
        a["name"] = src.name or (f"{ordinals[i]} floor" if i < len(ordinals) else f"Level {i}")
        analysed.append(a)

    # Levels drawn on different sheets do not share coordinates. DXFs do; the
    # rest are stacked on the centre of their outlines.
    all_world = all(a["plan"].world_aligned for a in analysed)
    ref = None
    for a in analysed:
        a["dx"] = a["dy"] = 0.0
        ys, xs = np.nonzero(a["F"])
        cx = a["plan"].x0 + (xs.min() + xs.max()) / 2 * a["res"]
        cy = a["plan"].y_top - (ys.min() + ys.max()) / 2 * a["res"]
        if all_world:
            continue
        if ref is None:
            ref = (cx, cy)
            a["dx"], a["dy"] = -cx, -cy
        else:
            a["dx"], a["dy"] = -cx, -cy
    if not all_world and len(analysed) > 1:
        res.findings.append(Finding(
            code="LEVELS-ALIGNED-BY-CENTRE", severity="review", subject=f"document:{data.document_id}",
            detail="The levels come from separate sheets with no shared coordinates, so each is "
                   "centred on its own outline. Levels with different outlines may sit offset.",
            action="Check the stacking against a grid line, or submit DXF plans that share coordinates."))

    levels, spaces, storeys, xs_all, ys_all = [], [], [], [], []
    elevation = 0.0
    wall_h = H["storey_height_m"] - H["slab_thickness_m"]
    for li, a in enumerate(analysed):
        src = a["src"]
        z = src.elevation_m if src.elevation_m is not None else elevation
        elevation = z + H["storey_height_m"]
        name = a["name"]
        storeys.append({"global_id": None, "name": name, "elevation_m": round(z, 3)})
        walls = [{"outer": _ring(p["outer"], a), "holes": [_hole(hh, a) for hh in p["holes"]]} for p in a["polys"]]
        fp = R.polygons(a["F"], eps=max(1.0, 0.05 / a["res"]), min_area=16.0)
        footprint = [{"outer": _ring(p["outer"], a), "holes": [_hole(hh, a) for hh in p["holes"]]} for p in fp]
        openings = []
        for op in a["ops"]:
            axis = op["axis"]
            angle = math.degrees(math.atan2(-axis[1], axis[0]))     # y flips into world axes
            kind = op["kind"]
            sill = H["window_sill_m"] if kind == "window" else 0.0
            head = H["window_head_m"] if kind == "window" else H["door_head_m"]
            openings.append({
                "kind": kind, "exterior": op["exterior"], "evidence": op["evidence"],
                "leaf": op["leaf"], "swing_side": op["swing_side"],
                "center": _to_world(op["center"], a), "angle_deg": round(angle, 2),
                "width_m": round(op["width"] * a["res"], 3), "thickness_m": round(op["thick"] * a["res"], 3),
                "sill_m": sill, "head_m": head})
        for p in footprint:
            for x, y in p["outer"]:
                xs_all.append(x), ys_all.append(y)
        unnamed = 0
        for ri, r in enumerate(a["rooms"]):
            poly = _ring(r["poly"]["outer"], a)
            area = round(r["area_px"] * a["res"] ** 2, 2)
            label = " ".join(x for x in (r["number"], r["name"]) if x) or f"{r['type'].replace('_', ' ').title()} {ri + 1}"
            unnamed += not r["named"]
            spaces.append({
                "id": f"L{li}-R{ri + 1}", "number": r["number"], "name": r["name"] or label,
                "label": label, "storey": name, "type": r["type"],
                "footprint_m": poly, "base_z_m": round(z, 3), "height_m": H["ceiling_height_m"],
                "area_m2": area, "area_source": "measured inside the traced walls",
                "outline_area_m2": area})
        counts = {}
        for o in openings:
            counts[o["kind"]] = counts.get(o["kind"], 0) + 1
        levels.append({
            "name": name, "elevation_m": round(z, 3), "wall_height_m": round(wall_h, 3),
            "ceiling_height_m": H["ceiling_height_m"], "slab_thickness_m": H["slab_thickness_m"],
            "footprint": footprint, "walls": walls, "openings": openings, "facade": a["facade"],
            "stairs": [s["id"] for s in spaces if s["storey"] == name and s["type"] == "stair"],
            "source": {"document_id": src.document_id, "file": src.storage_key, "kind": a["plan"].kind,
                       "scale": a["scale"], "wall_thickness_m": round(a["T"] * a["res"], 3),
                       "notes": a["notes"]},
            "counts": {"rooms": len(a["rooms"]), **counts}})
        for item in a["assumptions"]:
            res.assumptions.append(Assumption(key=f"{name}: {item['key']}", value=item["value"],
                                              basis=item["basis"], verify_from=item["verify_from"]))
        res.provenance.append(Provenance(value_ref=f"level:{name}",
                                         source=f"{src.storage_key} ({a['plan'].kind}; scale {a['scale']})"))
        if unnamed and a["plan"].texts:
            res.findings.append(Finding(
                code="ROOMS-UNNAMED", severity="info", subject=f"level:{name}",
                detail=f"{unnamed} room(s) on {name} had no readable name inside them and are named by type.",
                action="Check the names against the drawing."))

    devices, device_counts = [], {}
    if data.device_rules:
        from .devices import DeviceRules, propose
        devices, device_counts = propose(levels, spaces, DeviceRules.model_validate(data.device_rules))
        if devices:
            res.findings.append(Finding(
                code="DEVICES-PROPOSED", severity="review", subject=f"document:{data.document_id}",
                detail=f"{len(devices)} devices proposed from the rules library ("
                       + ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in sorted(device_counts.items()))
                       + "). None is in the drawings: each is a proposal with its rule.",
                action="Review the layout; cameras and access points are not proposed, as the "
                       "library has no placement rule for them."))
            for d in devices:
                res.provenance.append(Provenance(value_ref=f"device:{d['id']}", source=f"rule {d['rule']}"))

    top = levels[-1]
    roof = {"z": round(top["elevation_m"] + H["storey_height_m"], 3), "footprint": top["footprint"],
            "slab_thickness_m": H["slab_thickness_m"], "parapet_height_m": H["parapet_height_m"],
            "parapet_thickness_m": 0.2}
    zs = [0.0, roof["z"] + H["parapet_height_m"]]
    project = data.name or "Building prototype"
    res.outputs = {
        "model": {"schema": "prototype", "authoring_application": "SPI prototype from floor plans",
                  "is_revit_export": False, "project": project, "project_long_name": project,
                  "source": ", ".join(l.storage_key for l in data.levels)},
        "units": {"length": "metre", "metres_per_unit": 1.0},
        "storeys": storeys, "spaces": spaces, "devices": devices, "context": [],
        "systems": sorted({d["system"] for d in devices}),
        "counts": [{"system": next(d["system"] for d in devices if d["device_type"] == k),
                    "device_type": k, "unit": "no", "quantity": v, "proposed": True}
                   for k, v in sorted(device_counts.items())],
        "counts_by_storey": [], "unmapped_elements": [],
        "element_map": None, "context_without_outline": {},
        "building": {"levels": levels, "roof": roof, "heights": H},
        "bounds_m": {"min": [min(xs_all), min(ys_all), min(zs)], "max": [max(xs_all), max(ys_all), max(zs)]}
        if xs_all else None,
    }
    if not any(a.status == "verified" for a in res.assumptions):
        res.findings.append(Finding(
            code="PROTOTYPE-HEIGHTS-ASSUMED", severity="review", subject=f"document:{data.document_id}",
            detail="A floor plan has no heights. Storey, ceiling, door, window and parapet heights "
                   "are typical values, so the massing is indicative.",
            action="Enter the heights from the sections to make the model match the design."))
    for lv in levels:
        if lv["counts"].get("rooms", 0) == 0:
            res.findings.append(Finding(
                code="NO-ROOMS", severity="review", subject=f"level:{lv['name']}",
                detail=f"No enclosed rooms were found on {lv['name']}; the walls may not close.",
                action="Check the plan is a floor plan and its walls are drawn closed."))
    res.duration_ms = int((time.perf_counter() - started) * 1000)
    return res
