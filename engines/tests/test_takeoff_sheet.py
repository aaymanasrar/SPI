"""cad.takeoff_sheet and cad.sheet_setup.

Same synthetic floor plan as test_cad.py: three smoke detectors and a call
point on FA-DEVICES, a camera on CCTV, two unmapped blocks (FD, NORTH-ARROW),
and two rooms of 20 m² and 4 m² in millimetres.
"""
from __future__ import annotations

import io

import ezdxf
import pytest

from craft.cad import (ROOMS_LAYER, SCHEDULE_LAYER, SHEET_LAYER, TAKEOFF_LAYER,
                       CountInput, SheetSetupInput, TakeoffSheetInput, TitleBlock,
                       count_devices, sheet_setup, takeoff_sheet)
from craft.core import LocalStorage

from test_cad import SYMBOL_MAP, _dxf

FULL_MAP = {**SYMBOL_MAP, "rules": SYMBOL_MAP["rules"] + [
    {"block": "FD", "layer": "MECH", "system": "hvac_interface", "device_type": "fire_damper_monitor"},
    {"block": "NORTH-ARROW", "system": "drawing", "device_type": "north_arrow"},
]}

TB = TitleBlock(legal_owner="SmartPage Technology", title="Ground floor fire alarm layout",
                drawing_number="SPT-FA-101", revision="A", date_of_issue="2026-11-19",
                document_type="Shop drawing", created_by="A. Engineer", approved_by="B. Lead",
                project="Test tower", client="Test client", sheet="1/1")


@pytest.fixture
def storage(tmp_path):
    s = LocalStorage(tmp_path)
    s.write("fp.dxf", _dxf())
    s.write("unitless.dxf", _dxf(insunits=0))
    return s


def _open(storage, key):
    return ezdxf.read(io.StringIO(storage.read(key).decode("utf-8")))


def _texts(doc, layer):
    return [e.dxf.text for e in doc.modelspace().query("TEXT") if e.dxf.layer == layer]


# ------------------------------------------------------------------ takeoff
def test_takeoff_schedule_matches_count_devices(storage):
    count = count_devices(CountInput(document_id="d", storage_key="fp.dxf",
                                     symbol_map=SYMBOL_MAP), storage)
    sheet = takeoff_sheet(TakeoffSheetInput(document_id="d", storage_key="fp.dxf",
                                            symbol_map=SYMBOL_MAP, output_key="out/t.dxf"),
                          storage)
    by_count = {(c["system"], c["device_type"]): c["quantity"] for c in count.outputs["counts"]}
    by_sheet = {(r["system"], r["device_type"]): r["quantity"] for r in sheet.outputs["schedule"]}
    assert by_sheet == by_count == {("cctv", "camera"): 1, ("fire_alarm", "manual_call_point"): 1,
                                    ("fire_alarm", "smoke_detector"): 3}


def test_takeoff_leaves_the_original_alone_and_adds_only_spi_layers(storage):
    before = storage.read("fp.dxf")
    r = takeoff_sheet(TakeoffSheetInput(document_id="d", storage_key="fp.dxf",
                                        symbol_map=SYMBOL_MAP, room_boundary_layers=["ROOM-BOUNDARY"],
                                        output_key="out/t.dxf"), storage)
    assert storage.read("fp.dxf") == before
    assert r.files[0].storage_key == "out/t.dxf"
    original = {e.dxf.handle for e in _open(storage, "fp.dxf").modelspace()}
    added = [e for e in _open(storage, "out/t.dxf").modelspace() if e.dxf.handle not in original]
    assert added and {e.dxf.layer for e in added} <= {TAKEOFF_LAYER, SCHEDULE_LAYER, ROOMS_LAYER}


def test_every_counted_device_is_ringed_and_tagged(storage):
    takeoff_sheet(TakeoffSheetInput(document_id="d", storage_key="fp.dxf", symbol_map=FULL_MAP,
                                    output_key="out/t.dxf"), storage)
    doc = _open(storage, "out/t.dxf")
    rings = [e for e in doc.modelspace().query("CIRCLE") if e.dxf.layer == TAKEOFF_LAYER]
    assert len(rings) == 7
    tags = _texts(doc, TAKEOFF_LAYER)
    assert tags.count("FA2") == 3          # smoke detector is FA2 (sorted after call point)
    assert "CC1" in tags


def test_unmapped_blocks_make_the_schedule_incomplete_not_short(storage):
    r = takeoff_sheet(TakeoffSheetInput(document_id="d", storage_key="fp.dxf",
                                        symbol_map=SYMBOL_MAP, output_key="out/t.dxf"), storage)
    assert r.status == "missing_data"
    assert {m.record for m in r.missing} == {"block:FD layer:MECH", "block:NORTH-ARROW layer:TITLE"}
    schedule_text = " ".join(_texts(_open(storage, "out/t.dxf"), SCHEDULE_LAYER))
    assert "NOT COUNTED" in schedule_text
    assert "INCOMPLETE" in schedule_text
    marks = _texts(_open(storage, "out/t.dxf"), TAKEOFF_LAYER)
    assert marks.count("?") == 2


def test_fully_mapped_takeoff_is_ok(storage):
    r = takeoff_sheet(TakeoffSheetInput(document_id="d", storage_key="fp.dxf",
                                        symbol_map=FULL_MAP, output_key="out/t.dxf"), storage)
    assert r.status == "ok"
    assert "INCOMPLETE" not in " ".join(_texts(_open(storage, "out/t.dxf"), SCHEDULE_LAYER))


def test_room_areas_are_written_in_square_metres(storage):
    r = takeoff_sheet(TakeoffSheetInput(document_id="d", storage_key="fp.dxf", symbol_map=FULL_MAP,
                                        room_boundary_layers=["ROOM-BOUNDARY"],
                                        room_label_layers=["ROOM-NAMES"],
                                        output_key="out/t.dxf"), storage)
    areas = sorted(x["area_m2"] for x in r.outputs["rooms"])
    assert areas == [4.0, 20.0]
    named = [x for x in r.outputs["rooms"] if x["named"]]
    assert [x["name"] for x in named] == ["OFFICE 101"]
    doc = _open(storage, "out/t.dxf")
    assert "20.00 m²" in _texts(doc, ROOMS_LAYER)
    assert len([e for e in doc.modelspace().query("HATCH") if e.dxf.layer == ROOMS_LAYER]) == 2


def test_unitless_rooms_get_no_area(storage):
    r = takeoff_sheet(TakeoffSheetInput(document_id="d", storage_key="unitless.dxf",
                                        symbol_map=FULL_MAP, room_boundary_layers=["ROOM-BOUNDARY"],
                                        output_key="out/t.dxf"), storage)
    assert r.status == "missing_data"
    assert all(x["area_m2"] is None for x in r.outputs["rooms"])
    assert any(m.field == "drawing_units" for m in r.missing)


def test_derived_text_height_is_an_assumption(storage):
    r = takeoff_sheet(TakeoffSheetInput(document_id="d", storage_key="fp.dxf",
                                        symbol_map=FULL_MAP, output_key="out/t.dxf"), storage)
    assert [a.key for a in r.assumptions] == ["text_height"]
    r2 = takeoff_sheet(TakeoffSheetInput(document_id="d", storage_key="fp.dxf", symbol_map=FULL_MAP,
                                         text_height=200, output_key="out/t2.dxf"), storage)
    assert r2.assumptions == []


# -------------------------------------------------------------------- sheet
def test_sheet_draws_frame_and_title_block_on_its_own_layer(storage):
    before = storage.read("fp.dxf")
    r = sheet_setup(SheetSetupInput(document_id="d", storage_key="fp.dxf", paper="A3",
                                    scale=100, title_block=TB, north_angle_deg=0,
                                    output_key="out/s.dxf"), storage)
    assert r.status == "ok", r.missing
    assert storage.read("fp.dxf") == before
    doc = _open(storage, "out/s.dxf")
    texts = _texts(doc, SHEET_LAYER)
    for v in ("SPT-FA-101", "1:100", "Ground floor fire alarm layout", "N", "A3 · ISO 5457 / ISO 7200"):
        assert v in texts
    original = {e.dxf.handle for e in _open(storage, "fp.dxf").modelspace()}
    added = {e.dxf.layer for e in doc.modelspace() if e.dxf.handle not in original}
    assert added == {SHEET_LAYER}


def test_sheet_frame_is_paper_size_times_scale(storage):
    sheet_setup(SheetSetupInput(document_id="d", storage_key="fp.dxf", paper="A3",
                                scale=100, title_block=TB, output_key="out/s.dxf"), storage)
    polys = [e for e in _open(storage, "out/s.dxf").modelspace().query("LWPOLYLINE")
             if e.dxf.layer == SHEET_LAYER]
    widths = sorted({round(max(p[0] for p in e.get_points("xy")) - min(p[0] for p in e.get_points("xy")))
                     for e in polys}, reverse=True)
    assert widths[0] == 42000      # 420 mm × 100, drawing in millimetres
    assert widths[1] == 39000      # frame: 420 − 20 − 10


def test_missing_iso7200_fields_are_flagged_not_left_blank(storage):
    tb = TB.model_copy(update={"approved_by": None, "drawing_number": " "})
    r = sheet_setup(SheetSetupInput(document_id="d", storage_key="fp.dxf", paper="A3",
                                    scale=100, title_block=tb, output_key="out/s.dxf"), storage)
    assert r.status == "missing_data"
    assert {m.field for m in r.missing} == {"title_block.approved_by", "title_block.drawing_number"}
    assert _texts(_open(storage, "out/s.dxf"), SHEET_LAYER).count("MISSING") == 2


def test_unitless_drawing_cannot_be_scaled(storage):
    r = sheet_setup(SheetSetupInput(document_id="d", storage_key="unitless.dxf", paper="A3",
                                    scale=100, title_block=TB, output_key="out/s.dxf"), storage)
    assert r.status == "missing_data"
    assert r.files == []
    assert not storage.exists("out/s.dxf")


def test_no_bearing_means_no_north_arrow(storage):
    r = sheet_setup(SheetSetupInput(document_id="d", storage_key="fp.dxf", paper="A3",
                                    scale=100, title_block=TB, output_key="out/s.dxf"), storage)
    assert r.outputs["north_arrow"] is False
    assert "N" not in _texts(_open(storage, "out/s.dxf"), SHEET_LAYER)
    assert any(f.code == "SHEET-NO-NORTH" for f in r.findings)


def test_drawing_too_big_for_the_sheet_suggests_a_fit(storage):
    # The rooms span 8 m × 4 m. At 1:20 that is 400 mm wide; A3 has 390 mm.
    r = sheet_setup(SheetSetupInput(document_id="d", storage_key="fp.dxf", paper="A3",
                                    scale=20, title_block=TB, output_key="out/s.dxf"), storage)
    assert r.outputs["fits"] is False
    f = next(f for f in r.findings if f.code == "SHEET-DOES-NOT-FIT")
    assert f.severity == "review"
    assert r.outputs["suggestion"] == {"scale": 25, "paper_at_this_scale": "A2"}
