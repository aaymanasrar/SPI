"""Dimension checking, obstruction handling and coverage checking.

Every figure in these tests arrives as data with a citation. No spacing,
clearance or mounting number is defaulted by the code under test, and
test_no_engineering_values_are_hard_coded asserts that by reading the modules.
"""
from __future__ import annotations

import io
import math

import ezdxf
import pytest
from pydantic import ValidationError

from craft.cad import (CheckCoverageInput, CheckDimensionsInput, DevicePoint,
                       DimensionChain, Obstruction, PlaceDevicesInput, RoomOutline,
                       SpacingRule, check_coverage, check_dimensions, place_devices)
from craft.core import Finding, LocalStorage

NFPA = SpacingRule(rule_code="ELV-B-01", source="NFPA 72", confidence="code",
                   conditions="smooth flat ceiling",
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
    s = io.StringIO(); d.write(s)
    return s.getvalue().encode()


@pytest.fixture
def storage(tmp_path):
    s = LocalStorage(tmp_path)
    s.write("hall.dxf", _plan([("HALL", 0, 0, 30, 20)]))
    s.write("office.dxf", _plan([("OFFICE", 0, 0, 6, 5)]))
    return s


# ====================================================== dimension checking
def test_chain_that_does_not_reach_its_total_is_a_blocker():
    r = check_dimensions(CheckDimensionsInput(document_id="KG", chains=[
        DimensionChain(name="north", axis="x",
                       segments=[4.5, 3.67, 3.06, 3.06, 3.54, 1.98],
                       expected_total=23.0)]))
    f = next(x for x in r.findings if x.code == "DIM-CHAIN-SUM")
    assert f.severity == "blocker"
    assert "19.81" in f.detail and "23.0" in f.detail
    assert r.status != "ok"


def test_two_chains_on_one_axis_that_disagree_are_a_blocker():
    """The defect on the supplied KG sheet: 23.56 m against 21.40 m."""
    r = check_dimensions(CheckDimensionsInput(document_id="KG", chains=[
        DimensionChain(name="west", axis="y", segments=[4.23, 4, 4, 4.99, 2.16, 4.18]),
        DimensionChain(name="east", axis="y", segments=[1.44, 9.98, 9.98])]))
    f = next(x for x in r.findings if x.code == "DIM-CHAIN-CONFLICT")
    assert f.severity == "blocker"
    assert "23.56" in f.detail and "21.4" in f.detail
    assert "cannot tell which" in f.detail      # it does not pick a winner
    assert "Resolve against the original DXF" in f.action


def test_chains_that_agree_produce_no_finding():
    r = check_dimensions(CheckDimensionsInput(document_id="d", chains=[
        DimensionChain(name="a", axis="x", segments=[5.0, 5.0], expected_total=10.0),
        DimensionChain(name="b", axis="x", segments=[10.0])]))
    assert r.findings == []
    assert r.status == "ok"
    assert r.outputs["chains"][0]["agrees"] is True


def test_rounding_drift_inside_tolerance_is_accepted():
    r = check_dimensions(CheckDimensionsInput(document_id="d", tolerance_m=0.02,
        chains=[DimensionChain(name="a", axis="x", segments=[3.33, 3.33, 3.33],
                               expected_total=10.0)]))
    assert r.findings == []


def test_drift_beyond_tolerance_is_reported():
    r = check_dimensions(CheckDimensionsInput(document_id="d", tolerance_m=0.001,
        chains=[DimensionChain(name="a", axis="x", segments=[3.33, 3.33, 3.33],
                               expected_total=10.0)]))
    assert any(f.code == "DIM-CHAIN-SUM" for f in r.findings)


def test_dimension_text_typed_over_the_measurement_is_a_blocker(storage, tmp_path):
    """The defect that survives every visual check: the sheet reads right and
    the geometry is wrong."""
    d = ezdxf.new("R2010", setup=True)
    d.header["$INSUNITS"] = 6
    msp = d.modelspace()
    dim = msp.add_linear_dim(base=(0, -1), p1=(0, 0), p2=(5, 0),
                             text="7.50", dxfattribs={"layer": "DIMS"})
    dim.render()
    s = io.StringIO(); d.write(s)
    storage.write("lied.dxf", s.getvalue().encode())
    r = check_dimensions(CheckDimensionsInput(document_id="d",
                                              storage_key="lied.dxf"), storage)
    f = next(x for x in r.findings if x.code == "DIM-TEXT-OVERRIDE")
    assert f.severity == "blocker"
    assert "7.50" in f.detail
    assert r.status != "ok"


def test_a_dimension_showing_its_own_measurement_is_not_flagged(storage):
    d = ezdxf.new("R2010", setup=True)
    d.header["$INSUNITS"] = 6
    d.modelspace().add_linear_dim(base=(0, -1), p1=(0, 0), p2=(5, 0)).render()
    s = io.StringIO(); d.write(s)
    storage.write("honest.dxf", s.getvalue().encode())
    r = check_dimensions(CheckDimensionsInput(document_id="d",
                                              storage_key="honest.dxf"), storage)
    assert [f for f in r.findings if f.code == "DIM-TEXT-OVERRIDE"] == []


# ========================================================= obstructions
def test_a_device_landing_on_a_column_is_moved_clear(storage):
    """30 x 20 m hall: the rule puts a device at (4.6, 4.6)."""
    clean = place_devices(PlaceDevicesInput(
        document_id="d", storage_key="hall.dxf", boundary_layers=["ROOM-BOUNDARY"],
        label_layers=["ROOM-NAMES"], device_type="smoke_detector",
        system="fire_alarm", rule=NFPA), storage)
    pts = [tuple(o["geometry"]["coordinates"]) for o in clean.outputs["objects"]]
    assert (4.6, 4.6) in pts

    blocked = place_devices(PlaceDevicesInput(
        document_id="d", storage_key="hall.dxf", boundary_layers=["ROOM-BOUNDARY"],
        label_layers=["ROOM-NAMES"], device_type="smoke_detector",
        system="fire_alarm", rule=NFPA,
        obstructions=[Obstruction(kind="column", x_m=4.6, y_m=4.6, radius_m=0.6,
                                  source="A-101 column grid")]), storage)
    moved = [tuple(o["geometry"]["coordinates"]) for o in blocked.outputs["objects"]]
    assert (4.6, 4.6) not in moved
    assert len(moved) == len(pts)                      # displaced, not dropped
    near = min(math.hypot(x - 4.6, y - 4.6) for x, y in moved)
    assert near >= 0.6                                  # outside the keep-clear
    assert blocked.outputs["per_room"][0]["displaced_by_obstruction"] == 1


def test_an_unavoidable_obstruction_is_reported_not_silently_dropped(storage):
    """A keep-clear bigger than the permitted nudge cannot be worked around."""
    r = place_devices(PlaceDevicesInput(
        document_id="d", storage_key="hall.dxf", boundary_layers=["ROOM-BOUNDARY"],
        label_layers=["ROOM-NAMES"], device_type="smoke_detector",
        system="fire_alarm", rule=NFPA,
        obstructions=[Obstruction(kind="bulkhead", x_m=4.6, y_m=4.6, radius_m=8.0,
                                  source="A-301 section")]), storage)
    f = next(x for x in r.findings if x.code == "PLACEMENT-OBSTRUCTED")
    assert "bulkhead" in f.detail and "A-301 section" in f.detail
    assert "record the departure" in f.action
    assert r.outputs["per_room"][0]["blocked_by_obstruction"] >= 1


def test_an_obstruction_must_say_where_it_came_from():
    with pytest.raises(ValidationError):
        Obstruction(kind="column", x_m=1, y_m=1, radius_m=0.5)


# ================================================== rule conditions & grade
def test_every_placement_carries_its_rule_and_review_state(storage):
    r = place_devices(PlaceDevicesInput(
        document_id="d", storage_key="office.dxf", boundary_layers=["ROOM-BOUNDARY"],
        label_layers=["ROOM-NAMES"], device_type="smoke_detector",
        system="fire_alarm", rule=NFPA), storage)
    ev = r.outputs["objects"][0]["extracted_value"]
    assert ev["rule"]["code"] == "ELV-B-01"
    assert ev["rule"]["source"] == "NFPA 72"
    assert ev["rule"]["conditions"] == "smooth flat ceiling"
    assert ev["evidence"] == "calculated"
    assert ev["validation_status"] == "unreviewed"


def test_rule_conditions_are_raised_as_a_finding(storage):
    r = place_devices(PlaceDevicesInput(
        document_id="d", storage_key="office.dxf", boundary_layers=["ROOM-BOUNDARY"],
        label_layers=["ROOM-NAMES"], device_type="smoke_detector",
        system="fire_alarm", rule=NFPA), storage)
    f = next(x for x in r.findings if x.code == "PLACEMENT-CONDITIONS")
    assert "smooth flat ceiling" in f.detail
    assert "Nothing in this tool checks" in f.detail


def test_a_non_code_rule_is_flagged_as_weaker(storage):
    practice = NFPA.model_copy(update={"confidence": "spec", "rule_code": "SPT-CC-11"})
    r = place_devices(PlaceDevicesInput(
        document_id="d", storage_key="office.dxf", boundary_layers=["ROOM-BOUNDARY"],
        label_layers=["ROOM-NAMES"], device_type="camera", system="cctv",
        rule=practice), storage)
    f = next(x for x in r.findings if x.code == "PLACEMENT-RULE-NOT-CODE")
    assert "spec" in f.detail


def test_placement_records_its_basis_as_an_assumption(storage):
    r = place_devices(PlaceDevicesInput(
        document_id="d", storage_key="office.dxf", boundary_layers=["ROOM-BOUNDARY"],
        label_layers=["ROOM-NAMES"], device_type="smoke_detector",
        system="fire_alarm", rule=NFPA), storage)
    a = next(x for x in r.assumptions if x.key == "placement_basis")
    assert a.value == "ELV-B-01" and a.status == "assumed"


# ============================================================== coverage
SQUARE = RoomOutline(name="HALL", boundary_m=[(0, 0), (20, 0), (20, 20), (0, 20)])


def test_a_room_with_no_device_is_a_blocker():
    r = check_coverage(CheckCoverageInput(document_id="d", rooms=[SQUARE],
                                          devices=[], rule=NFPA))
    f = next(x for x in r.findings if x.code == "COVERAGE-NO-DEVICE")
    assert f.severity == "blocker"
    assert r.outputs["rooms_passing"] == 0


def test_one_device_cannot_cover_a_room_larger_than_its_reach():
    r = check_coverage(CheckCoverageInput(document_id="d", rooms=[SQUARE],
        devices=[DevicePoint(x_m=10, y_m=10)], rule=NFPA))
    assert any(f.code == "COVERAGE-GAP" for f in r.findings)
    assert r.outputs["uncovered_samples"] > 0


def test_a_layout_that_satisfies_both_limits_passes():
    small = RoomOutline(name="OFFICE", boundary_m=[(0, 0), (6, 0), (6, 5), (0, 5)])
    r = check_coverage(CheckCoverageInput(document_id="d", rooms=[small],
        devices=[DevicePoint(x_m=3, y_m=2.5)], rule=NFPA))
    assert r.findings == []
    assert r.outputs["per_room"][0]["passes"] is True


def test_a_wall_with_no_device_near_it_is_reported():
    """The limit binds the WALL, not the device: every wall must be served."""
    big = RoomOutline(name="BIG", boundary_m=[(0, 0), (40, 0), (40, 40), (0, 40)])
    r = check_coverage(CheckCoverageInput(document_id="d", rooms=[big],
        devices=[DevicePoint(x_m=20, y_m=20)], rule=NFPA, grid_step_m=2.0))
    walls = r.outputs["per_room"][0]["walls_beyond_device_limit"]
    assert len(walls) == 4                 # a lone central device serves none
    f = next(x for x in r.findings if x.code == "COVERAGE-WALL-DISTANCE")
    assert "has no device within" in f.detail


def test_an_interior_device_is_not_faulted_for_being_away_from_walls():
    """A detector in the middle of a large room is governed by spacing, not by
    the wall limit. Faulting it was a real defect in this checker."""
    hall = RoomOutline(name="HALL", boundary_m=[(0, 0), (30, 0), (30, 20), (0, 20)])
    corners = [DevicePoint(x_m=x, y_m=y)
               for x in (4.6, 11.533, 18.467, 25.4) for y in (4.6, 10.0, 15.4)]
    r = check_coverage(CheckCoverageInput(document_id="d", rooms=[hall],
        devices=corners, rule=NFPA, grid_step_m=1.0))
    assert r.outputs["per_room"][0]["walls_beyond_device_limit"] == []


def test_coverage_result_states_plainly_that_it_is_not_compliance():
    r = check_coverage(CheckCoverageInput(document_id="d", rooms=[SQUARE],
        devices=[DevicePoint(x_m=10, y_m=10)], rule=NFPA))
    assert r.outputs["is_compliance_assessment"] is False
    assert "ceiling obstructions, beams and bulkheads" in r.outputs["checks_NOT_performed"]
    assert "NOT a compliance assessment" in " ".join(r.warnings)


def test_what_this_engine_proposes_passes_its_own_check(storage):
    """Propose and verify are separate acts, and they must agree."""
    placed = place_devices(PlaceDevicesInput(
        document_id="d", storage_key="hall.dxf", boundary_layers=["ROOM-BOUNDARY"],
        label_layers=["ROOM-NAMES"], device_type="smoke_detector",
        system="fire_alarm", rule=NFPA), storage)
    pts = [DevicePoint(x_m=o["geometry"]["coordinates"][0],
                       y_m=o["geometry"]["coordinates"][1])
           for o in placed.outputs["objects"]]
    hall = RoomOutline(name="HALL", boundary_m=[(0, 0), (30, 0), (30, 20), (0, 20)])
    r = check_coverage(CheckCoverageInput(document_id="d", rooms=[hall],
                                          devices=pts, rule=NFPA, grid_step_m=0.5))
    assert [f.code for f in r.findings] == []


def test_coverage_needs_rooms():
    from craft.core import InvalidInput
    with pytest.raises(InvalidInput):
        check_coverage(CheckCoverageInput(document_id="d", rooms=[],
                                          devices=[], rule=NFPA))


# ======================================================= the standing rule
def test_no_engineering_values_are_hard_coded():
    """Every spacing, clearance and mounting figure must arrive as data."""
    import inspect
    import craft.cad.place as place, craft.cad.coverage as cov
    for mod in (place, cov):
        src = inspect.getsource(mod)
        for forbidden in ("9.1", "4.6", "7.5", "5.3", "1.07", "1.22", "2.03"):
            assert forbidden not in src, f"{forbidden} hard-coded in {mod.__name__}"
