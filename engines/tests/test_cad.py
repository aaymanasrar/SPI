"""CADCraft tests.

Fixtures are synthesised with ezdxf and are explicitly not how a consultant
draws — see docs/data-requests/craft-engines.md 6. They exercise the decisions,
not real draughting.
"""
from __future__ import annotations

import io

import ezdxf
import pytest
from pydantic import ValidationError

from craft.cad import (MARKUP_LAYER, CountInput, default_map, MarkupInput, Note, ReadDxfInput,
                       RoomsInput, SymbolMap, count_devices, extract_rooms,
                       markup, measure_route, place_devices, read_dxf)
from craft.cad.place import MeasureRouteInput
from craft.cad.rooms import point_in_polygon, polygon_area
from craft.core import InvalidInput, LocalStorage

SYMBOL_MAP = {
    "name": "PLACEHOLDER client standard",
    "version": "0.1",
    "source_document": "PLACEHOLDER — no real drawing standard supplied yet",
    "rules": [
        {"block": "SD", "layer": "FA-DEVICES", "system": "fire_alarm",
         "device_type": "smoke_detector"},
        {"block": "MCP", "layer": "FA-DEVICES", "system": "fire_alarm",
         "device_type": "manual_call_point"},
        {"block": "CAM-.*", "is_regex": True, "system": "cctv",
         "device_type": "camera"},
    ],
}


def _dxf(insunits: int = 4) -> bytes:
    d = ezdxf.new("R2010", setup=True)
    d.header["$INSUNITS"] = insunits
    for b in ("SD", "MCP", "CAM-FIXED", "FD", "NORTH-ARROW"):
        d.blocks.new(b)
    for layer in ("FA-DEVICES", "CCTV", "MECH", "TITLE", "ROOM-BOUNDARY",
                  "ROOM-NAMES"):
        d.layers.add(layer)
    m = d.modelspace()
    for i in range(3):
        m.add_blockref("SD", (1000 + i * 1000, 2000),
                       dxfattribs={"layer": "FA-DEVICES"})
    m.add_blockref("MCP", (500, 500), dxfattribs={"layer": "FA-DEVICES"})
    m.add_blockref("CAM-FIXED", (4000, 3000), dxfattribs={"layer": "CCTV"})
    m.add_blockref("FD", (2000, 100), dxfattribs={"layer": "MECH"})        # unmapped
    m.add_blockref("NORTH-ARROW", (0, 9000), dxfattribs={"layer": "TITLE"})  # unmapped
    # Two rooms, 5m x 4m and 2m x 2m, in millimetres.
    m.add_lwpolyline([(0, 0), (5000, 0), (5000, 4000), (0, 4000)], close=True,
                     dxfattribs={"layer": "ROOM-BOUNDARY"})
    m.add_lwpolyline([(6000, 0), (8000, 0), (8000, 2000), (6000, 2000)], close=True,
                     dxfattribs={"layer": "ROOM-BOUNDARY"})
    m.add_text("OFFICE 101", dxfattribs={"layer": "ROOM-NAMES"}).set_placement((2000, 2000))
    s = io.StringIO()
    d.write(s)
    return s.getvalue().encode("utf-8")


@pytest.fixture
def storage(tmp_path):
    s = LocalStorage(tmp_path)
    s.write("fp.dxf", _dxf())
    s.write("unitless.dxf", _dxf(insunits=0))
    return s


# --------------------------------------------------------------------- read
def test_read_reports_layers_blocks_and_inserts(storage):
    r = read_dxf(ReadDxfInput(document_id="d", storage_key="fp.dxf"), storage)
    assert r.status == "ok"
    assert "FA-DEVICES" in r.outputs["layers"]
    assert "SD" in r.outputs["block_definitions"]
    assert r.outputs["insert_total"] == 7
    sd = next(i for i in r.outputs["inserts"] if i["block"] == "SD")
    assert sd["count"] == 3


def test_read_resolves_units(storage):
    r = read_dxf(ReadDxfInput(document_id="d", storage_key="fp.dxf"), storage)
    assert r.outputs["units"] == {"insunits": 4, "name": "millimetres",
                                 "metres_per_unit": 0.001}
    assert r.warnings == []


def test_read_warns_when_the_drawing_has_no_units(storage):
    r = read_dxf(ReadDxfInput(document_id="d", storage_key="unitless.dxf"), storage)
    assert r.outputs["units"]["metres_per_unit"] is None
    assert any("no units" in w for w in r.warnings)


def test_read_flags_entities_on_layers_with_no_layer_table_record(storage):
    """ezdxf lets an entity name a layer that was never created; a layer filter
    matches on the entity's name, so both lists have to be reported."""
    d = ezdxf.new("R2010", setup=True)
    d.header["$INSUNITS"] = 4
    d.blocks.new("SD")
    d.modelspace().add_blockref("SD", (0, 0), dxfattribs={"layer": "GHOST-LAYER"})
    s = io.StringIO(); d.write(s)
    storage.write("ghost.dxf", s.getvalue().encode())
    r = read_dxf(ReadDxfInput(document_id="d", storage_key="ghost.dxf"), storage)
    assert "GHOST-LAYER" not in r.outputs["layers"]
    assert "GHOST-LAYER" in r.outputs["entity_layers"]
    assert any("no record in the layer table" in w for w in r.warnings)


def test_read_lists_both_declared_and_used_layers(storage):
    r = read_dxf(ReadDxfInput(document_id="d", storage_key="fp.dxf"), storage)
    assert "FA-DEVICES" in r.outputs["layers"]
    assert "FA-DEVICES" in r.outputs["entity_layers"]
    # Declared in the fixture but carrying no entity.
    assert "Defpoints" in r.outputs["layers"]
    assert "Defpoints" not in r.outputs["entity_layers"]


def test_read_rejects_a_file_that_is_not_dxf(storage):
    storage.write("fake.dwg", b"AC1032" + b"\x00" * 200)
    with pytest.raises(InvalidInput) as e:
        read_dxf(ReadDxfInput(document_id="d", storage_key="fake.dwg"), storage)
    assert "DWG" in str(e.value)


# ------------------------------------------------------------------ symbols
def test_symbol_map_requires_a_stated_origin():
    bad = dict(SYMBOL_MAP, source_document="  ")
    with pytest.raises(ValidationError):
        SymbolMap.load(bad)


def test_symbol_map_rejects_an_empty_rule_list():
    with pytest.raises(ValidationError):
        SymbolMap.load(dict(SYMBOL_MAP, rules=[]))


def test_symbol_map_rejects_malformed_json():
    with pytest.raises(InvalidInput):
        SymbolMap.load("{not json")


def test_symbol_rule_order_is_precedence():
    m = SymbolMap.load({
        "name": "t", "version": "1", "source_document": "test",
        "rules": [
            {"block": "SD", "layer": "FA-SPECIAL", "system": "fire_alarm",
             "device_type": "duct_detector"},
            {"block": "SD", "system": "fire_alarm", "device_type": "smoke_detector"},
        ]})
    assert m.resolve("SD", "FA-SPECIAL").device_type == "duct_detector"
    assert m.resolve("SD", "FA-DEVICES").device_type == "smoke_detector"


def test_symbol_rule_matching_ignores_case_and_supports_regex():
    m = SymbolMap.load(SYMBOL_MAP)
    assert m.resolve("sd", "fa-devices").device_type == "smoke_detector"
    assert m.resolve("CAM-PTZ", "anything").device_type == "camera"
    assert m.resolve("FD", "MECH") is None


# ------------------------------------------------------------ default map
DESCRIPTIVE = [
    ("SMOKE-DETECTOR", "smoke_detector"), ("smoke_det", "smoke_detector"),
    ("OPTICAL-SMOKE-DETECTOR", "smoke_detector"),
    ("HEAT-DETECTOR", "heat_detector"), ("DUCT-SMOKE-DETECTOR", "duct_detector"),
    ("MANUAL-CALL-POINT", "manual_call_point"), ("BREAK-GLASS", "manual_call_point"),
    ("SOUNDER", "sounder"), ("SOUNDER-STROBE", "sounder_strobe"),
    ("FACP", "fire_alarm_panel"), ("FIRE-ALARM-PANEL", "fire_alarm_panel"),
    ("CAMERA", "camera"), ("DOME-CAMERA", "camera"), ("PTZ-CAMERA", "ptz_camera"),
    ("NVR", "recorder"), ("CARD-READER", "card_reader"),
    ("DOOR-CONTACT", "door_contact"), ("MAGLOCK", "magnetic_lock"),
    ("REX", "exit_button"), ("DATA-OUTLET", "data_outlet"), ("RJ45", "data_outlet"),
    ("WAP", "wireless_access_point"), ("ACCESS-POINT", "wireless_access_point"),
    ("PATCH-PANEL", "patch_panel"), ("CEILING-SPEAKER", "speaker"),
]


@pytest.mark.parametrize("block,expected", DESCRIPTIVE)
def test_default_map_reads_descriptive_block_names(block, expected):
    rule = default_map().resolve(block, "ANY-LAYER")
    assert rule is not None, f"{block} unmapped"
    assert rule.device_type == expected


# Each of these would be a plausible-looking wrong answer.
@pytest.mark.parametrize("block", [
    "SD", "FD", "HD", "MCP", "CP", "AP", "DC", "EL", "PB", "TS", "SW", "BG", "VC",
    "PANEL", "FACEPLATE", "CONTROLLER", "CONTACT",
])
def test_default_map_refuses_ambiguous_codes(block):
    """A wrong mapping is worse than a missing one: it produces a confident
    count instead of missing_data, and nobody looks again."""
    m = default_map()
    assert m.resolve(block, "FA-DEVICES") is None, f"{block} was guessed"


@pytest.mark.parametrize("block", [
    "SD", "FD", "MCP", "PANEL", "FACEPLATE", "CONTROLLER",
])
def test_every_refused_code_explains_itself(block):
    note = default_map().ambiguity_note(block)
    assert note and len(note) > 20, block


def test_ambiguity_note_matches_a_prefixed_block_name():
    """Drawings name blocks SD-01, FD_02; the code is still the ambiguous part."""
    m = default_map()
    assert m.ambiguity_note("SD-01")
    assert m.ambiguity_note("FD_02")
    assert m.ambiguity_note("SMOKE-DETECTOR") is None


def test_default_map_states_it_is_not_a_client_standard():
    src = default_map().source_document
    assert "NOT a client drawing standard" in src
    assert "legend" in src


def test_default_map_rules_are_all_valid_regexes():
    import re
    for rule in default_map().rules:
        assert rule.is_regex
        re.compile(rule.block)          # raises if malformed


def test_no_default_rule_matches_an_empty_or_furniture_block():
    m = default_map()
    for block in ("", " ", "NORTH-ARROW", "TITLE-BLOCK", "GRID-BUBBLE",
                  "SCALE-BAR", "REVISION-CLOUD", "DIM-STYLE"):
        assert m.resolve(block, "TITLE") is None, block


# -------------------------------------------------------------------- count
def test_count_tallies_mapped_devices(storage):
    r = count_devices(CountInput(document_id="d", storage_key="fp.dxf",
                                 symbol_map=SYMBOL_MAP), storage)
    got = {(c["system"], c["device_type"]): c["quantity"] for c in r.outputs["counts"]}
    assert got == {("fire_alarm", "smoke_detector"): 3,
                   ("fire_alarm", "manual_call_point"): 1,
                   ("cctv", "camera"): 1}


def test_unmapped_block_makes_the_whole_count_missing_data(storage):
    """A partial count that looks complete is the failure this prevents."""
    r = count_devices(CountInput(document_id="d", storage_key="fp.dxf",
                                 symbol_map=SYMBOL_MAP), storage)
    assert r.status == "missing_data"
    assert r.outputs["unmapped_insert_count"] == 2
    blocks = {m.record for m in r.missing}
    assert "block:FD layer:MECH" in blocks
    assert all(m.field == "symbol_mapping" for m in r.missing)
    # The tallies are still there, so the cost of the gap is visible.
    assert r.outputs["mapped_insert_count"] == 5


def test_count_is_ok_once_every_block_is_mapped(storage):
    full = dict(SYMBOL_MAP)
    full["rules"] = SYMBOL_MAP["rules"] + [
        {"block": "FD", "system": "mechanical", "device_type": "fire_damper"},
        {"block": "NORTH-ARROW", "system": "annotation",
         "device_type": "drawing_furniture"},
    ]
    r = count_devices(CountInput(document_id="d", storage_key="fp.dxf",
                                 symbol_map=full), storage)
    assert r.status == "ok"
    assert r.missing == []


def test_count_emits_drawing_objects_ready_rows(storage):
    r = count_devices(CountInput(document_id="d", storage_key="fp.dxf",
                                 symbol_map=SYMBOL_MAP,
                                 drawing_page_id="11111111-1111-1111-1111-111111111111"),
                      storage)
    o = next(o for o in r.outputs["objects"] if o["object_type"] == "smoke_detector")
    assert o["source"] == "imported"
    assert o["review_status"] == "pending"
    # An exact mapping lookup is not an inference; a score here would be theatre.
    assert o["confidence"] is None
    assert o["geometry"]["type"] == "Point"
    assert o["drawing_page_id"] == "11111111-1111-1111-1111-111111111111"
    assert "fp.dxf#SD@FA-DEVICES" == o["source_reference"]


def test_count_records_the_symbol_map_in_provenance(storage):
    r = count_devices(CountInput(document_id="d", storage_key="fp.dxf",
                                 symbol_map=SYMBOL_MAP), storage)
    assert r.provenance
    assert all("PLACEHOLDER" in p.source for p in r.provenance)
    assert any("0.1" in p.source for p in r.provenance)


def test_count_can_be_restricted_to_layers(storage):
    r = count_devices(CountInput(document_id="d", storage_key="fp.dxf",
                                 symbol_map=SYMBOL_MAP, layers=["CCTV"]), storage)
    assert r.outputs["counts"] == [{"system": "cctv", "device_type": "camera",
                                   "unit": "no", "quantity": 1}]


def test_count_falls_back_to_the_default_map(storage):
    """symbol_map omitted uses the generic default rather than refusing."""
    r = count_devices(CountInput(document_id="d", storage_key="fp.dxf"), storage)
    assert r.outputs["symbol_map"]["name"] == "Generic ELV drawing conventions"
    # The fixture uses SD/MCP/FD, every one of them an ambiguous code, so the
    # default map maps nothing and says so.
    assert r.status == "missing_data"
    assert r.outputs["mapped_insert_count"] == 0
    notes = " ".join(m.note for m in r.missing)
    assert "deliberately does not interpret" in notes
    assert "legend sheet" in notes


def test_default_map_counts_a_drawing_that_uses_descriptive_names(storage, tmp_path):
    d = ezdxf.new("R2010", setup=True)
    d.header["$INSUNITS"] = 4
    for b in ("SMOKE-DETECTOR", "MANUAL-CALL-POINT", "DOME-CAMERA"):
        d.blocks.new(b)
    d.layers.add("FA-DEVICES")
    m = d.modelspace()
    for i in range(4):
        m.add_blockref("SMOKE-DETECTOR", (i * 1000, 0), dxfattribs={"layer": "FA-DEVICES"})
    m.add_blockref("MANUAL-CALL-POINT", (0, 500), dxfattribs={"layer": "FA-DEVICES"})
    m.add_blockref("DOME-CAMERA", (0, 900), dxfattribs={"layer": "CCTV"})
    s = io.StringIO(); d.write(s)
    storage.write("descriptive.dxf", s.getvalue().encode())

    r = count_devices(CountInput(document_id="d", storage_key="descriptive.dxf"), storage)
    assert r.status == "ok"
    got = {(c["system"], c["device_type"]): c["quantity"] for c in r.outputs["counts"]}
    assert got == {("fire_alarm", "smoke_detector"): 4,
                   ("fire_alarm", "manual_call_point"): 1,
                   ("cctv", "camera"): 1}


def test_count_writes_no_file(storage):
    r = count_devices(CountInput(document_id="d", storage_key="fp.dxf",
                                 symbol_map=SYMBOL_MAP), storage)
    assert r.files == []


# -------------------------------------------------------------------- rooms
def test_shoelace_area():
    assert polygon_area([(0, 0), (4, 0), (4, 3), (0, 3)]) == 12.0
    assert polygon_area([(0, 0), (1, 1)]) == 0.0
    # Wound the other way, same area.
    assert polygon_area([(0, 3), (4, 3), (4, 0), (0, 0)]) == 12.0


def test_point_in_polygon():
    sq = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert point_in_polygon(5, 5, sq)
    assert not point_in_polygon(15, 5, sq)
    assert not point_in_polygon(-1, -1, sq)


def test_rooms_converts_area_to_square_metres(storage):
    r = extract_rooms(RoomsInput(document_id="d", storage_key="fp.dxf",
                                 boundary_layers=["ROOM-BOUNDARY"]), storage)
    areas = sorted(x["area_m2"] for x in r.outputs["rooms"])
    assert areas == [4.0, 20.0]          # 2m x 2m and 5m x 4m


def test_rooms_assigns_a_label_that_falls_inside(storage):
    r = extract_rooms(RoomsInput(document_id="d", storage_key="fp.dxf",
                                 boundary_layers=["ROOM-BOUNDARY"],
                                 label_layers=["ROOM-NAMES"]), storage)
    named = [x for x in r.outputs["rooms"] if x["name"]]
    assert len(named) == 1
    assert named[0]["name"] == "OFFICE 101"
    assert named[0]["area_m2"] == 20.0


def test_rooms_leaves_an_unlabelled_room_null_and_says_so(storage):
    r = extract_rooms(RoomsInput(document_id="d", storage_key="fp.dxf",
                                 boundary_layers=["ROOM-BOUNDARY"],
                                 label_layers=["ROOM-NAMES"]), storage)
    assert r.outputs["unlabelled_rooms"] == 1
    assert any(x["name"] is None for x in r.outputs["rooms"])
    assert any("no text label" in w for w in r.warnings)


def test_unitless_drawing_cannot_report_areas(storage):
    r = extract_rooms(RoomsInput(document_id="d", storage_key="unitless.dxf",
                                 boundary_layers=["ROOM-BOUNDARY"]), storage)
    assert r.status == "missing_data"
    assert r.missing[0].field == "drawing_units"
    assert all(x["area_m2"] is None for x in r.outputs["rooms"])
    # The outlines are still useful, so they are still returned.
    assert r.outputs["room_count"] == 2
    assert all(x["area_drawing_units"] > 0 for x in r.outputs["rooms"])


def test_rooms_requires_the_boundary_layer_to_be_named(storage):
    with pytest.raises(InvalidInput) as e:
        extract_rooms(RoomsInput(document_id="d", storage_key="fp.dxf",
                                 boundary_layers=[]), storage)
    assert "boundary_layers" in str(e.value)


def test_open_polyline_is_skipped_with_a_warning(storage, tmp_path):
    d = ezdxf.new("R2010", setup=True)
    d.header["$INSUNITS"] = 4
    d.modelspace().add_lwpolyline([(0, 0), (1000, 0), (1000, 1000)], close=False,
                                  dxfattribs={"layer": "ROOM-BOUNDARY"})
    s = io.StringIO(); d.write(s)
    storage.write("open.dxf", s.getvalue().encode())
    r = extract_rooms(RoomsInput(document_id="d", storage_key="open.dxf",
                                 boundary_layers=["ROOM-BOUNDARY"]), storage)
    assert r.outputs["room_count"] == 0
    assert any("unclosed" in w for w in r.warnings)


# ------------------------------------------------------------------- markup
def test_markup_writes_a_new_file_and_leaves_the_original_alone(storage):
    before = storage.read("fp.dxf")
    r = markup(MarkupInput(document_id="d", storage_key="fp.dxf",
                           notes=[Note(x=1000, y=2000, text="Spacing exceeds rule",
                                       circle_radius=400)],
                           output_key="out/m.dxf"), storage)
    assert r.status == "ok"
    assert storage.read("fp.dxf") == before
    assert r.files[0].storage_key == "out/m.dxf"


def test_markup_goes_on_its_own_layer(storage):
    markup(MarkupInput(document_id="d", storage_key="fp.dxf",
                       notes=[Note(x=0, y=0, text="note")],
                       output_key="out/m.dxf"), storage)
    doc = ezdxf.read(io.StringIO(storage.read("out/m.dxf").decode("utf-8")))
    assert MARKUP_LAYER in doc.layers
    added = [e for e in doc.modelspace() if e.dxf.layer == MARKUP_LAYER]
    assert [e.dxftype() for e in added] == ["TEXT"]


def test_markup_preserves_the_original_entities(storage):
    markup(MarkupInput(document_id="d", storage_key="fp.dxf",
                       notes=[Note(x=0, y=0, text="note")],
                       output_key="out/m.dxf"), storage)
    doc = ezdxf.read(io.StringIO(storage.read("out/m.dxf").decode("utf-8")))
    inserts = [e for e in doc.modelspace() if e.dxftype() == "INSERT"]
    assert len(inserts) == 7


def test_markup_with_no_notes_is_invalid_input(storage):
    r = markup(MarkupInput(document_id="d", storage_key="fp.dxf", notes=[]), storage)
    assert r.status == "invalid_input"
    assert r.files == []


# -------------------------------------------------------------- phase 2 stubs
def test_place_devices_is_implemented_now_that_a_cited_rule_exists():
    """It was a stub while nothing could supply a spacing figure with a source.
    The figure still does not live in this package -- it is passed in."""
    from craft.cad import PlaceDevicesInput, SpacingRule, place_devices
    import inspect
    src = inspect.getsource(place_devices)
    assert "NotImplementedError" not in src
    # No spacing number is hard-coded anywhere in the module.
    import craft.cad.place as mod
    assert "9.1" not in inspect.getsource(mod)


def test_measure_route_refuses_and_says_why():
    with pytest.raises(NotImplementedError) as e:
        measure_route(MeasureRouteInput(document_id="d", storage_key="fp.dxf",
                                        from_point=(0, 0), to_point=(100, 100)))
    assert "not a cable length" in str(e.value)


def test_only_route_measurement_remains_unimplemented():
    from craft.core import tool_schemas
    by_name = {s["name"]: s for s in tool_schemas()}
    assert by_name["cad.measure_route"]["implemented"] is False
    assert by_name["cad.place_devices"]["implemented"] is True
    assert by_name["cad.count_devices"]["implemented"] is True
