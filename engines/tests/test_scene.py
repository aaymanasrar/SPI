"""cad.scene_3d tests.

The whole point of this tool is the two numbers a DXF does not contain: ceiling
height and mounting heights. Most of these tests are about refusing to invent
them.
"""
from __future__ import annotations

import io

import ezdxf
import pytest
from pydantic import ValidationError

from craft.cad import MountingHeight, Scene3dInput, scene_3d
from craft.core import InvalidInput, LocalStorage

SYMBOLS = {
    "name": "test", "version": "1", "source_document": "test fixture",
    "rules": [
        {"block": "SMOKE-DETECTOR", "system": "fire_alarm", "device_type": "smoke_detector"},
        {"block": "MANUAL-CALL-POINT", "system": "fire_alarm", "device_type": "manual_call_point"},
        {"block": "DATA-OUTLET", "system": "data", "device_type": "data_outlet"},
    ],
}
HEIGHTS = {
    "smoke_detector": MountingHeight(
        at_ceiling=True, source="SPT-FA-01 (NFPA 72 Ch.17) - ceiling mounted"),
    "manual_call_point": MountingHeight(
        height_m=1.15, tolerance_m=(1.07, 1.22),
        source="SPT-FA-12 (NFPA 72 17.15.9) - 1.07-1.22 m AFF"),
}


def _plan(insunits: int = 4) -> bytes:
    d = ezdxf.new("R2010", setup=True)
    d.header["$INSUNITS"] = insunits
    for b in ("SMOKE-DETECTOR", "MANUAL-CALL-POINT", "DATA-OUTLET"):
        d.blocks.new(b)
    for l in ("FA-DEVICES", "DATA", "ROOM-BOUNDARY", "ROOM-NAMES"):
        d.layers.add(l)
    m = d.modelspace()
    # One 10 m x 6 m room, in millimetres.
    m.add_lwpolyline([(0, 0), (10000, 0), (10000, 6000), (0, 6000)], close=True,
                     dxfattribs={"layer": "ROOM-BOUNDARY"})
    m.add_text("OFFICE", dxfattribs={"layer": "ROOM-NAMES", "height": 200}
               ).set_placement((5000, 3000))
    m.add_blockref("SMOKE-DETECTOR", (2000, 2000), dxfattribs={"layer": "FA-DEVICES"})
    m.add_blockref("SMOKE-DETECTOR", (7000, 4000), dxfattribs={"layer": "FA-DEVICES"})
    m.add_blockref("MANUAL-CALL-POINT", (500, 500), dxfattribs={"layer": "FA-DEVICES"})
    m.add_blockref("DATA-OUTLET", (9000, 1000), dxfattribs={"layer": "DATA"})
    s = io.StringIO()
    d.write(s)
    return s.getvalue().encode()


@pytest.fixture
def storage(tmp_path):
    s = LocalStorage(tmp_path)
    s.write("L01.dxf", _plan())
    s.write("unitless.dxf", _plan(insunits=0))
    return s


def _run(storage, **kw):
    base = dict(document_id="L01", storage_key="L01.dxf",
                boundary_layers=["ROOM-BOUNDARY"], label_layers=["ROOM-NAMES"],
                ceiling_height_m=2.8, mounting_heights=HEIGHTS, symbol_map=SYMBOLS)
    base.update(kw)
    return scene_3d(Scene3dInput(**base), storage)


# ------------------------------------------------------------ geometry
def test_plan_coordinates_are_converted_to_metres(storage):
    r = _run(storage)
    d = next(x for x in r.outputs["devices"] if x["device_type"] == "manual_call_point")
    assert d["x_m"] == 0.5 and d["y_m"] == 0.5        # 500 mm
    room = r.outputs["rooms"][0]
    assert room["area_m2"] == 60.0                    # 10 m x 6 m
    assert room["boundary_m"][2] == [10.0, 6.0]


def test_rooms_carry_the_supplied_ceiling_height(storage):
    r = _run(storage, ceiling_height_m=3.2)
    assert all(x["height_m"] == 3.2 for x in r.outputs["rooms"])
    assert r.outputs["ceiling_height_m"] == 3.2


def test_each_device_is_assigned_to_the_room_it_sits_in(storage):
    r = _run(storage)
    assert all(d["room"] == "OFFICE" for d in r.outputs["devices"])


def test_counts_are_grouped_by_system(storage):
    r = _run(storage)
    assert r.outputs["counts_by_system"] == {"data": 1, "fire_alarm": 3}
    assert r.outputs["device_count"] == 4


# ---------------------------------------------- the heights it will not invent
def test_ceiling_mounted_devices_sit_at_the_ceiling(storage):
    r = _run(storage, ceiling_height_m=2.8)
    for d in r.outputs["devices"]:
        if d["device_type"] == "smoke_detector":
            assert d["z_m"] == 2.8
            assert "NFPA 72" in d["height_source"]


def test_a_fixed_height_is_used_with_its_band_and_citation(storage):
    r = _run(storage)
    d = next(x for x in r.outputs["devices"] if x["device_type"] == "manual_call_point")
    assert d["z_m"] == 1.15
    assert d["height_band_m"] == [1.07, 1.22]
    assert "17.15.9" in d["height_source"]


def test_a_device_type_with_no_supplied_height_is_not_placed(storage):
    """The refusal this tool exists for: no height means no vertical position,
    not a plausible-looking default."""
    r = _run(storage)
    d = next(x for x in r.outputs["devices"] if x["device_type"] == "data_outlet")
    assert d["z_m"] is None
    assert d["height_source"] is None
    assert r.status == "missing_data"
    assert r.outputs["devices_without_mounting_height"] == {"data_outlet": 1}
    note = next(m.note for m in r.missing if m.record == "device_type:data_outlet")
    assert "no mounting height" in note and "holds no heights of its own" in note


def test_an_unplaced_device_keeps_its_plan_position(storage):
    """It is still counted and still located in plan; only Z is missing."""
    r = _run(storage)
    d = next(x for x in r.outputs["devices"] if x["device_type"] == "data_outlet")
    assert d["x_m"] == 9.0 and d["y_m"] == 1.0
    assert d["room"] == "OFFICE"


def test_the_whole_scene_is_ok_once_every_height_is_supplied(storage):
    heights = dict(HEIGHTS)
    heights["data_outlet"] = MountingHeight(
        height_m=0.3, source="SPT-NW (project standard) - 300 mm AFF")
    r = _run(storage, mounting_heights=heights)
    assert r.status == "ok"
    assert r.missing == []
    assert all(d["z_m"] is not None for d in r.outputs["devices"])


def test_a_mounting_height_without_a_source_is_rejected():
    """A height with no citation cannot be defended on site."""
    with pytest.raises(ValidationError):
        MountingHeight(height_m=1.15)


def test_ceiling_height_is_required():
    with pytest.raises(ValidationError):
        Scene3dInput(document_id="d", storage_key="L01.dxf",
                     boundary_layers=["ROOM-BOUNDARY"])


def test_a_nonsense_ceiling_height_is_refused(storage):
    with pytest.raises(InvalidInput) as e:
        _run(storage, ceiling_height_m=0)
    assert "sections" in str(e.value)


def test_a_unitless_drawing_cannot_be_built_to_scale(storage):
    r = _run(storage, storage_key="unitless.dxf")
    assert r.status == "missing_data"
    assert r.missing[0].field == "drawing_units"
    assert r.outputs == {}


# ----------------------------------------------------------------- provenance
def test_every_supplied_height_appears_in_provenance(storage):
    r = _run(storage)
    refs = {p.value_ref for p in r.provenance}
    assert "mounting_height:smoke_detector" in refs
    assert "mounting_height:manual_call_point" in refs
    assert "ceiling_height_m" in refs
    assert any("2.8" in p.source for p in r.provenance
               if p.value_ref == "ceiling_height_m")


def test_scene_3d_writes_no_file(storage):
    r = _run(storage)
    assert r.files == []


def test_scene_3d_is_preview_only():
    from craft.core import tool_schemas
    s = next(x for x in tool_schemas() if x["name"] == "cad.scene_3d")
    assert s["modes"] == ["preview"]
