"""What a floor plan has, next to what SPI's rules would put there.

Counted: block inserts claimed by the symbol map — the same walk as
cad.count_devices, so the numbers cannot disagree. Recommended: bim.prototype's
proposal from the rules library (bim/prototype/devices.py) — every proposed
device carries the rule and the arithmetic that placed it. Both are located in
the prototype's rooms, which for a DXF are in the drawing's own coordinates
scaled to metres.

Area-based devices (detectors, sounder-strobes, data outlets) are compared room
by room. Door-based devices (call points, readers, exit buttons, door contacts)
are compared per level: the rule puts them by an exit, which may be in the room
next door to where a designer drew one.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from ..bim.prototype import PrototypeInput, prototype
from ..cad.count import scan_inserts
from ..cad.read_dxf import open_dxf
from ..cad.rooms import point_in_polygon
from ..cad.symbols import SymbolMap, default_map
from ..cad.units import describe
from ..core import Storage

AREA_BASED = {"smoke_detector", "sounder_strobe", "data_outlet"}
DOOR_BASED = {"manual_call_point", "card_reader", "exit_button", "door_contact"}
#: Drawn detectors that answer a smoke-detection recommendation in their room.
DETECTORS = {"smoke_detector", "heat_detector", "multisensor_detector"}
#: Device types the rules library can recommend, by the rule set that does it.
RULED = {"smoke": {"smoke_detector"}, "call_point": {"manual_call_point"},
         "strobe": {"sounder_strobe"}, "access": {"card_reader", "exit_button", "door_contact"},
         "data_outlets": {"data_outlet"}}


def ruled_types(device_rules: dict | None) -> set[str]:
    out: set[str] = set()
    for k, types in RULED.items():
        if device_rules and device_rules.get(k):
            out |= types
    return out


def review_drawing(storage: Storage, document_id: str, storage_key: str,
                   symbol_map: dict | None, layers: list[str] | None,
                   device_rules: dict | None, storey_height_m: float | None = None) -> dict:
    """Counted and recommended devices per room. Raises nothing for a gap; gaps
    come back in 'missing' and 'findings' for the caller to report."""
    doc = open_dxf(storage.read(storage_key), storage_key)
    msp = doc.modelspace()
    insunits = int(doc.header.get("$INSUNITS", 0))
    unit_name, mpu = describe(insunits)
    smap = SymbolMap.load(symbol_map) if symbol_map else default_map()
    hits, unmapped = scan_inserts(msp, smap, layers)

    proto = prototype(PrototypeInput(document_id=document_id,
                                     levels=[{"document_id": document_id, "storage_key": storage_key}],
                                     storey_height_m=storey_height_m,
                                     device_rules=device_rules), storage=storage)
    po = proto.outputs or {}
    spaces = [s for s in po.get("spaces", []) if s.get("footprint_m")]
    rooms = [{"id": s["id"], "name": s.get("label") or s["id"], "type": s.get("type") or "room",
              "area_m2": s.get("area_m2"), "storey": s.get("storey"),
              "footprint_m": [tuple(p[:2]) for p in s["footprint_m"]]} for s in spaces]

    def room_at(x: float, y: float) -> dict | None:
        for r in rooms:
            if point_in_polygon(x, y, r["footprint_m"]):
                return r
        return None

    drawn: list[dict] = []
    for h in hits:
        xm, ym = (h.x * mpu, h.y * mpu) if mpu else (None, None)
        r = room_at(xm, ym) if mpu else None
        drawn.append({"system": h.rule.system, "device_type": h.rule.device_type, "block": h.block,
                      "layer": h.layer, "unit": h.rule.unit, "x_m": xm, "y_m": ym,
                      "room_id": r["id"] if r else None, "storey": r["storey"] if r else None})

    recommended: list[dict] = []
    for d in po.get("devices", []):
        if not d.get("proposed"):
            continue
        # The proposer names the room a device serves; a reader outside the
        # entrance or a contact in the door head is not inside any outline.
        r = room_at(d["x_m"], d["y_m"]) or _named(rooms, d.get("space"), d["x_m"], d["y_m"])
        recommended.append({"system": d["system"], "device_type": d["device_type"],
                            "room_id": r["id"] if r else None, "storey": d.get("storey"),
                            "x_m": d["x_m"], "y_m": d["y_m"], "z_m": d["z_m"],
                            "rule": d["rule"], "basis": d["basis"]})

    return {
        "units": {"insunits": insunits, "name": unit_name, "metres_per_unit": mpu},
        "rooms": rooms,
        "drawn": drawn,
        "recommended": recommended,
        "unmapped": [{"block": b, "layer": l, "count": n} for (b, l), n in sorted(unmapped.items())],
        "symbol_map": f"{smap.name}@{smap.version}",
        "ruled_types": sorted(ruled_types(device_rules)),
        "prototype_status": proto.status,
        "prototype_missing": [m.model_dump() for m in proto.missing],
        "prototype_findings": [f.model_dump() for f in proto.findings],
        "prototype_assumptions": [a.model_dump() for a in proto.assumptions],
    }


def _named(rooms: list[dict], label: str | None, x: float, y: float) -> dict | None:
    """The room with this label; of several, the one whose outline is nearest."""
    same = [r for r in rooms if label and r["name"] == label]
    if not same:
        return None

    def dist(r):
        xs = [p[0] for p in r["footprint_m"]]
        ys = [p[1] for p in r["footprint_m"]]
        return abs(x - min(max(x, min(xs)), max(xs))) + abs(y - min(max(y, min(ys)), max(ys)))
    return min(same, key=dist)


def compare(d: dict) -> tuple[list[dict], list[dict]]:
    """(per-room lines, per-device lines). A line has drawn and recommended
    quantities, the difference, where and why."""
    rooms = {r["id"]: r for r in d["rooms"]}
    ruled = set(d["ruled_types"])
    drawn_room: Counter = Counter()
    rec_room: Counter = Counter()
    why: dict[tuple, set] = defaultdict(set)
    for x in d["drawn"]:
        drawn_room[(x["room_id"], x["system"], x["device_type"])] += 1
    for x in d["recommended"]:
        rec_room[(x["room_id"], x["system"], x["device_type"])] += 1
        why[(x["system"], x["device_type"])].add(f"{x['rule']}: {x['basis']}")

    room_lines: list[dict] = []
    for room_id, system, dtype in sorted(set(drawn_room) | set(rec_room),
                                         key=lambda k: (rooms.get(k[0], {}).get("name") or "~", k[1], k[2])):
        if dtype in DOOR_BASED:
            continue
        n_drawn = drawn_room[(room_id, system, dtype)]
        n_rec = rec_room[(room_id, system, dtype)]
        note = None
        if dtype == "smoke_detector" and n_rec:
            other = sum(drawn_room[(room_id, "fire_alarm", t)] for t in DETECTORS - {"smoke_detector"})
            if other:
                n_drawn += other
                note = f"includes {other} heat/multisensor detector(s) drawn in this room"
        if dtype in (DETECTORS - {"smoke_detector"}) and rec_room[(room_id, "fire_alarm", "smoke_detector")]:
            continue  # counted against the smoke line above
        room = rooms.get(room_id)
        room_lines.append({
            "room_id": room_id, "room": room["name"] if room else "outside any room",
            "room_type": room["type"] if room else None,
            "area_m2": room["area_m2"] if room else None,
            "system": system, "device_type": dtype, "drawn": n_drawn,
            "recommended": n_rec if dtype in ruled else None,
            "difference": (n_drawn - n_rec) if dtype in ruled else None,
            "status": _status(n_drawn, n_rec, dtype in ruled),
            "note": note,
        })

    total_drawn: Counter = Counter((x["system"], x["device_type"]) for x in d["drawn"])
    total_rec: Counter = Counter((x["system"], x["device_type"]) for x in d["recommended"])
    unit = {(x["system"], x["device_type"]): x["unit"] for x in d["drawn"]}
    where_drawn: dict[tuple, Counter] = defaultdict(Counter)
    where_rec: dict[tuple, Counter] = defaultdict(Counter)
    for x in d["drawn"]:
        where_drawn[(x["system"], x["device_type"])][_room_name(rooms, x["room_id"])] += 1
    for x in d["recommended"]:
        where_rec[(x["system"], x["device_type"])][_room_name(rooms, x["room_id"])] += 1

    # A total can match while one room is short and another has a spare.
    short_rooms: Counter = Counter()
    for l in room_lines:
        if l["recommended"] is not None and l["drawn"] < l["recommended"]:
            short_rooms[(l["system"], l["device_type"])] += 1

    device_lines: list[dict] = []
    for key in sorted(set(total_drawn) | set(total_rec)):
        system, dtype = key
        has_rule = dtype in ruled
        nd, nr = total_drawn[key], total_rec[key]
        device_lines.append({
            "system": system, "device_type": dtype, "unit": unit.get(key, "no"),
            "drawn": nd, "recommended": nr if has_rule else None,
            "difference": (nd - nr) if has_rule else None,
            "status": _status(nd, nr, has_rule) if not (has_rule and nd == nr and short_rooms[key])
                      else f"total matches; {short_rooms[key]} room(s) short",
            "where_drawn": _where(where_drawn[key]),
            "where_recommended": _where(where_rec[key]),
            "why": " | ".join(sorted(why[key])) if has_rule else
                   "No placement rule in the library for this device: the drawn quantity stands as drawn.",
        })
    return room_lines, device_lines


def _status(drawn: int, rec: int, has_rule: bool) -> str:
    if not has_rule:
        return "no rule"
    if drawn == rec:
        return "matches"
    if drawn == 0:
        return "not drawn"
    return "fewer than recommended" if drawn < rec else "more than recommended"


def _room_name(rooms: dict, room_id: str | None) -> str:
    return rooms[room_id]["name"] if room_id in rooms else "outside any room"


def _where(c: Counter) -> str:
    return ", ".join(f"{name} ×{n}" for name, n in sorted(c.items()))
