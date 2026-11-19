"""BIMCraft tests.

The office fixture (fixtures/revit_elv_office.py) is written the way Revit's IFC
exporter writes a model; no client Revit model has been supplied. The small
inline models below each isolate one export habit.
"""
from __future__ import annotations

import importlib.util
import io
import json
import math
import sys
import zipfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from craft.bim import (CountInput, ElementMap, ReadIfcInput, SceneInput,
                       SpacesInput, count_devices, extract_spaces, open_ifc,
                       read_ifc, scene_3d)
from craft.bim.step import Enum, Ref, StepFile, Typed, parse_args
from craft.core import InvalidInput, LocalStorage

ENGINES = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "revit_elv_office", ENGINES / "fixtures" / "revit_elv_office.py")
office = importlib.util.module_from_spec(_spec)
sys.modules["revit_elv_office"] = office     # dataclasses look their module up here
_spec.loader.exec_module(office)
SPT_MAP = json.loads((ENGINES / "fixtures" / "spt_element_map.json").read_text())


@pytest.fixture
def store(tmp_path):
    s = LocalStorage(tmp_path)
    s.write("office4.ifc", office.build("IFC4").encode())
    s.write("office2x3.ifc", office.build("IFC2X3").encode())
    return s


def _ifc(data: str, schema: str = "IFC4") -> str:
    return ("ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION((''),'2;1');\n"
            "FILE_NAME('t.ifc','',(''),(''),'','','');\n"
            f"FILE_SCHEMA(('{schema}'));\nENDSEC;\nDATA;\n{data}\nENDSEC;\n"
            "END-ISO-10303-21;\n")


def _put(store: LocalStorage, key: str, text: str) -> str:
    store.write(key, text.encode())
    return key


# -- the STEP reader ---------------------------------------------------------

def test_step_values_decode_to_the_right_python_types():
    v = parse_args("('a;b(c)','it''s',$,*,.T.,#12,-1.5E2,7,IFCLABEL('x'),((1,2),(3,4)),\"0F\")")
    assert v[:3] == ["a;b(c)", "it's", None]
    assert v[3] is None
    assert isinstance(v[4], Enum) and v[4] == "T"
    assert isinstance(v[5], Ref) and int(v[5]) == 12
    assert v[6] == -150.0 and v[7] == 7 and isinstance(v[7], int)
    assert v[8] == Typed("IFCLABEL", "x")
    assert v[9] == [[1, 2], [3, 4]]


def test_step_string_escapes_including_arabic():
    assert parse_args(r"('\X2\063A\X0\\X2\0631\X0\')") == ["غر"]
    assert parse_args(r"('\X\E9t\S\i')") == ["été"]
    assert parse_args(r"('a\\b')") == ["a\\b"]


def test_semicolons_inside_strings_and_comments_do_not_split_statements():
    f = StepFile(_ifc("/* a; comment */\n#1=IFCLABELLED('x;y','(z');\n#2=IFCTHING(#1);"))
    assert f.get(1).args == ["x;y", "(z"]
    assert f.get(2).args == [Ref(1)]


def test_malformed_argument_list_is_invalid_input_not_a_crash():
    f = StepFile(_ifc("#1=IFCTHING((1,2);"))
    with pytest.raises(InvalidInput):
        f.get(1)


def test_reference_to_a_missing_instance_is_none():
    f = StepFile(_ifc("#1=IFCTHING(#99);"))
    assert f.get(f.get(1).arg(0)) is None


# -- what is and is not an IFC file -------------------------------------------

def test_native_revit_file_is_refused_with_the_export_route(tmp_path):
    s = LocalStorage(tmp_path)
    s.write("model.rvt", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64)
    with pytest.raises(InvalidInput, match=r"native Revit file.*File → Export → IFC"):
        read_ifc(ReadIfcInput(document_id="d", storage_key="model.rvt"), storage=s)


@pytest.mark.parametrize("raw, why", [
    (b"<?xml version='1.0'?><ifcXML/>", "ifcXML"),
    (b"just some text", "does not start with ISO-10303-21"),
    (_ifc("", schema="AUTOMOTIVE_DESIGN").encode(), "not IFC"),
])
def test_other_files_are_refused_with_a_reason(tmp_path, raw, why):
    s = LocalStorage(tmp_path)
    s.write("x.ifc", raw)
    with pytest.raises(InvalidInput, match=why):
        read_ifc(ReadIfcInput(document_id="d", storage_key="x.ifc"), storage=s)


def test_ifczip_is_read(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("Model.ifc", office.build("IFC4"))
    s = LocalStorage(tmp_path)
    s.write("model.ifczip", buf.getvalue())
    out = read_ifc(ReadIfcInput(document_id="d", storage_key="model.ifczip"), storage=s).outputs
    assert out["schema"] == "IFC4" and len(out["storeys"]) == 2


# -- inventory ----------------------------------------------------------------

def test_inventory_identifies_revit_from_the_application_record(store):
    out = read_ifc(ReadIfcInput(document_id="d", storage_key="office4.ifc"), storage=store).outputs
    # Revit's FILE_NAME header names its exporter add-in, never "Revit".
    assert "Revit" not in out["originating_system"]
    assert out["is_revit_export"] is True
    assert out["authoring_application"].startswith("Autodesk Revit 2024")
    assert out["units"]["length"] == {"name": "millimetre", "metres_per_unit": 0.001}
    assert [(s["name"], s["elevation_m"]) for s in out["storeys"]] == [("Level 1", 0.0), ("Level 2", 4.0)]
    assert out["element_classes"]["IFCBUILDINGELEMENTPROXY"] == 10


def test_feet_are_converted_through_the_conversion_based_unit(tmp_path):
    s = LocalStorage(tmp_path)
    key = _put(s, "ft.ifc", _ifc(
        "#1=IFCSIUNIT(*,.LENGTHUNIT.,$,.METRE.);"
        "#2=IFCDIMENSIONALEXPONENTS(1,0,0,0,0,0,0);"
        "#3=IFCMEASUREWITHUNIT(IFCLENGTHMEASURE(0.3048),#1);"
        "#4=IFCCONVERSIONBASEDUNIT(#2,.LENGTHUNIT.,'FOOT',#3);"
        "#5=IFCUNITASSIGNMENT((#4));"
        "#6=IFCPROJECT('p',$,'P',$,$,$,$,$,#5);", schema="IFC2X3"))
    out = read_ifc(ReadIfcInput(document_id="d", storage_key=key), storage=s).outputs
    assert out["units"]["length"] == {"name": "foot", "metres_per_unit": 0.3048}


# -- counting ------------------------------------------------------------------

def test_default_map_counts_standard_types_and_reports_the_rest(store):
    res = count_devices(CountInput(document_id="d", storage_key="office4.ifc"), storage=store)
    counts = {c["device_type"]: c["quantity"] for c in res.outputs["counts"]}
    assert counts == {"smoke_detector": 24, "manual_call_point": 4, "camera": 5, "data_outlet": 3}
    # Proxies and USERDEFINED elements are gaps, not zeros: the count says so.
    assert res.status == "missing_data"
    gaps = {(u["ifc_class"], u["type_name"]): u["count"] for u in res.outputs["unmapped_elements"]}
    assert gaps == {("IFCBUILDINGELEMENTPROXY", "SPT_FA_Sounder_Beacon:Wall"): 7,
                    ("IFCBUILDINGELEMENTPROXY", "SPT_ACS_CardReader:Mullion"): 3,
                    ("IFCCOMMUNICATIONSAPPLIANCE", "Wireless Access Point"): 6}
    assert all(m.field == "element_mapping" for m in res.missing)
    # Power outlets are ignored by a rule, and say so rather than vanishing.
    assert res.outputs["ignored_elements"][0]["count"] == 3


def test_project_map_resolves_family_names(store):
    res = count_devices(CountInput(document_id="d", storage_key="office4.ifc",
                                   element_map=SPT_MAP), storage=store)
    assert res.status == "ok"
    counts = {c["device_type"]: c["quantity"] for c in res.outputs["counts"]}
    assert counts["sounder_strobe"] == 7 and counts["card_reader"] == 3
    assert counts["wireless_access_point"] == 6
    by = {(c["storey"], c["device_type"]): c["quantity"] for c in res.outputs["counts_by_storey"]}
    assert by[("Level 1", "smoke_detector")] == 8 and by[("Level 2", "smoke_detector")] == 16
    assert all(o["review_status"] == "pending" and o["source"] == "imported"
               for o in res.outputs["objects"])
    assert res.provenance and "SPT demo family naming@0.1" in res.provenance[0].source


def test_ifc2x3_detectors_are_identified_by_their_type_object(store):
    res = count_devices(CountInput(document_id="d", storage_key="office2x3.ifc",
                                   element_map=SPT_MAP), storage=store)
    counts = {c["device_type"]: c["quantity"] for c in res.outputs["counts"]}
    assert counts == {"smoke_detector": 24, "manual_call_point": 4, "sounder_strobe": 7}
    first = res.outputs["objects"][0]["extracted_value"]
    assert first["ifc_class"] == "IFCSENSOR" and first["predefined_type"] == "SMOKESENSOR"


def test_storey_filter(store):
    res = count_devices(CountInput(document_id="d", storage_key="office4.ifc",
                                   element_map=SPT_MAP, storeys=["level 2"]), storage=store)
    assert {c["storey"] for c in res.outputs["counts_by_storey"]} == {"Level 2"}


# -- positions -----------------------------------------------------------------

def test_positions_are_world_metres_with_rotation(store):
    res = count_devices(CountInput(document_id="d", storage_key="office4.ifc",
                                   element_map=SPT_MAP), storage=store)
    cams = [o for o in res.outputs["objects"] if o["object_type"] == "camera"]
    first = cams[0]
    assert first["geometry"]["coordinates"] == [0.3, 0.3, 2.7]
    assert first["extracted_value"]["yaw_deg"] == 45.0
    up = [o for o in res.outputs["objects"]
          if o["extracted_value"]["storey"] == "Level 2"][0]
    assert up["geometry"]["coordinates"][2] == pytest.approx(6.8)   # 4.0 storey + 2.8


def test_family_placed_through_a_mapped_item_is_located_from_the_transform(store):
    res = count_devices(CountInput(document_id="d", storage_key="office4.ifc",
                                   element_map=SPT_MAP), storage=store)
    baked = [o for o in res.outputs["objects"]
             if o["extracted_value"]["position_basis"] == "geometry"]
    assert len(baked) == 1
    assert baked[0]["geometry"]["coordinates"] == [6.5, 8.0, 2.8]


def test_location_baked_into_geometry_with_a_cancelling_storey_offset(tmp_path):
    # Revit: storey at 3140 mm, element offset (0,0,-3140) lands on the origin,
    # and the real location is the extrusion's own position.
    s = LocalStorage(tmp_path)
    key = _put(s, "baked.ifc", _ifc(
        "#1=IFCSIUNIT(*,.LENGTHUNIT.,.MILLI.,.METRE.);#2=IFCUNITASSIGNMENT((#1));"
        "#3=IFCPROJECT('p',$,'P',$,$,$,$,$,#2);"
        "#10=IFCCARTESIANPOINT((0.,0.,0.));#11=IFCAXIS2PLACEMENT3D(#10,$,$);"
        "#12=IFCCARTESIANPOINT((0.,0.,3140.));#13=IFCAXIS2PLACEMENT3D(#12,$,$);"
        "#14=IFCLOCALPLACEMENT($,#13);"
        "#15=IFCBUILDINGSTOREY('s',$,'Level 2',$,$,#14,$,$,.ELEMENT.,3140.);"
        "#16=IFCCARTESIANPOINT((0.,0.,-3140.));#17=IFCAXIS2PLACEMENT3D(#16,$,$);"
        "#18=IFCLOCALPLACEMENT(#14,#17);"
        "#20=IFCCARTESIANPOINT((0.,0.));#21=IFCAXIS2PLACEMENT2D(#20,$);"
        "#22=IFCRECTANGLEPROFILEDEF(.AREA.,$,#21,100.,100.);"
        "#23=IFCCARTESIANPOINT((-25041.4,102372.8,3195.2));#24=IFCAXIS2PLACEMENT3D(#23,$,$);"
        "#25=IFCDIRECTION((0.,0.,1.));#26=IFCEXTRUDEDAREASOLID(#22,#24,#25,50.);"
        "#27=IFCSHAPEREPRESENTATION($,'Body','SweptSolid',(#26));"
        "#28=IFCPRODUCTDEFINITIONSHAPE($,$,(#27));"
        "#30=IFCSENSOR('d',$,'Det:Ceiling:1',$,$,#18,#28,'1',.SMOKESENSOR.);"
        "#31=IFCRELCONTAINEDINSPATIALSTRUCTURE('r',$,$,$,(#30),#15);"))
    res = count_devices(CountInput(document_id="d", storage_key=key), storage=s)
    obj = res.outputs["objects"][0]
    assert obj["geometry"]["coordinates"] == [-25.0414, 102.3728, 3.1952]
    assert obj["extracted_value"]["position_basis"] == "geometry"


def test_cyclic_placement_does_not_hang_and_gives_no_position(tmp_path):
    s = LocalStorage(tmp_path)
    key = _put(s, "cyc.ifc", _ifc(
        "#1=IFCSIUNIT(*,.LENGTHUNIT.,$,.METRE.);#2=IFCUNITASSIGNMENT((#1));"
        "#3=IFCPROJECT('p',$,'P',$,$,$,$,$,#2);"
        "#10=IFCCARTESIANPOINT((1.,2.,3.));#11=IFCAXIS2PLACEMENT3D(#10,$,$);"
        "#12=IFCLOCALPLACEMENT(#13,#11);#13=IFCLOCALPLACEMENT(#12,#11);"
        "#20=IFCSENSOR('d',$,'Det',$,$,#12,$,'1',.SMOKESENSOR.);"))
    res = count_devices(CountInput(document_id="d", storage_key=key), storage=s)
    assert res.outputs["objects"][0]["geometry"] is None
    assert any("no storey" in w for w in res.warnings)


# -- rooms -----------------------------------------------------------------------

def test_room_areas_come_from_the_model_or_are_missing(store):
    res = extract_spaces(SpacesInput(document_id="d", storage_key="office4.ifc"), storage=store)
    rooms = {s["number"]: s for s in res.outputs["spaces"]}
    assert rooms["101"]["area_m2"] == 48.0
    assert rooms["101"]["area_source"] == "quantity BaseQuantities.NetFloorArea"
    assert rooms["103"]["area_source"] == "property PSet_Revit_Dimensions.Area"
    assert rooms["104"]["name"] == "غرفة الخوادم"
    # The lobby has an outline but no area quantity: missing, never computed here.
    assert rooms["105"]["area_m2"] is None
    assert res.status == "missing_data"
    assert [m.record for m in res.missing] == ["space:105 Lobby"]
    assert {b["storey"]: b["space_count"] for b in res.outputs["by_storey"]} == {"Level 1": 5, "Level 2": 4}


# -- scene -----------------------------------------------------------------------

def test_scene_outlines_heights_and_rooms_of_devices(store):
    res = scene_3d(SceneInput(document_id="d", storage_key="office4.ifc",
                              element_map=SPT_MAP), storage=store)
    out = res.outputs
    rooms = {s["number"]: s for s in out["spaces"]}
    assert all(s["footprint_m"] for s in out["spaces"])
    assert rooms["102"]["height_m"] == 2.8 and rooms["201"]["base_z_m"] == 4.0
    # The outline of a rectangular room agrees with its exported quantity.
    assert rooms["102"]["outline_area_m2"] == pytest.approx(rooms["102"]["area_m2"])
    # Revit puts devices in the storey; the scene finds the room they sit in.
    det = next(d for d in out["devices"] if d["x_m"] == 12.0 and d["y_m"] == 3.5)
    assert det["space"] == "102 Open Office" and det["space_basis"] == "located"
    assert len([c for c in out["context"] if c["kind"] == "wall"]) == 15
    assert out["bounds_m"]["max"][2] == pytest.approx(8.0)
    assert res.status == "ok"
    assert [f.code for f in res.findings] == ["DEVICE-POSITION-FROM-GEOMETRY"]


def test_curved_room_outline_follows_the_arc(store):
    res = scene_3d(SceneInput(document_id="d", storage_key="office4.ifc",
                              element_map=SPT_MAP), storage=store)
    lobby = next(s for s in res.outputs["spaces"] if s["number"] == "105")
    # 8 m x 4 m rectangle plus the circular segment of chord 8 m, sagitta 1.5 m.
    r = (4 ** 2 + 1.5 ** 2) / (2 * 1.5)
    half = math.asin(4 / r)
    exact = 32 + r * r * (2 * half - math.sin(2 * half)) / 2
    assert lobby["outline_area_m2"] == pytest.approx(exact, rel=1e-3)


def test_scene_refuses_a_model_with_no_length_unit(tmp_path):
    s = LocalStorage(tmp_path)
    key = _put(s, "nounit.ifc", _ifc("#1=IFCPROJECT('p',$,'P',$,$,$,$,$,$);"))
    with pytest.raises(InvalidInput, match="no usable length unit"):
        scene_3d(SceneInput(document_id="d", storage_key=key), storage=s)


# -- the element map is data with an origin ---------------------------------------

def test_element_map_needs_an_origin_and_complete_rules():
    with pytest.raises(ValidationError):
        ElementMap.load({"name": "x", "version": "1", "source_document": " ",
                         "rules": [{"ifc_class": "IfcSensor", "system": "fa", "device_type": "sd"}]})
    with pytest.raises(ValidationError):
        ElementMap.load({"name": "x", "version": "1", "source_document": "doc",
                         "rules": [{"ifc_class": "IfcSensor"}]})
    with pytest.raises(ValidationError):
        ElementMap.load({"name": "x", "version": "1", "source_document": "doc",
                         "rules": [{"system": "fa", "device_type": "sd"}]})
    ok = ElementMap.load({"name": "x", "version": "1", "source_document": "doc",
                          "rules": [{"ifc_class": "IfcOutlet", "ignore": True}]})
    assert ok.rules[0].ignore


def test_revit_element_id_suffix_does_not_defeat_an_exact_name_rule(store):
    m = {"name": "x", "version": "1", "source_document": "doc", "rules": [
        {"name": "SPT_FA_Sounder_Beacon:Wall", "system": "fire_alarm", "device_type": "sounder"}]}
    res = count_devices(CountInput(document_id="d", storage_key="office4.ifc", element_map=m,
                                   classes=["IfcBuildingElementProxy"]), storage=store)
    assert {c["device_type"]: c["quantity"] for c in res.outputs["counts"]} == {"sounder": 7}
