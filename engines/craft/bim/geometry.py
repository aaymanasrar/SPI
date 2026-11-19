"""The little geometry the BIM tools need: where an element's insertion point
is, and the plan footprint of anything modelled as an extrusion.

Deliberately not a geometry kernel. Rooms, walls, columns and slabs come out of
Revit as profiles extruded vertically, and a footprint plus a height is enough to
show them and to test a point against them. Anything else — boolean cuts, breps,
sloped extrusions, swept or revolved solids — is reported as having no
footprint rather than approximated, because a wrong outline in a coverage check
is worse than a missing one.

Frames are (R, o): a 3x3 rotation (columns are the local axes in world terms)
and an origin. A local point p maps to o + R·p.
"""
from __future__ import annotations

import math

from .model import IfcModel, PLACEMENT, _number
from .step import Entity, Ref

Frame = tuple[tuple, tuple]
IDENTITY: Frame = (((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)), (0.0, 0.0, 0.0))

# Representation identifiers in the order they are tried.
BODY_FIRST = ("Body", "Facetation", None)
ARC_SEGMENTS = 72      # 5° per chord: under 0.1 % area error on a room-sized arc


def apply(frame: Frame, p: tuple) -> tuple:
    r, o = frame
    return tuple(o[i] + sum(r[i][j] * p[j] for j in range(3)) for i in range(3))


def compose(outer: Frame, inner: Frame) -> Frame:
    r, o = outer
    ri, oi = inner
    rot = tuple(tuple(sum(r[i][k] * ri[k][j] for k in range(3)) for j in range(3))
                for i in range(3))
    return rot, apply(outer, oi)


def _point(model: IfcModel, ref) -> tuple | None:
    e = model.step.get(ref)
    if e is None or not isinstance(e.arg(0), list):
        return None
    nums = [float(v) for v in e.arg(0) if isinstance(v, (int, float))]
    return tuple((nums + [0.0, 0.0, 0.0])[:3]) if nums else None


def _frame(model: IfcModel, ref) -> Frame | None:
    """An IfcAxis2Placement as a frame. Unset means identity."""
    if ref is None:
        return IDENTITY
    placed = model._axis_placement(model.step.get(ref))
    return placed


def _operator_frame(model: IfcModel, op: Entity | None) -> tuple[Frame, float] | None:
    """IfcCartesianTransformationOperator(3D): (frame, uniform scale)."""
    if op is None or not op.type.startswith("IFCCARTESIANTRANSFORMATIONOPERATOR"):
        return None
    origin = _point(model, op.arg(2)) or (0.0, 0.0, 0.0)
    scale = _number(op.arg(3)) or 1.0

    def axis(ref, default):
        d = _point(model, ref)
        if d is None:
            return default
        n = math.sqrt(sum(c * c for c in d)) or 1.0
        return tuple(c / n for c in d)

    x = axis(op.arg(0), (1.0, 0.0, 0.0))
    y = axis(op.arg(1), (0.0, 1.0, 0.0))
    z = axis(op.arg(4), (0.0, 0.0, 1.0)) if len(op.args) > 4 else (0.0, 0.0, 1.0)
    rot = tuple((x[i], y[i], z[i]) for i in range(3))
    return (rot, origin), scale


def representation_items(model: IfcModel, product: Entity) -> list[Entity]:
    """The items of the product's body representation (Body preferred)."""
    shape = model.step.get(product.arg(6))
    if shape is None or not isinstance(shape.arg(2), list):
        return []
    reps = [model.step.get(r) for r in shape.arg(2)]
    reps = [r for r in reps if r is not None and r.type == "IFCSHAPEREPRESENTATION"]
    for wanted in BODY_FIRST:
        for rep in reps:
            ident = rep.arg(1)
            if wanted is None or ident == wanted:
                items = [model.step.get(i) for i in (rep.arg(3) or [])]
                items = [i for i in items if i is not None]
                if items:
                    return items
    return []


def _resolve_item(model: IfcModel, item: Entity, depth: int = 0) -> tuple[Entity, Frame] | None:
    """Follow mapped items and boolean results down to the solid that carries
    the geometry, accumulating the transforms on the way."""
    if depth > 16:
        return None
    if item.type == "IFCMAPPEDITEM":
        source = model.step.get(item.arg(0))
        target = _operator_frame(model, model.step.get(item.arg(1)))
        if source is None or source.type != "IFCREPRESENTATIONMAP" or target is None:
            return None
        (target_frame, _scale) = target
        origin = _frame(model, source.arg(0))
        mapped = model.step.get(source.arg(1))
        if origin is None or mapped is None or not mapped.arg(3):
            return None
        inner = model.step.get(mapped.arg(3)[0])
        if inner is None:
            return None
        found = _resolve_item(model, inner, depth + 1)
        if found is None:
            return None
        solid, frame = found
        # Geometry is defined relative to the mapping origin, then placed by the
        # target: target ∘ origin⁻¹ ∘ frame.
        ro, oo = origin
        inv = (tuple(tuple(ro[j][i] for j in range(3)) for i in range(3)),
               tuple(-sum(ro[j][i] * oo[j] for j in range(3)) for i in range(3)))
        return solid, compose(target_frame, compose(inv, frame))
    if item.type in ("IFCBOOLEANCLIPPINGRESULT", "IFCBOOLEANRESULT"):
        first = model.step.get(item.arg(1))
        return _resolve_item(model, first, depth + 1) if first is not None else None
    return item, IDENTITY


def anchor(model: IfcModel, product: Entity) -> tuple | None:
    """The insertion point of the body geometry, in the product's local frame.
    Used when an exporter left the placement at the origin and baked the
    location into the geometry, which Revit does for some families."""
    for item in representation_items(model, product):
        found = _resolve_item(model, item)
        if found is None:
            continue
        solid, frame = found
        if solid.type in ("IFCEXTRUDEDAREASOLID", "IFCREVOLVEDAREASOLID",
                          "IFCEXTRUDEDAREASOLIDTAPERED"):
            local = _frame(model, solid.arg(1))
            if local is not None:
                full = compose(frame, local)
                point = (0.0, 0.0, 0.0)
                if all(abs(c) < 1e-9 for c in local[1]):
                    # One level further down: the profile itself drawn at the
                    # element's location. Its centroid is the best anchor.
                    pts = _profile_points(model, model.step.get(solid.arg(0)))
                    if pts:
                        point = (sum(p[0] for p in pts) / len(pts),
                                 sum(p[1] for p in pts) / len(pts), 0.0)
                return apply(full, point)
        return apply(frame, (0.0, 0.0, 0.0))
    return None


# -- profiles ----------------------------------------------------------------

def _curve_points(model: IfcModel, ref, depth: int = 0) -> list[tuple] | None:
    """A closed 2D curve as points, or None when it uses something not read."""
    curve = model.step.get(ref)
    if curve is None or depth > 8:
        return None
    t = curve.type
    if t == "IFCPOLYLINE":
        pts = [_point(model, p) for p in (curve.arg(0) or [])]
        return None if any(p is None for p in pts) else pts
    if t == "IFCINDEXEDPOLYCURVE":
        plist = model.step.get(curve.arg(0))
        coords = plist.arg(0) if plist is not None else None
        if not isinstance(coords, list):
            return None
        table = [tuple((list(map(float, c)) + [0.0, 0.0, 0.0])[:3]) for c in coords
                 if isinstance(c, list)]
        segments = curve.arg(1)
        if not segments:
            return table
        out: list[tuple] = []
        for seg in segments:
            idx = getattr(seg, "value", None)
            idx = idx if isinstance(idx, list) else [idx]
            try:
                pts = [table[int(i) - 1] for i in idx]
            except (IndexError, TypeError, ValueError):
                return None
            if getattr(seg, "type", "") == "IFCARCINDEX" and len(pts) == 3:
                pts = _arc_through(*pts)
            out.extend(pts if not out else pts[1:])
        return out
    if t == "IFCCOMPOSITECURVE":
        out = []
        for seg_ref in curve.arg(0) or []:
            seg = model.step.get(seg_ref)
            if seg is None:
                return None
            pts = _curve_points(model, seg.arg(2), depth + 1)
            if pts is None:
                return None
            if str(seg.arg(1)).upper() in ("F", "FALSE", ".F."):
                pts = list(reversed(pts))
            out.extend(pts if not out else pts[1:])
        return out
    if t == "IFCTRIMMEDCURVE":
        return _trimmed(model, curve)
    return None


def _trimmed(model: IfcModel, curve: Entity) -> list[tuple] | None:
    basis = model.step.get(curve.arg(0))
    if basis is None:
        return None

    def trim_point(trims):
        for t in trims or []:
            if isinstance(t, Ref):
                return _point(model, t)
        return None

    def trim_param(trims):
        for t in trims or []:
            n = _number(t)
            if n is not None:
                return n
        return None

    sense = str(curve.arg(3)).upper() not in ("F", "FALSE")
    if basis.type == "IFCLINE":
        a, b = trim_point(curve.arg(1)), trim_point(curve.arg(2))
        if a is None or b is None:
            origin = _point(model, basis.arg(0))
            vec = model.step.get(basis.arg(1))
            direction = _point(model, vec.arg(0)) if vec else None
            magnitude = _number(vec.arg(1)) if vec else None
            p1, p2 = trim_param(curve.arg(1)), trim_param(curve.arg(2))
            if None in (origin, direction, magnitude, p1, p2):
                return None
            a = tuple(origin[i] + direction[i] * magnitude * p1 for i in range(3))
            b = tuple(origin[i] + direction[i] * magnitude * p2 for i in range(3))
        return [a, b] if sense else [b, a]
    if basis.type == "IFCCIRCLE":
        frame = _frame(model, basis.arg(0))
        radius = _number(basis.arg(1))
        if frame is None or radius is None:
            return None
        p1, p2 = trim_param(curve.arg(1)), trim_param(curve.arg(2))
        if p1 is None or p2 is None:
            a, b = trim_point(curve.arg(1)), trim_point(curve.arg(2))
            if a is None or b is None:
                return None
            r, o = frame
            local = lambda p: tuple(sum(r[j][i] * (p[j] - o[j]) for j in range(3)) for i in range(3))  # noqa: E731
            la, lb = local(a), local(b)
            p1, p2 = math.atan2(la[1], la[0]), math.atan2(lb[1], lb[0])
        else:
            # Parameter trims are in the model's plane angle unit. Revit writes
            # radians; a value beyond 2π can only be degrees.
            if max(abs(p1), abs(p2)) > 2 * math.pi + 1e-6:
                p1, p2 = math.radians(p1), math.radians(p2)
        if sense:
            while p2 <= p1:
                p2 += 2 * math.pi
        else:
            while p2 >= p1:
                p2 -= 2 * math.pi
        steps = max(2, int(ARC_SEGMENTS * abs(p2 - p1) / (2 * math.pi)) + 1)
        return [apply(frame, (radius * math.cos(p1 + (p2 - p1) * k / steps),
                              radius * math.sin(p1 + (p2 - p1) * k / steps), 0.0))
                for k in range(steps + 1)]
    return None


def _arc_through(a: tuple, b: tuple, c: tuple) -> list[tuple]:
    """Points along the circular arc a→b→c (2D, z carried from a)."""
    ax, ay, bx, by, cx, cy = a[0], a[1], b[0], b[1], c[0], c[1]
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return [a, b, c]
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay)
          + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx)
          + (cx * cx + cy * cy) * (bx - ax)) / d
    r = math.hypot(ax - ux, ay - uy)
    t1, t2, t3 = (math.atan2(p[1] - uy, p[0] - ux) for p in (a, b, c))
    ccw = ((bx - ax) * (cy - ay) - (by - ay) * (cx - ax)) > 0
    if ccw:
        while t3 <= t1:
            t3 += 2 * math.pi
    else:
        while t3 >= t1:
            t3 -= 2 * math.pi
    steps = max(2, int(ARC_SEGMENTS * abs(t3 - t1) / (2 * math.pi)) + 1)
    return [(ux + r * math.cos(t1 + (t3 - t1) * k / steps),
             uy + r * math.sin(t1 + (t3 - t1) * k / steps), a[2]) for k in range(steps + 1)]


def _profile_points(model: IfcModel, profile: Entity | None) -> list[tuple] | None:
    if profile is None:
        return None
    if profile.type in ("IFCARBITRARYCLOSEDPROFILEDEF", "IFCARBITRARYPROFILEDEFWITHVOIDS"):
        return _curve_points(model, profile.arg(2))      # outer boundary only
    if profile.type in ("IFCRECTANGLEPROFILEDEF", "IFCROUNDEDRECTANGLEPROFILEDEF",
                        "IFCRECTANGLEHOLLOWPROFILEDEF"):
        frame = _frame(model, profile.arg(2))
        x, y = _number(profile.arg(3)), _number(profile.arg(4))
        if frame is None or x is None or y is None:
            return None
        return [apply(frame, (sx * x / 2, sy * y / 2, 0.0))
                for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    if profile.type == "IFCCIRCLEPROFILEDEF":
        frame = _frame(model, profile.arg(2))
        r = _number(profile.arg(3))
        if frame is None or r is None:
            return None
        return [apply(frame, (r * math.cos(2 * math.pi * k / ARC_SEGMENTS),
                              r * math.sin(2 * math.pi * k / ARC_SEGMENTS), 0.0))
                for k in range(ARC_SEGMENTS)]
    return None


def footprint(model: IfcModel, product: Entity, world: Frame) -> dict | None:
    """Plan outline (world XY), base level and height of a vertically extruded
    product, in model length units. None when the body is anything else."""
    for item in representation_items(model, product):
        found = _resolve_item(model, item)
        if found is None:
            continue
        solid, frame = found
        if solid.type != "IFCEXTRUDEDAREASOLID":
            continue
        local = _frame(model, solid.arg(1))
        direction = _point(model, solid.arg(2))
        depth = _number(solid.arg(3))
        pts = _profile_points(model, model.step.get(solid.arg(0)))
        if local is None or direction is None or depth is None or not pts:
            continue
        full = compose(world, compose(frame, local))
        # Only a vertical extrusion has a plan footprint.
        n = math.sqrt(sum(c * c for c in direction)) or 1.0
        dz_local = tuple(c / n for c in direction)
        dz = tuple(sum(full[0][i][j] * dz_local[j] for j in range(3)) for i in range(3))
        if abs(abs(dz[2]) - 1.0) > 1e-3:
            continue
        world_pts = [apply(full, p) for p in pts]
        if len(world_pts) > 1 and math.dist(world_pts[0][:2], world_pts[-1][:2]) < 1e-9:
            world_pts = world_pts[:-1]
        if len(world_pts) < 3:
            continue
        base = min(p[2] for p in world_pts)
        height = depth * dz[2]
        if height < 0:
            base, height = base + height, -height
        return {"points": [(p[0], p[1]) for p in world_pts], "base": base, "height": height}
    return None


def polygon_area(points: list[tuple]) -> float:
    s = 0.0
    for i in range(len(points)):
        x1, y1 = points[i][0], points[i][1]
        x2, y2 = points[(i + 1) % len(points)][0], points[(i + 1) % len(points)][1]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


def world_frame(model: IfcModel, product: Entity) -> Frame | None:
    return model._world(product.arg(PLACEMENT), 0)
