"""Propose an ELV device layout for a prototype, rule by rule.

Every position here is a PROPOSAL computed from a rule that is passed in as
data — the spacing, the distance from an exit, the mounting band — so this file
holds no engineering value of its own, exactly as cad.place_devices holds none.
Each device carries the rule code and the arithmetic that placed it.

What is proposed, and on what basis:

* smoke detectors — a grid at the rule's spacing, no further than its wall
  distance from any wall, then checked point by point against the coverage
  radius and topped up where a point is not reached;
* manual call points — beside every exit door (outside doors and doors into a
  stair), on the room side, within the rule's distance;
* sounder-strobes — on the longest wall of each room, one per square of the
  rule's largest room size; corridors at the rule's end and repeat distances;
* access control — reader, exit button and door contact at outside doors and
  doors into server rooms. Which doors are controlled is a security design
  decision; these are only where a design usually starts;
* data outlets — the rule's outlets per area in work rooms, in twin positions
  along the walls.

Nothing is proposed for cameras or wireless access points: the library has no
placement rule for them, and a position with no rule behind it is a guess.
"""
from __future__ import annotations

import math

from pydantic import BaseModel, Field


class Band(BaseModel):
    rule: str
    source: str
    height_m: float = Field(description="mounting height used, within the rule's band")
    band: str = Field(description="the rule's band as written, e.g. '1.07-1.22 m AFF'")


class DeviceRules(BaseModel):
    """The rules a proposal uses, each with its citation. Any may be omitted;
    an omitted rule means that system is not proposed."""
    smoke: dict | None = Field(None, description="{rule, source, spacing_m, max_wall_distance_m, radius_m}")
    call_point: dict | None = Field(None, description="{rule, source, max_from_exit_m, height_m, band}")
    strobe: dict | None = Field(None, description="{rule, source, height_m, band, max_room_side_m, corridor_end_m, corridor_spacing_m}")
    access: dict | None = Field(None, description="{rule, source, height_m, band}")
    data_outlets: dict | None = Field(None, description="{rule, source, area_per_group_m2, outlets_per_group, height_m, height_basis}")


WORK_ROOMS = {"office", "open_office", "meeting", "classroom", "reception", "room"}
NO_NOTIFIER = {"stair", "lift", "plant", "store"}


def _inside(x, y, poly):
    inside, j = False, len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-30) + xi:
            inside = not inside
        j = i
    return inside


def _edge_dist(x, y, poly):
    best = math.inf
    for i in range(len(poly)):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % len(poly)]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy or 1e-12
        t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / L2))
        best = min(best, math.hypot(x - ax - t * dx, y - ay - t * dy))
    return best


def _room_at(x, y, rooms):
    for r in rooms:
        if _inside(x, y, r["footprint_m"]):
            return r
    return None


def _device(n, kind, system, room, x, y, z, rule, basis, yaw=0.0):
    return {
        "id": f"proposal-{n}", "system": system, "device_type": kind,
        "name": f"Proposed {kind.replace('_', ' ')} {n}", "type_name": None, "tag": None,
        "ifc_class": None, "predefined_type": None, "storey": room["storey"],
        "space": room["label"], "space_basis": "located",
        "x_m": round(x, 3), "y_m": round(y, 3), "z_m": round(z, 3), "yaw_deg": round(yaw, 1),
        "position_basis": "proposed", "proposed": True, "rule": rule, "basis": basis,
        "source_reference": f"proposed by rule {rule}",
    }


def _grid(room, spacing, wall):
    """Detector grid over the room: rows and columns no further apart than the
    spacing, the outer ones no further than the wall distance from the walls."""
    xs = [p[0] for p in room["footprint_m"]]
    ys = [p[1] for p in room["footprint_m"]]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)

    def axis(a, b):
        length = b - a
        n = max(1, math.ceil(max(length - 2 * min(wall, spacing / 2), 0) / spacing) + 1)
        if length / n > spacing:
            n = math.ceil(length / spacing)
        step = length / n
        return [a + step * (i + 0.5) for i in range(n)]

    return [(x, y) for x in axis(x0, x1) for y in axis(y0, y1)
            if _inside(x, y, room["footprint_m"])]


def _cover(room, pts, radius, step=0.5):
    """Add a detector at each sample point the coverage radius does not reach,
    until every point is reached (irregular rooms, rooms the grid missed)."""
    poly = room["footprint_m"]
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    added = []
    y = min(ys) + step / 2
    samples = []
    while y < max(ys):
        x = min(xs) + step / 2
        while x < max(xs):
            if _inside(x, y, poly):
                samples.append((x, y))
            x += step
        y += step
    for _ in range(200):
        far = [s for s in samples if all(math.hypot(s[0] - p[0], s[1] - p[1]) > radius for p in pts + added)]
        if not far:
            break
        cx = sum(s[0] for s in far) / len(far)
        cy = sum(s[1] for s in far) / len(far)
        if not _inside(cx, cy, poly):
            cx, cy = far[0]
        added.append((cx, cy))
    return added


def _beside_door(op, rooms, offset, prefer):
    """A wall point beside a door, on the side of the room `prefer` chooses."""
    a = math.radians(op["angle_deg"])
    ux, uy = math.cos(a), math.sin(a)
    px, py = -uy, ux
    cx, cy = op["center"]
    t = op["thickness_m"] / 2 + 0.06
    sides = []
    for s in (1, -1):
        room = _room_at(cx + px * s * 0.5, cy + py * s * 0.5, rooms)
        sides.append((s, room))
    pick = prefer(sides)
    if pick is None:
        return None
    s, room = pick
    x = cx + ux * (op["width_m"] / 2 + offset) + px * s * t
    y = cy + uy * (op["width_m"] / 2 + offset) + py * s * t
    return room, x, y, math.degrees(math.atan2(py * s, px * s))


def propose(levels: list[dict], spaces: list[dict], rules: DeviceRules) -> tuple[list[dict], dict]:
    devices, counts = [], {}
    n = [0]

    def add(kind, system, room, x, y, z, rule, basis, yaw=0.0):
        n[0] += 1
        devices.append(_device(n[0], kind, system, room, x, y, z, rule, basis, yaw))
        counts[kind] = counts.get(kind, 0) + 1

    for lv in levels:
        rooms = [s for s in spaces if s["storey"] == lv["name"] and s.get("footprint_m")]
        stairs = {s["id"] for s in rooms if s.get("type") == "stair"}
        ceil = lambda r: r["base_z_m"] + r["height_m"]  # noqa: E731

        if rules.smoke:
            R = rules.smoke
            for r in rooms:
                if r.get("area_m2", 99) < 1.0:
                    continue
                pts = _grid(r, R["spacing_m"], R["max_wall_distance_m"])
                if not pts:
                    xs = [p[0] for p in r["footprint_m"]]
                    ys = [p[1] for p in r["footprint_m"]]
                    pts = [((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)]
                extra = _cover(r, pts, R["radius_m"])
                for x, y in pts:
                    add("smoke_detector", "fire_alarm", r, x, y, ceil(r), R["rule"],
                        f"grid at ≤ {R['spacing_m']} m, ≤ {R['max_wall_distance_m']} m from walls ({R['source']})")
                for x, y in extra:
                    add("smoke_detector", "fire_alarm", r, x, y, ceil(r), R["rule"],
                        f"added where a point was beyond the {R['radius_m']} m coverage radius")

        exits = []
        for op in lv["openings"]:
            if op["kind"] not in ("door", "opening"):
                continue
            a = math.radians(op["angle_deg"])
            px, py = -math.sin(a), math.cos(a)
            cx, cy = op["center"]
            near = [_room_at(cx + px * s * 0.5, cy + py * s * 0.5, rooms) for s in (1, -1)]
            into_stair = any(r and r["id"] in stairs for r in near)
            if op["exterior"] or into_stair:
                exits.append((op, into_stair))

        if rules.call_point:
            R = rules.call_point
            for op, into_stair in exits:
                # On the room side: inside the building, outside the stair.
                def prefer(sides):
                    ok = [x for x in sides if x[1] and x[1]["id"] not in stairs]
                    return ok[0] if ok else None
                spot = _beside_door(op, rooms, min(0.3, R["max_from_exit_m"] / 2), prefer)
                if spot:
                    room, x, y, yaw = spot
                    add("manual_call_point", "fire_alarm", room, x, y, room["base_z_m"] + R["height_m"],
                        R["rule"], f"beside an exit door, within {R['max_from_exit_m']} m; "
                                   f"{R['height_m']} m, inside the {R['band']} band ({R['source']})", yaw)

        if rules.strobe:
            R = rules.strobe
            for r in rooms:
                if r.get("type") in NO_NOTIFIER or r.get("area_m2", 99) < 2.0:
                    continue
                poly = r["footprint_m"]
                edges = sorted(((math.dist(poly[i], poly[(i + 1) % len(poly)]), i) for i in range(len(poly))),
                               reverse=True)
                L, i = edges[0]
                a, b = poly[i], poly[(i + 1) % len(poly)]
                if r.get("type") == "corridor":
                    k = max(1, math.ceil(max(L - 2 * R["corridor_end_m"], 0) / R["corridor_spacing_m"]) + 1)
                    basis = f"corridor: ≤ {R['corridor_end_m']} m from the ends, ≤ {R['corridor_spacing_m']} m apart"
                else:
                    side = R["max_room_side_m"]
                    k = max(1, math.ceil(r.get("area_m2", L * L) / (side * side)))
                    basis = f"one per room up to {side} × {side} m"
                ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
                nx, ny = -uy, ux
                mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
                if not _inside(mx + nx * 0.2, my + ny * 0.2, poly):
                    nx, ny = -nx, -ny
                for j in range(k):
                    t = (j + 0.5) / k
                    x = a[0] + (b[0] - a[0]) * t + nx * 0.08
                    y = a[1] + (b[1] - a[1]) * t + ny * 0.08
                    add("sounder_strobe", "fire_alarm", r, x, y, r["base_z_m"] + R["height_m"], R["rule"],
                        f"{basis}; lens at {R['height_m']} m, inside the {R['band']} band ({R['source']})",
                        math.degrees(math.atan2(ny, nx)))

        if rules.access:
            R = rules.access
            controlled = []
            for op in lv["openings"]:
                if op["kind"] != "door":
                    continue
                a = math.radians(op["angle_deg"])
                px, py = -math.sin(a), math.cos(a)
                cx, cy = op["center"]
                near = [_room_at(cx + px * s * 0.5, cy + py * s * 0.5, rooms) for s in (1, -1)]
                if op["exterior"] or any(r and r.get("type") == "server" for r in near):
                    controlled.append(op)
            for op in controlled:
                def outer(sides):
                    # The reader on the approach side: outdoors, else the room that is not the server room.
                    out = [x for x in sides if x[1] is None]
                    if out:
                        inner = [x for x in sides if x[1] is not None]
                        return (out[0][0], inner[0][1]) if inner else None
                    ok = [x for x in sides if x[1] and x[1].get("type") != "server"]
                    return ok[0] if ok else None

                def inner(sides):
                    # The egress side: the server room when it is one, else the building.
                    ok = [x for x in sides if x[1]]
                    srv = [x for x in ok if x[1].get("type") == "server"]
                    return (srv or ok or [None])[0]
                spot = _beside_door(op, rooms, 0.2, outer)
                if spot:
                    room, x, y, yaw = spot
                    add("card_reader", "access_control", room, x, y, room["base_z_m"] + R["height_m"], R["rule"],
                        f"latch side, approach face; {R['height_m']} m within {R['band']} ({R['source']}). "
                        "Which doors are controlled is a security design decision.", yaw)
                spot = _beside_door(op, rooms, 0.35, inner)
                if spot:
                    room, x, y, yaw = spot
                    add("exit_button", "access_control", room, x, y, room["base_z_m"] + R["height_m"],
                        R.get("exit_rule", R["rule"]), "request-to-exit on the egress side", yaw)
                    cx, cy = op["center"]
                    add("door_contact", "access_control", room, cx, cy, room["base_z_m"] + R.get("head_m", 2.1),
                        R.get("contact_rule", R["rule"]), "door position switch at the head", yaw)

        if rules.data_outlets:
            R = rules.data_outlets
            for r in rooms:
                if r.get("type") not in WORK_ROOMS or r.get("area_m2", 0) < 4:
                    continue
                groups = math.ceil(r["area_m2"] / R["area_per_group_m2"])
                poly = r["footprint_m"]
                perim = [(math.dist(poly[i], poly[(i + 1) % len(poly)]), poly[i], poly[(i + 1) % len(poly)])
                         for i in range(len(poly))]
                total = sum(p[0] for p in perim)
                for gi in range(groups):
                    d = total * (gi + 0.5) / groups
                    for L, a, b in perim:
                        if d <= L:
                            t = d / L
                            ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
                            nx, ny = -uy, ux
                            x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                            if not _inside(x + nx * 0.2, y + ny * 0.2, poly):
                                nx, ny = -nx, -ny
                            add("data_outlet", "data", r, x + nx * 0.03, y + ny * 0.03,
                                r["base_z_m"] + R["height_m"], R["rule"],
                                f"{R['outlets_per_group']} outlets per {R['area_per_group_m2']} m² ({R['source']}); "
                                f"height {R['height_m']} m — {R['height_basis']}",
                                math.degrees(math.atan2(ny, nx)))
                            break
                        d -= L
    return devices, counts
