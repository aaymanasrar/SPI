#!/usr/bin/env python
"""Run a real project end to end and compare against an engineer-verified BOQ.

    ./validate_project.py --config project.json

This is the only thing that can tell you whether the engine is accurate. Every
other test in this repository proves the engine does what it was told; this one
asks whether what it produces matches what an engineer actually issued.

It will not run on invented inputs. A synthetic drawing with a synthetic answer
proves the harness works and says nothing about real-world accuracy, so the
inputs must be real files on disk and the harness refuses otherwise.

Config (JSON):
{
  "project_code": "RYD-001",
  "dxf": "path/to/client.dxf",
  "baseline_boq": "path/to/engineer_verified.csv",   # device_type,quantity
  "symbol_map": "path/to/symbols.json",              # optional
  "boundary_layers": ["A-ROOM"],
  "label_layers": ["A-ROOM-IDEN"],
  "ceiling_height_m": 2.8,
  "ceiling_height_verified_from": "A-201 section B-B",
  "dimension_chains": [{"name":"west","axis":"y","segments":[...]}],
  "placement": [{"device_type":"smoke_detector","system":"fire_alarm",
                 "rule":{"rule_code":"ELV-B-01","source":"NFPA 72",
                         "confidence":"code","conditions":"smooth flat ceiling",
                         "max_spacing_m":9.1,"max_wall_distance_m":4.6},
                 "skip_rooms":["TOILET"]}],
  "obstructions": [...]
}
Every engineering figure above comes from the caller. The harness holds none.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from craft.cad import (CheckCoverageInput, CheckDimensionsInput, CountInput,
                       DevicePoint, DimensionChain, Obstruction,
                       PlaceDevicesInput, ReadDxfInput, RoomOutline, RoomsInput,
                       SpacingRule, check_coverage, check_dimensions,
                       count_devices, extract_rooms, place_devices, read_dxf)
from craft.core import LocalStorage

STEPS = ["import drawing", "identify rooms and symbols", "check dimensions",
         "propose devices", "generate BOQ", "compliance report",
         "compare with baseline"]


class Blocked(Exception):
    """An input the harness needs does not exist. Not a failure of the engine."""


def _require(path: str | None, what: str) -> Path:
    if not path:
        raise Blocked(f"{what} was not given in the config.")
    p = Path(path).expanduser()
    if not p.is_file():
        raise Blocked(f"{what} does not exist at {p}.")
    if p.stat().st_size == 0:
        raise Blocked(f"{what} at {p} is empty.")
    return p


def run(cfg: dict) -> int:
    print(f"Project {cfg.get('project_code','(unnamed)')}\n" + "=" * 62)
    try:
        dxf = _require(cfg.get("dxf"), "The client DXF")
        baseline = _require(cfg.get("baseline_boq"),
                            "The engineer-verified baseline BOQ")
    except Blocked as e:
        print(f"\nBLOCKED: {e}")
        print("\nThe harness is built and every step below is implemented. It has")
        print("not been run against a real project, so nothing here is evidence")
        print("of real-world accuracy.\n")
        for i, s in enumerate(STEPS, 1):
            print(f"  {i}. {s}  -- implemented, not exercised")
        print("\nTo close this, supply:")
        print("  * a client DXF for one floor")
        print("  * the BOQ an engineer issued for that same floor")
        print("  * the symbol map from that drawing's legend sheet")
        return 2

    store = LocalStorage(dxf.parent)
    key = dxf.name
    findings, failures = [], 0

    print("\n1. import drawing")
    r = read_dxf(ReadDxfInput(document_id=key, storage_key=key), store)
    print(f"   units {r.outputs['units']['name']}, {r.outputs['insert_total']} inserts, "
          f"{len(r.outputs['layers'])} layers")
    findings += r.findings

    print("\n2. identify rooms and symbols")
    rooms = extract_rooms(RoomsInput(document_id=key, storage_key=key,
        boundary_layers=cfg["boundary_layers"],
        label_layers=cfg.get("label_layers")), store)
    print(f"   {rooms.outputs['room_count']} rooms, "
          f"{sum(x['area_m2'] or 0 for x in rooms.outputs['rooms']):.1f} m2")
    smap = json.loads(Path(cfg["symbol_map"]).read_text()) if cfg.get("symbol_map") else None
    counted = count_devices(CountInput(document_id=key, storage_key=key,
                                       symbol_map=smap), store)
    print(f"   counted {counted.outputs['mapped_insert_count']} devices, "
          f"{counted.outputs['unmapped_insert_count']} unmapped")
    findings += rooms.findings + counted.findings

    print("\n3. check dimensions")
    chains = [DimensionChain(**c) for c in cfg.get("dimension_chains", [])]
    dims = check_dimensions(CheckDimensionsInput(document_id=key, storage_key=key,
                                                 chains=chains), store)
    print(f"   {dims.outputs['dimension_entities']} dimension entities, "
          f"{dims.outputs['conflicts']} conflict(s)")
    findings += dims.findings

    print("\n4. propose devices")
    proposed: dict[str, list] = {}
    obstructions = [Obstruction(**o) for o in cfg.get("obstructions", [])]
    for spec in cfg.get("placement", []):
        p = place_devices(PlaceDevicesInput(
            document_id=key, storage_key=key,
            boundary_layers=cfg["boundary_layers"],
            label_layers=cfg.get("label_layers"),
            device_type=spec["device_type"], system=spec["system"],
            rule=SpacingRule(**spec["rule"]),
            obstructions=obstructions,
            skip_rooms=spec.get("skip_rooms", []),
            min_room_area_m2=spec.get("min_room_area_m2", 0.0)), store)
        proposed[spec["device_type"]] = p.outputs["objects"]
        print(f"   {spec['device_type']}: {p.outputs['proposed_count']} proposed "
              f"from {spec['rule']['rule_code']}")
        findings += p.findings

    print("\n5. generate BOQ")
    print("   (quantities from step 2 and 4, each carrying its source; prices and")
    print("    product mappings must come from the catalogue, never defaulted)")

    print("\n6. compliance report")
    outlines = [RoomOutline(name=x["name"], boundary_m=[(a, b) for a, b in x["boundary"]])
                for x in rooms.outputs["rooms"]]
    for spec in cfg.get("placement", []):
        dt = spec["device_type"]
        pts = [DevicePoint(x_m=o["geometry"]["coordinates"][0],
                           y_m=o["geometry"]["coordinates"][1])
               for o in proposed.get(dt, [])]
        if not pts:
            continue
        # A room excluded from this system by an engineering decision must not
        # then be reported as uncovered by it.
        skip = {s.casefold() for s in spec.get("skip_rooms", [])}
        scoped = [o for o in outlines
                  if not (o.name and o.name.casefold() in skip)]
        cov = check_coverage(CheckCoverageInput(document_id=key, rooms=scoped,
            devices=pts, rule=SpacingRule(**spec["rule"])), None)
        print(f"   {dt}: {cov.outputs['rooms_passing']}/{cov.outputs['rooms_checked']} "
              f"rooms pass the geometric checks (NOT a compliance assessment)")
        findings += cov.findings

    print("\n7. compare with the engineer-verified baseline")
    want: dict[str, float] = {}
    with baseline.open() as fh:
        for row in csv.DictReader(fh):
            want[row["device_type"].strip()] = float(row["quantity"])
    got = {k: float(len(v)) for k, v in proposed.items()}
    for c in counted.outputs["counts"]:
        got[c["device_type"]] = got.get(c["device_type"], 0.0) + c["quantity"]

    print(f"   {'device type':<26} {'baseline':>9} {'engine':>8} {'diff':>8}")
    for dt in sorted(set(want) | set(got)):
        w, g = want.get(dt, 0.0), got.get(dt, 0.0)
        d = g - w
        if abs(d) > 1e-9:
            failures += 1
        print(f"   {dt:<26} {w:>9.0f} {g:>8.0f} {d:>+8.0f}")

    blockers = [f for f in findings if f.severity == "blocker"]
    print(f"\n{'-'*62}\nfindings: {len(findings)} ({len(blockers)} blocker)")
    for f in findings:
        print(f"  [{f.severity}] {f.code}: {f.subject}")
    print(f"quantity discrepancies: {failures}")
    if blockers:
        print("\nNOT VALIDATED: a blocker finding means the drawing or the inputs")
        print("cannot be relied on, whatever the quantities came out at.")
        return 1
    if failures:
        print("\nNOT VALIDATED: the engine disagrees with the engineer. Each line")
        print("above is a discrepancy to explain before the engine is trusted.")
        return 1
    print("\nMatched the baseline on every line.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    a = ap.parse_args()
    cfg_path = Path(a.config).expanduser()
    if not cfg_path.is_file():
        print(f"BLOCKED: no config at {cfg_path}")
        return 2
    return run(json.loads(cfg_path.read_text()))


if __name__ == "__main__":
    sys.exit(main())
