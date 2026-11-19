#!/usr/bin/env python
"""Run the real cad.* tools over the KG floor plan and write the viewer's scene.

    cd engines && PYTHONPATH=$PWD ./.venv/bin/python fixtures/build_kg_scene.py

Writes out/walkthrough/kg.json. Nothing here invents an engineering value: the
rooms come from kg_floor_plan.py (a traced reading of the supplied drawing) and
every device position comes from a rule passed in with its citation.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kg_floor_plan import DOORS, H, ROOMS, W, WINDOWS, build_dxf   # noqa: E402

from craft.cad import (PlaceDevicesInput, RoomsInput, SpacingRule,  # noqa: E402
                       extract_rooms, place_devices)
from craft.core import LocalStorage                                 # noqa: E402

#: Generated files go to out/, which is gitignored: everything there is
#: rebuildable from this directory and viewer/.
OUT = Path(os.environ.get("SPI_OUT",
                          Path(__file__).resolve().parents[2] / "out" / "walkthrough"))

# Smoke detector spacing. Supplied here with its citation, as data -- the engine
# holds no spacing figure of its own.
DETECTOR_RULE = SpacingRule(
    rule_code="ELV-B-01", source="NFPA 72", confidence="code",
    conditions="smooth flat ceiling, no high airflow",
    max_spacing_m=9.1, max_wall_distance_m=4.6)

#: Rooms that do not take a detector. An engineering decision, so it is stated
#: here rather than inferred by the tool.
SKIP_TYPES = ("wc", "toilet", "electrical")

#: Call points go at exit doors, per SPT-FA-11.
EXIT_MARKS = {"DE", "D1", "D3"}
CALL_POINT_RULE = {
    "rule_code": "SPT-FA-11", "source": "NFPA 72 §17.15.9",
    "value_limit": "Within 1.5 m (5 ft) of each exit door; travel distance "
                   "<= 61 m (200 ft) on the same floor"}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    work = OUT / "kgwork"
    shutil.rmtree(work, ignore_errors=True)
    store = LocalStorage(work)

    dxf_path = OUT / "KG_L01.dxf"
    build_dxf(str(dxf_path))
    store.write("KG_L01.dxf", dxf_path.read_bytes())

    rooms = extract_rooms(RoomsInput(
        document_id="KG", storage_key="KG_L01.dxf",
        boundary_layers=["ROOM-BOUNDARY"], label_layers=["ROOM-NAMES"]), store)
    print(f"extract_rooms : {rooms.status} | {rooms.outputs['room_count']} rooms | "
          f"{sum(r['area_m2'] for r in rooms.outputs['rooms']):.1f} m2")

    skip = [n for n, t, *_ in ROOMS if t in SKIP_TYPES]
    det = place_devices(PlaceDevicesInput(
        document_id="KG", storage_key="KG_L01.dxf",
        boundary_layers=["ROOM-BOUNDARY"], label_layers=["ROOM-NAMES"],
        device_type="smoke_detector", system="fire_alarm",
        rule=DETECTOR_RULE, skip_rooms=skip, min_room_area_m2=2.0), store)
    print(f"place_devices : {det.status} | {det.outputs['proposed_count']} detectors "
          f"from {DETECTOR_RULE.rule_code}")

    calls = []
    for mark, x, y, _w, facing in DOORS:
        if mark not in EXIT_MARKS:
            continue
        if facing == "v":
            calls.append({"x": round(x + (0.18 if x < 1 else -0.18), 2),
                          "y": round(y + 1.2, 2)})
        else:
            calls.append({"x": round(x + 1.2, 2),
                          "y": round(y + (0.18 if y < 1 else -0.18), 2)})
    print(f"call points   : {len(calls)} from {CALL_POINT_RULE['rule_code']}")

    scene = {
        "building": {
            "name": "KG Building", "level": "Level 01",
            "width_m": W, "depth_m": H,
            "vertical_conflict":
                "West chain 23.56 m, east chain 21.40 m (differ by 2.16 m, the "
                "entrance band). West chain used. Confirm on the DXF.",
        },
        "rooms": [{"name": n, "type": t, "x0": x0, "y0": y0, "x1": x1, "y1": y1,
                   "area_m2": round((x1 - x0) * (y1 - y0), 2)}
                  for n, t, x0, y0, x1, y1 in ROOMS],
        "doors": [{"mark": m, "x": x, "y": y, "w": w, "dir": f}
                  for m, x, y, w, f in DOORS],
        "windows": [{"mark": m, "x": x, "y": y, "w": w, "dir": f}
                    for m, x, y, w, f in WINDOWS],
        "proposed_detectors": [{"x": o["geometry"]["coordinates"][0],
                                "y": o["geometry"]["coordinates"][1],
                                "room": o["extracted_value"]["room"]}
                               for o in det.outputs["objects"]],
        "proposed_call_points": calls,
        "detector_rule": det.outputs["rule"],
        "call_point_rule": CALL_POINT_RULE,
        "detector_warning": det.warnings[0] if det.warnings else "",
    }
    (OUT / "kg.json").write_text(json.dumps(scene, separators=(",", ":")))
    print(f"wrote         : {OUT / 'kg.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
