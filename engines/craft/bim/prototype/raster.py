"""Binary-image operations the prototype pipeline needs, on numpy alone.

scipy and OpenCV would do all of this, but scipy is a large addition to the
engine image for five functions, and OpenCV's wheels bundle FFmpeg (LGPL),
which the licence policy refuses. Each function here is the textbook method,
written for speed with whole-array numpy operations:

* dilation and erosion by a square, with the van Herk / Gil-Werman running
  max, so the cost does not grow with the kernel;
* connected components by run-length labelling — a plan has a few thousand
  runs per row band, where it has millions of pixels;
* outlines by following pixel edges, then Douglas-Peucker simplification.

Masks are bool arrays indexed [row, col]; row 0 is the top of the image.
"""
from __future__ import annotations

import numpy as np


# -- morphology ------------------------------------------------------------------

def _running_max(a: np.ndarray, k: int, axis: int) -> np.ndarray:
    """Max over a centred window of k cells along one axis (van Herk)."""
    if k <= 1:
        return a.copy()
    a = np.moveaxis(a, axis, -1)
    n = a.shape[-1]
    left = k // 2
    pad_hi = (-(n + k - 1)) % k + (k - 1 - left)
    padded = np.pad(a, [(0, 0)] * (a.ndim - 1) + [(left, pad_hi)], constant_values=False)
    m = padded.shape[-1]
    blocks = padded.reshape(a.shape[:-1] + (m // k, k))
    pre = np.maximum.accumulate(blocks, axis=-1).reshape(a.shape[:-1] + (m,))
    suf = np.flip(np.maximum.accumulate(np.flip(blocks, -1), axis=-1), -1).reshape(a.shape[:-1] + (m,))
    out = np.maximum(suf[..., :m - k + 1], pre[..., k - 1:])[..., :n]
    return np.moveaxis(out, -1, axis)


def _odd(k: int) -> int:
    # An even square has no centre; erosion and dilation would then be offset
    # by a pixel from each other.
    return int(k) | 1


def dilate(mask: np.ndarray, k: int) -> np.ndarray:
    """Dilate by a k x k square (k rounded up to odd)."""
    k = _odd(k)
    if k <= 1:
        return mask.copy()
    return _running_max(_running_max(mask, k, 0), k, 1)


def erode(mask: np.ndarray, k: int) -> np.ndarray:
    """Erode by a k x k square (k rounded up to odd). Outside counts as background."""
    k = _odd(k)
    if k <= 1:
        return mask.copy()
    return ~dilate(~mask, k) & _inner(mask.shape, k)


def _inner(shape, k):
    m = np.zeros(shape, dtype=bool)
    lo, hi = k // 2, k - 1 - k // 2
    m[lo:shape[0] - hi, lo:shape[1] - hi] = True
    return m


def opening(mask: np.ndarray, k: int) -> np.ndarray:
    """Keep only what a k x k square fits inside: removes strokes thinner than k."""
    return dilate(erode(mask, k), k) & mask if k > 1 else mask.copy()


def closing(mask: np.ndarray, k: int) -> np.ndarray:
    """Fill gaps narrower than k."""
    if k <= 1:
        return mask.copy()
    pad = k
    p = np.pad(mask, pad, constant_values=False)
    return erode(dilate(p, k), k)[pad:-pad, pad:-pad] | mask


# -- connected components -------------------------------------------------------

def label(mask: np.ndarray, connectivity: int = 4) -> tuple[np.ndarray, int]:
    """Label 4- or 8-connected components. Returns (labels, count); 0 is background."""
    h, w = mask.shape
    padded = np.zeros((h, w + 2), dtype=np.int8)
    padded[:, 1:-1] = mask
    d = np.diff(padded, axis=1)
    sy, sx = np.nonzero(d == 1)          # run starts (inclusive)
    ey, ex = np.nonzero(d == -1)         # run ends (exclusive)
    n = len(sy)
    if n == 0:
        return np.zeros((h, w), dtype=np.int32), 0
    parent = np.arange(n)

    def find(i):
        root = i
        while parent[root] != root:
            root = parent[root]
        while parent[i] != root:
            parent[i], i = root, parent[i]
        return root

    row_start = np.searchsorted(sy, np.arange(h + 1))
    slack = 1 if connectivity == 8 else 0
    sxl, exl = sx.tolist(), ex.tolist()
    for y in range(h - 1):
        a0, a1 = row_start[y], row_start[y + 1]
        b0, b1 = row_start[y + 1], row_start[y + 2]
        i, j = a0, b0
        while i < a1 and j < b1:
            if sxl[i] < exl[j] + slack and sxl[j] < exl[i] + slack:
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[max(ri, rj)] = min(ri, rj)
            if exl[i] < exl[j]:
                i += 1
            else:
                j += 1
    roots = np.array([find(i) for i in range(n)])
    uniq, compact = np.unique(roots, return_inverse=True)
    labels = np.zeros((h, w), dtype=np.int32)
    lab = (compact + 1).tolist()
    syl = sy.tolist()
    for i in range(n):
        labels[syl[i], sxl[i]:exl[i]] = lab[i]
    return labels, len(uniq)


def touching_border(labels: np.ndarray) -> set[int]:
    edge = np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]])
    return set(np.unique(edge[edge > 0]).tolist())


def fill_holes(mask: np.ndarray) -> np.ndarray:
    """The mask plus every background region not connected to the border."""
    lab, _ = label(~mask)
    outside = np.isin(lab, list(touching_border(lab)))
    return ~outside


def otsu(gray: np.ndarray) -> float:
    hist = np.bincount(gray.ravel().astype(np.int64), minlength=256)[:256].astype(np.float64)
    total = hist.sum()
    if total == 0:
        return 128.0
    omega = np.cumsum(hist) / total
    mu = np.cumsum(hist * np.arange(256)) / total
    with np.errstate(divide="ignore", invalid="ignore"):
        between = (mu[-1] * omega - mu) ** 2 / (omega * (1 - omega))
    if not np.isfinite(between).any():
        return 128.0                    # a blank page: one grey level, nothing to split
    return float(np.nanargmax(np.where(np.isfinite(between), between, np.nan)))


# -- outlines ---------------------------------------------------------------------

def outlines(mask: np.ndarray) -> list[list[tuple[int, int]]]:
    """Closed outlines of a mask along pixel edges, as (x, y) grid-corner loops.

    Outer boundaries run counter-clockwise and holes clockwise in image axes
    (y down). Diagonal pinches are resolved so loops never cross.
    """
    h, w = mask.shape
    m = np.zeros((h + 2, w + 2), dtype=bool)
    m[1:-1, 1:-1] = mask
    nxt: dict[tuple[int, int], list[tuple[int, int]]] = {}
    # Horizontal edges between rows r-1 and r (grid y = r - 1 in mask coords).
    dv = m[1:, :] != m[:-1, :]
    ys, xs = np.nonzero(dv)
    for r, c in zip(ys.tolist(), xs.tolist()):
        below = m[r + 1, c]           # pixel under the edge is inside
        x, y = c - 1, r
        if below:                     # inside below: walk right->left? keep inside on the left
            a, b = (x + 1, y), (x, y)
        else:
            a, b = (x, y), (x + 1, y)
        nxt.setdefault(a, []).append(b)
    dh = m[:, 1:] != m[:, :-1]
    ys, xs = np.nonzero(dh)
    for r, c in zip(ys.tolist(), xs.tolist()):
        right = m[r, c + 1]
        x, y = c, r - 1
        if right:
            a, b = (x, y), (x, y + 1)
        else:
            a, b = (x, y + 1), (x, y)
        nxt.setdefault(a, []).append(b)

    loops = []
    while nxt:
        start = next(iter(nxt))
        loop = [start]
        cur, prev_dir = start, None
        while True:
            outs = nxt.get(cur)
            if not outs:
                break
            if len(outs) == 1 or prev_dir is None:
                b = outs.pop(0)
            else:
                # Pinch: turn left, keeping regions that touch only at a corner apart.
                left = (prev_dir[1], -prev_dir[0])
                pick = next((o for o in outs if (o[0] - cur[0], o[1] - cur[1]) == left), outs[0])
                outs.remove(pick)
                b = pick
            if not outs:
                del nxt[cur]
            prev_dir = (b[0] - cur[0], b[1] - cur[1])
            if b == start:
                break
            loop.append(b)
            cur = b
        if len(loop) >= 4:
            loops.append(_collinear_out(loop))
    return loops


def _collinear_out(loop):
    out = []
    n = len(loop)
    for i in range(n):
        a, b, c = loop[i - 1], loop[i], loop[(i + 1) % n]
        if (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]) != 0:
            out.append(b)
    return out


def signed_area(poly) -> float:
    s = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        s += x1 * y2 - x2 * y1
    return s / 2


def simplify(poly, eps: float):
    """Douglas-Peucker on a closed loop."""
    if len(poly) < 5 or eps <= 0:
        return [(float(p[0]), float(p[1])) for p in poly]
    pts = np.asarray(poly, dtype=float)
    # Start from the two points furthest apart so the loop splits well.
    i0 = 0
    i1 = int(np.argmax(((pts - pts[0]) ** 2).sum(1)))
    a = _dp(pts[i0:i1 + 1], eps)
    b = _dp(np.vstack([pts[i1:], pts[:1]]), eps)
    out = [(float(p[0]), float(p[1])) for p in a[:-1]] + [(float(p[0]), float(p[1])) for p in b[:-1]]
    return out if len(out) >= 3 else [(float(p[0]), float(p[1])) for p in pts]


def _dp(pts: np.ndarray, eps: float) -> np.ndarray:
    keep = np.zeros(len(pts), dtype=bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        s, e = stack.pop()
        if e <= s + 1:
            continue
        a, b = pts[s], pts[e]
        seg = b - a
        L = np.hypot(*seg)
        rel = pts[s + 1:e] - a
        d = np.abs(seg[0] * rel[:, 1] - seg[1] * rel[:, 0]) / L if L > 1e-12 else np.hypot(rel[:, 0], rel[:, 1])
        k = int(np.argmax(d))
        if d[k] > eps:
            keep[s + 1 + k] = True
            stack += [(s, s + 1 + k), (s + 1 + k, e)]
    return pts[keep]


def polygons(mask: np.ndarray, eps: float = 1.5, min_area: float = 4.0) -> list[dict]:
    """Outlines grouped into polygons with holes, simplified, in grid units."""
    loops = [l for l in outlines(mask) if abs(signed_area(l)) >= min_area]
    # In image axes (y down) the walk keeps the inside on the right, which is
    # a negative signed area for outer boundaries.
    outers = [l for l in loops if signed_area(l) < 0]
    holes = [l for l in loops if signed_area(l) > 0]
    polys = [{"outer": o, "holes": []} for o in outers]
    for hole in holes:
        hx, hy = hole[0]
        best = None
        for p in polys:
            if point_in(hx + 0.5, hy + 0.5, p["outer"]) or point_in(hx, hy, p["outer"]):
                if best is None or abs(signed_area(p["outer"])) < abs(signed_area(best["outer"])):
                    best = p
        if best is not None:
            best["holes"].append(hole)
    for p in polys:
        p["outer"] = simplify(p["outer"], eps)
        p["holes"] = [simplify(h, eps) for h in p["holes"]]
    return polys


def point_in(x: float, y: float, poly) -> bool:
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-30) + xi:
            inside = not inside
        j = i
    return inside
