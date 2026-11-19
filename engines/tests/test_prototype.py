"""bim.prototype tests: floor plans in, a building out.

The fixture office (fixtures/floor_plans.py) is drawn three ways with the true
rooms and openings alongside. These tests pin what the pipeline recovers from
each: every room, named where the drawing names it, with its net area; every
opening, with its kind.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from craft.bim.prototype import PrototypeInput, prototype
from craft.core import InvalidInput, LocalStorage

ENGINES = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("floor_plans", ENGINES / "fixtures" / "floor_plans.py")
FP = importlib.util.module_from_spec(_spec)
sys.modules["floor_plans"] = FP
_spec.loader.exec_module(FP)
LEVELS = list(FP.LEVELS)


@pytest.fixture(scope="module")
def store(tmp_path_factory):
    s = LocalStorage(tmp_path_factory.mktemp("plans"))
    for i, name in enumerate(LEVELS):
        s.write(f"plan-L{i}.dxf", FP.build_dxf(name))
    pdf = FP.build_pdf(LEVELS)
    s.write("plans.pdf", pdf)
    s.write("scan.jpg", FP.build_scan(pdf, 1))
    return s


def _run(store, levels, **kw):
    return prototype(PrototypeInput(document_id="set", levels=levels, **kw), storage=store)


def _check_level(out, level_name, *, named=True, tol=0.03):
    lv = next(l for l in out["building"]["levels"] if l["name"] == level_name)
    truth = FP.truth(level_name)
    counts = {k: v for k, v in lv["counts"].items() if k != "rooms"}
    assert counts == truth["openings"], f"{level_name} openings"
    assert lv["counts"]["rooms"] == len(truth["rooms"]), f"{level_name} room count"
    if named:
        got = {s["name"].title(): s["area_m2"] for s in out["spaces"] if s["storey"] == level_name}
        for name, area in truth["rooms"].items():
            assert name in got, f"{name} not found on {level_name}"
            assert got[name] == pytest.approx(area, rel=tol), name
    return lv


@pytest.fixture(scope="module")
def dxf_result(store):
    return _run(store, [{"document_id": "a", "storage_key": "plan-L0.dxf", "name": LEVELS[0]},
                        {"document_id": "b", "storage_key": "plan-L1.dxf", "name": LEVELS[1]}])


def test_dxf_plans_give_every_room_and_opening(dxf_result):
    out = dxf_result.outputs
    for name in LEVELS:
        _check_level(out, name)
    lv = out["building"]["levels"][0]
    assert lv["source"]["kind"] == "dxf" and "A-WALL" in lv["source"]["notes"][0]
    # Door and window blocks decide the kind on a DXF.
    assert all("block" in o["evidence"] for o in lv["openings"] if o["kind"] != "opening")


def test_levels_stack_on_assumed_storey_heights_and_say_so(dxf_result):
    out = dxf_result.outputs
    assert [s["elevation_m"] for s in out["storeys"]] == [0.0, 3.6]
    assert out["building"]["roof"]["z"] == pytest.approx(7.2)
    keys = {a.key for a in dxf_result.assumptions}
    assert {"storey_height_m", "ceiling_height_m", "door_head_m", "window_sill_m"} <= keys
    assert all(a.status == "assumed" for a in dxf_result.assumptions)
    assert "PROTOTYPE-HEIGHTS-ASSUMED" in [f.code for f in dxf_result.findings]
    # DXFs share coordinates, so the levels are not re-centred.
    assert "LEVELS-ALIGNED-BY-CENTRE" not in [f.code for f in dxf_result.findings]


def test_openings_are_placed_where_they_are_drawn(dxf_result):
    lv = dxf_result.outputs["building"]["levels"][0]
    entrance = min((o for o in lv["openings"] if o["exterior"] and o["kind"] == "door"),
                   key=lambda o: abs(o["center"][0] - 4.0) + abs(o["center"][1]))
    assert entrance["center"] == pytest.approx([4.0, 0.0], abs=0.05)
    assert entrance["width_m"] == pytest.approx(1.8, abs=0.05)
    assert entrance["leaf"] is True


def test_pdf_sheet_gives_every_room_and_opening(store):
    res = _run(store, [{"document_id": "p", "storage_key": "plans.pdf", "page": 1, "name": LEVELS[0]},
                       {"document_id": "p", "storage_key": "plans.pdf", "page": 2, "name": LEVELS[1]}])
    for name in LEVELS:
        lv = _check_level(res.outputs, name)
        assert lv["source"]["scale"].startswith("sheet text: 1:100")
    # Two sheets do not share coordinates: stacked on their outlines, and said.
    assert "LEVELS-ALIGNED-BY-CENTRE" in [f.code for f in res.findings]


def test_scan_with_a_dimension_gives_every_room(store):
    res = _run(store, [{"document_id": "s", "storage_key": "scan.jpg", "name": LEVELS[0],
                        "known_length_m": 20.3}])
    lv = _check_level(res.outputs, LEVELS[0], named=False)
    assert lv["source"]["scale"].startswith("calibrated")
    areas = sorted(s["area_m2"] for s in res.outputs["spaces"])
    truth = sorted(FP.truth(LEVELS[0])["rooms"].values())
    assert areas == pytest.approx(truth, rel=0.04)


def test_scan_without_a_scale_estimates_one_and_records_it(store):
    res = _run(store, [{"document_id": "s", "storage_key": "scan.jpg", "name": LEVELS[0]}])
    _check_level(res.outputs, LEVELS[0], named=False)
    scale = [a for a in res.assumptions if a.key.endswith(": scale")]
    assert scale and "door" in scale[0].basis
    assert "dimension" in scale[0].verify_from


def test_supplied_heights_are_used_and_verified(store):
    res = _run(store, [{"document_id": "a", "storage_key": "plan-L0.dxf"}],
               storey_height_m=4.2, ceiling_height_m=3.3, heights_verified_from="A-301 Section A-A")
    out = res.outputs
    assert out["building"]["roof"]["z"] == pytest.approx(4.2)
    assert {s["height_m"] for s in out["spaces"]} == {3.3}
    verified = {a.key for a in res.assumptions if a.status == "verified"}
    assert {"storey_height_m", "ceiling_height_m"} <= verified
    assert "PROTOTYPE-HEIGHTS-ASSUMED" not in [f.code for f in res.findings]


def test_what_cannot_be_read_is_refused_with_a_reason(store, tmp_path):
    s = LocalStorage(tmp_path)
    s.write("x.dwg", b"AC1032" + b"\0" * 64)
    with pytest.raises(InvalidInput, match="Save it as DXF"):
        _run(s, [{"document_id": "x", "storage_key": "x.dwg"}])
    blank = Image.fromarray(np.full((400, 600), 255, np.uint8))
    import io
    buf = io.BytesIO()
    blank.save(buf, "PNG")
    s.write("blank.png", buf.getvalue())
    with pytest.raises(InvalidInput, match="no walls"):
        _run(s, [{"document_id": "x", "storage_key": "blank.png"}])
    with pytest.raises(InvalidInput, match="page 3 does not exist"):
        _run(store, [{"document_id": "p", "storage_key": "plans.pdf", "page": 3}])


def _device_rules():
    import json
    import subprocess
    out = subprocess.run([sys.executable, str(ENGINES.parent / "simulator" / "rules.py"), "--device-rules"],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_device_layout_is_proposed_from_rules_and_covers_every_room(store):
    res = _run(store, [{"document_id": "a", "storage_key": "plan-L0.dxf"},
                       {"document_id": "b", "storage_key": "plan-L1.dxf"}], device_rules=_device_rules())
    out = res.outputs
    devs = out["devices"]
    assert devs and all(d["proposed"] and d["rule"] and d["basis"] for d in devs)
    kinds = {c["device_type"]: c["quantity"] for c in out["counts"]}
    # An exit door on the ground floor and a stair door on each floor.
    assert kinds["manual_call_point"] == 3
    assert kinds["card_reader"] == 1                  # the one outside door
    # Every point of every room is within the FA-02 radius of a detector in it.
    for room in out["spaces"]:
        dets = [d for d in devs if d["device_type"] == "smoke_detector" and d["space"] == room["label"]
                and d["storey"] == room["storey"]]
        poly = room["footprint_m"]
        xs, ys = [p[0] for p in poly], [p[1] for p in poly]
        for gx in np.linspace(min(xs) + 0.1, max(xs) - 0.1, 12):
            for gy in np.linspace(min(ys) + 0.1, max(ys) - 0.1, 12):
                assert any(np.hypot(d["x_m"] - gx, d["y_m"] - gy) <= 6.37 for d in dets), room["label"]
    # Heights sit inside the rule's band, or at the room's ceiling.
    for d in devs:
        base = 0.0 if d["storey"] == "Ground floor" else 3.6
        if d["device_type"] == "manual_call_point":
            assert 1.07 <= d["z_m"] - base <= 1.22
        if d["device_type"] == "sounder_strobe":
            assert 2.03 <= d["z_m"] - base <= 2.44
    assert "DEVICES-PROPOSED" in [f.code for f in res.findings]


def test_no_rules_no_devices(dxf_result):
    assert dxf_result.outputs["devices"] == []
