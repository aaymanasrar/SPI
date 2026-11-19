"""cad.place_devices tests.

This was a stub. It is implemented now only because the rules library carries
spacing figures with citations, and the rule is passed in as data. The tests
that matter are the ones proving the output is a proposal, not an observation.
"""
from __future__ import annotations

import io
import math

import ezdxf
import pytest
from pydantic import ValidationError

from craft.cad import PlaceDevicesInput, SpacingRule, place_devices
from craft.cad.place import _axis_positions, measure_route
from craft.core import InvalidInput, LocalStorage

NFPA = SpacingRule(rule_code="ELV-B-01", source="NFPA 72",
                   max_spacing_m=9.1, max_wall_distance_m=4.6)


def _plan(rooms, insunits=6) -> bytes:
    d = ezdxf.new("R2010", setup=True)
    d.header["$INSUNITS"] = insunits
    for l in ("ROOM-BOUNDARY", "ROOM-NAMES"):
        d.layers.add(l)
    m = d.modelspace()
    for name, x0, y0, x1, y1 in rooms:
        m.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True,
                         dxfattribs={"layer": "ROOM-BOUNDARY"})
        m.add_text(name, dxfattribs={"layer": "ROOM-NAMES", "height": 0.2}
                   ).set_placement(((x0 + x1) / 2, (y0 + y1) / 2))
    s = io.StringIO()
    d.write(s)
    return s.getvalue().encode()


@pytest.fixture
def storage(tmp_path):
    s = LocalStorage(tmp_path)
    s.write("small.dxf", _plan([("OFFICE", 0, 0, 6, 5)]))
    s.write("hall.dxf", _plan([("HALL", 0, 0, 30, 20)]))
    s.write("mixed.dxf", _plan([("CLASS", 0, 0, 8, 9), ("WC", 9, 0, 10.5, 1.5)]))
    s.write("unitless.dxf", _plan([("OFFICE", 0, 0, 6, 5)], insunits=0))
    return s


def _run(storage, key="small.dxf", **kw):
    base = dict(document_id="d", storage_key=key, boundary_layers=["ROOM-BOUNDARY"],
                label_layers=["ROOM-NAMES"], device_type="smoke_detector",
                system="fire_alarm", rule=NFPA)
    base.update(kw)
    return place_devices(PlaceDevicesInput(**base), storage)


# ------------------------------------------------------------ the spacing maths
def test_a_room_within_the_wall_limit_gets_one_device():
    """6 m wide, limit 4.6 m from each wall: the centre is within reach of both."""
    assert _axis_positions(6.0, 9.1, 4.6) == [3.0]


def test_a_long_room_gets_enough_points_to_hold_the_spacing():
    pos = _axis_positions(30.0, 9.1, 4.6)
    assert pos[0] <= 4.6 + 1e-9
    assert 30.0 - pos[-1] <= 4.6 + 1e-9
    for a, b in zip(pos, pos[1:]):
        assert b - a <= 9.1 + 1e-9


def test_points_are_spread_evenly_not_packed_to_one_end():
    pos = _axis_positions(30.0, 9.1, 4.6)
    gaps = [round(b - a, 6) for a, b in zip(pos, pos[1:])]
    assert len(set(gaps)) == 1


def test_a_single_device_covers_a_small_room(storage):
    r = _run(storage)
    assert r.outputs["proposed_count"] == 1
    x, y = r.outputs["objects"][0]["geometry"]["coordinates"]
    assert (x, y) == (3.0, 2.5)


def test_a_large_room_respects_both_limits(storage):
    r = _run(storage, key="hall.dxf")
    pts = [o["geometry"]["coordinates"] for o in r.outputs["objects"]]
    # 30 m: (30-9.2)/9.1 -> 4 positions.  20 m: (20-9.2)/9.1 -> 3.
    assert len(pts) == 12
    # The wall limit binds the end positions on each axis; the ones between are
    # governed by spacing. Asserting it of every point is simply wrong.
    for axis, extent in ((0, 30.0), (1, 20.0)):
        vals = sorted({round(p[axis], 3) for p in pts})
        assert vals[0] <= 4.6 + 1e-6
        assert extent - vals[-1] <= 4.6 + 1e-6
        for a, b in zip(vals, vals[1:]):
            assert b - a <= 9.1 + 1e-6


# ------------------------------------------------- proposal, not observation
def test_every_position_is_marked_as_a_proposal_for_review(storage):
    r = _run(storage)
    o = r.outputs["objects"][0]
    assert o["source"] == "ai_extracted"       # not 'imported': never drawn
    assert o["review_status"] == "pending"
    assert o["confidence"] is None


def test_the_rule_is_named_on_every_object_and_in_provenance(storage):
    r = _run(storage)
    o = r.outputs["objects"][0]
    assert "ELV-B-01" in o["source_reference"] and "NFPA 72" in o["source_reference"]
    assert o["extracted_value"]["basis"] == "ELV-B-01"
    assert any("ELV-B-01" in p.source for p in r.provenance)


def test_the_result_warns_that_spacing_is_a_maximum(storage):
    r = _run(storage)
    w = " ".join(r.warnings)
    assert "PROPOSED" in w and "not" in w
    assert "maximum" in w and "engineer must review" in w


def test_it_writes_no_file_and_no_rows(storage):
    r = _run(storage)
    assert r.files == []


# -------------------------------------------------------- what it refuses
def test_a_rule_without_a_citation_cannot_be_built():
    with pytest.raises(ValidationError):
        SpacingRule(rule_code="ELV-B-01", max_spacing_m=9.1, max_wall_distance_m=4.6)
    with pytest.raises(ValidationError):
        SpacingRule(source="NFPA 72", max_spacing_m=9.1, max_wall_distance_m=4.6)


def test_a_nonpositive_spacing_is_refused():
    with pytest.raises(ValidationError):
        SpacingRule(rule_code="X", source="Y", max_spacing_m=0, max_wall_distance_m=4.6)


def test_a_unitless_drawing_is_refused(storage):
    with pytest.raises(InvalidInput) as e:
        _run(storage, key="unitless.dxf")
    assert "real-world distance" in str(e.value)


def test_rooms_can_be_skipped_by_the_caller(storage):
    """Which rooms need a detector is an engineering decision, not the tool's."""
    everything = _run(storage, key="mixed.dxf")
    assert {p["room"] for p in everything.outputs["per_room"]} == {"CLASS", "WC"}
    skipped = _run(storage, key="mixed.dxf", skip_rooms=["WC"])
    assert {p["room"] for p in skipped.outputs["per_room"]} == {"CLASS"}
    assert skipped.outputs["rooms_skipped"] == ["wc"]


def test_tiny_rooms_can_be_filtered_by_area(storage):
    r = _run(storage, key="mixed.dxf", min_room_area_m2=5.0)
    assert {p["room"] for p in r.outputs["per_room"]} == {"CLASS"}


def test_measure_route_is_still_not_implemented():
    from craft.cad.place import MeasureRouteInput
    with pytest.raises(NotImplementedError) as e:
        measure_route(MeasureRouteInput(document_id="d", storage_key="x.dxf",
                                        from_point=(0, 0), to_point=(1, 1)))
    assert "D-7" in str(e.value)


def test_the_registry_now_reports_place_devices_as_implemented():
    from craft.core import tool_schemas
    by = {s["name"]: s for s in tool_schemas()}
    assert by["cad.place_devices"]["implemented"] is True
    assert by["cad.measure_route"]["implemented"] is False
