"""GridCraft golden-file tests.

Byte comparison of .xlsx is useless — the zip embeds timestamps — so every test
opens the produced workbook with openpyxl and asserts BOTH the computed value and
the formula string. That is the whole point of the design: the engine computes in
Python and writes the formula for Excel, and the two must agree.
"""
import io
import sys
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from craft import LocalStorage, TOOL_REGISTRY                 # noqa: E402
from craft.core.errors import InvalidInput                    # noqa: E402
from craft.grid import BoqLine, WriteBoqInput, write_boq      # noqa: E402
from craft.grid import ReadClientBoqInput, read_client_boq    # noqa: E402
from craft.grid.formulas import guard, product, total         # noqa: E402


@pytest.fixture
def store(tmp_path):
    return LocalStorage(tmp_path)


def _open(storage, key):
    return load_workbook(io.BytesIO(storage.read(key)))


# --------------------------------------------------------------- formulas
def test_formula_allowlist_rejects_unknown_function():
    with pytest.raises(InvalidInput) as e:
        guard("=INDIRECT(A1)")
    assert "INDIRECT" in str(e.value)


def test_formula_allowlist_permits_the_five():
    assert product("E2", "F2") == "=ROUND(E2*F2,2)"
    assert total("G2", "G9") == "=SUM(G2:G9)"


# --------------------------------------------------------------- write_boq
def _lines():
    return [
        BoqLine(description="Multi-sensor detector OOH740", unit="no", quantity=120,
                system="Fire Alarm", part_number="S54320-F7-A3", boq_item_id="b1",
                quantity_source="rule_execution", rule_execution_id="re-1",
                unit_cost_minor=18500, price_source="vendor_approved"),
        BoqLine(description="Manual call point FDM225-RP", unit="no", quantity=18,
                system="Fire Alarm", part_number="A5Q00012020", boq_item_id="b2",
                quantity_source="rule_execution", rule_execution_id="re-2",
                unit_cost_minor=9900, price_source="vendor_approved"),
        BoqLine(description="Cat 6A U/FTP cable, LSZH", unit="m", quantity=2400,
                system="Structured Cabling", boq_item_id="b3",
                quantity_source="manual", unit_cost_minor=420,
                price_source="internal_price_list"),
    ]


def test_write_boq_values_and_formulas_agree(store):
    res = write_boq(WriteBoqInput(boq_id="boq-1", project_name="Riyadh Tower",
                                  project_code="RYD-001", revision=3,
                                  lines=_lines()), storage=store)
    assert res.status == "ok"
    key = res.files[0].storage_key
    assert res.files[0].name == "BOQ_RYD-001_Rev03.xlsx"

    wb = _open(store, key)
    assert wb.sheetnames[0] == "Summary"
    assert "Fire Alarm" in wb.sheetnames and "Structured Cabling" in wb.sheetnames

    fa = wb["Fire Alarm"]
    assert fa["C2"].value == "Multi-sensor detector OOH740"
    assert fa["E2"].value == 120                 # quantity
    assert fa["F2"].value == 185.0               # minor units -> major
    assert fa["G2"].value == "=ROUND(E2*F2,2)"   # formula for the human
    assert fa["G4"].value == "=SUM(G2:G3)"       # subtotal over 2 fire lines

    # Python-computed total, which is the number that carries provenance.
    assert res.outputs["sheet_totals"]["Fire Alarm"] == pytest.approx(120 * 185 + 18 * 99)
    assert res.outputs["grand_total"] == pytest.approx(120 * 185 + 18 * 99 + 2400 * 4.2)


def test_write_boq_summary_references_sheets_live(store):
    res = write_boq(WriteBoqInput(boq_id="b", project_name="P", project_code="P1",
                                  lines=_lines()), storage=store)
    s = _open(store, res.files[0].storage_key)["Summary"]
    refs = [s.cell(row=r, column=2).value for r in range(5, 7)]
    assert any(str(v).startswith("='Fire Alarm'!G") for v in refs)
    assert str(s.cell(row=7, column=2).value).startswith("=SUM(")


def test_write_boq_provenance_sheet_is_hidden_and_populated(store):
    res = write_boq(WriteBoqInput(boq_id="boq-9", project_name="P", project_code="P1",
                                  lines=_lines()), storage=store)
    wb = _open(store, res.files[0].storage_key)
    p = wb["Provenance"]
    assert p.sheet_state == "hidden"
    sources = {row[2] for row in p.iter_rows(min_row=2, values_only=True) if row[2]}
    assert "rule_execution:re-1" in sources
    assert any(s.startswith("price_source:") for s in sources)
    # every rule-derived quantity is traceable in the result envelope too
    assert {pv.source for pv in res.provenance} >= {"rule_execution:re-1", "rule_execution:re-2"}


def test_write_boq_unpriced_line_warns_but_still_renders(store):
    lines = _lines()
    lines[2].unit_cost_minor = None
    lines[2].price_source = None
    res = write_boq(WriteBoqInput(boq_id="b", project_name="P", project_code="P1",
                                  lines=lines), storage=store)
    assert res.status == "ok"
    assert any("no resolved price" in w for w in res.warnings)
    sc = _open(store, res.files[0].storage_key)["Structured Cabling"]
    assert sc["F2"].value is None                # blank rate, not a guessed one


def test_write_boq_require_pricing_returns_missing_data_not_a_guess(store):
    lines = _lines()
    lines[2].unit_cost_minor = None
    res = write_boq(WriteBoqInput(boq_id="b", project_name="P", project_code="P1",
                                  lines=lines, require_pricing=True), storage=store)
    assert res.status == "missing_data"
    assert res.files == []                       # nothing written
    assert res.missing[0].field == "unit_cost_minor"
    assert "13.2" in res.missing[0].note


def test_write_boq_rejects_empty_line_list(store):
    res = write_boq(WriteBoqInput(boq_id="b", project_name="P", project_code="P1"),
                    storage=store)
    assert res.status == "invalid_input"


def test_storage_refuses_to_overwrite_an_original(store):
    store.write("original.xlsx", b"x")
    with pytest.raises(InvalidInput):
        store.write("original.xlsx", b"y")


# --------------------------------------------------------- read_client_boq
def _client_workbook(path, headers, rows, preamble=2):
    wb = Workbook()
    ws = wb.active
    ws.title = "Bill of Quantities"
    for _ in range(preamble):
        ws.append(["Some client preamble"])
    ws.append(headers)
    for r in rows:
        ws.append(r)
    wb.save(path)
    return path


def test_read_client_boq_autodetects_header_and_maps_synonyms(store, tmp_path):
    p = _client_workbook(tmp_path / "client.xlsx",
                         ["Item Description", "UOM", "Qnty", "Unit Price", "MLFB"],
                         [["Smoke detector", "No.", 40, 185.0, "S54320-F7-A3"],
                          ["", "", "", "", ""],
                          ["Call point", "No.", 6, 99.0, None]])
    res = read_client_boq(ReadClientBoqInput(document_id="d1", storage_key=p.name),
                          storage=LocalStorage(tmp_path))
    assert res.status == "ok"
    assert res.outputs["header_row"] == 3
    assert res.outputs["row_count"] == 2
    assert res.outputs["blank_rows_skipped"] == 1
    assert res.outputs["rows"][0]["description"] == "Smoke detector"
    assert res.outputs["rows"][0]["quantity"] == 40
    assert res.outputs["rows"][0]["part_number"] == "S54320-F7-A3"
    # nothing imported is authoritative
    assert res.outputs["rows"][0]["quantity_source"] == "imported"
    assert any("proposals" in w for w in res.warnings)


def test_read_client_boq_raises_when_no_header_is_recognisable(tmp_path):
    p = _client_workbook(tmp_path / "junk.xlsx", ["alpha", "beta"], [["x", "y"]])
    with pytest.raises(InvalidInput) as e:
        read_client_boq(ReadClientBoqInput(document_id="d", storage_key=p.name),
                        storage=LocalStorage(tmp_path))
    assert "header row" in str(e.value)


# ------------------------------------------------------------------ registry
def test_registry_exposes_json_schemas_only():
    from craft import tool_schemas
    names = {s["name"] for s in tool_schemas()}
    assert {"grid.write_boq", "grid.read_client_boq"} <= names
    spec = next(s for s in tool_schemas() if s["name"] == "grid.read_client_boq")
    assert spec["modes"] == ["preview"]          # reading a client file never commits
    assert "storage_key" in spec["input_schema"]["properties"]


# ---------------------------------------------------------------------------
# Provenance gaps found by the end-to-end run, where a BOQ is built from a
# drawing count rather than from rule executions or existing boq_items.
# ---------------------------------------------------------------------------

def _counted_line(**kw):
    base = dict(description="Smoke Detector", unit="no", quantity=14.0,
                system="fire_alarm", quantity_source="imported",
                unit_cost_minor=18500, price_source="SPT price list 2026-Q4",
                currency="SAR")
    base.update(kw)
    return BoqLine(**base)


def _write(store, lines, key, **kw):
    return write_boq(WriteBoqInput(boq_id="B1", project_name="P", project_code="C",
                                   lines=lines, currency="SAR", output_key=key,
                                   **kw), store)


def test_an_imported_quantity_records_where_it_came_from(store):
    """A quantity counted off a drawing must answer 'where did you come from?'
    even with no rule_execution_id and no boq_item_id."""
    r = _write(store, [_counted_line(
        quantity_reference="cad.count_devices on L01.dxf")], "out/q.xlsx")
    assert r.status == "ok"
    sources = [p.source for p in r.provenance]
    assert "cad.count_devices on L01.dxf" in sources
    assert r.warnings == [] or not any("no provenance" in w for w in r.warnings)


def test_an_imported_quantity_with_no_reference_is_flagged(store):
    """It is still written -- an unpriced or unreferenced BOQ is a legitimate
    deliverable -- but it is named, not passed over in silence."""
    r = _write(store, [_counted_line()], "out/q2.xlsx")
    assert r.status == "ok"
    assert any("no provenance" in w for w in r.warnings)
    assert any("Smoke Detector" in w for w in r.warnings)


def test_a_manual_quantity_is_not_flagged(store):
    """A manual figure is self-evidently a person's; demanding a reference
    would make every hand-entered line a warning."""
    r = _write(store, [_counted_line(quantity_source="manual")], "out/q3.xlsx")
    assert not any("no provenance" in w for w in r.warnings)


def test_price_provenance_does_not_require_a_boq_item_id(store):
    """The original condition was `price_source and boq_item_id`, so a rate with
    a stated source but no database row recorded nothing."""
    r = _write(store, [_counted_line(
        quantity_reference="cad.count_devices on L01.dxf")], "out/p.xlsx")
    assert any(p.source == "price_source:SPT price list 2026-Q4"
               for p in r.provenance)


def test_quantity_reference_reaches_the_quantity_source_column(store):
    from openpyxl import load_workbook
    import io as _io
    _write(store, [_counted_line(quantity_reference="cad.count_devices on L01.dxf")],
           "out/col.xlsx")
    wb = load_workbook(_io.BytesIO(store.read("out/col.xlsx")))
    ws = wb["fire_alarm"]
    assert ws.cell(row=2, column=8).value == "imported:cad.count_devices on L01.dxf"


def test_every_priced_counted_line_gets_two_provenance_rows(store):
    """One for the quantity, one for the rate."""
    lines = [_counted_line(description=f"Device {i}",
                           quantity_reference=f"cad.count_devices on L0{i}.dxf")
             for i in range(1, 4)]
    r = _write(store, lines, "out/two.xlsx")
    assert len(r.provenance) == 6
    assert sum(1 for p in r.provenance if p.source.startswith("price_source:")) == 3


def test_rule_execution_still_takes_precedence(store):
    """quantity_reference must not override a real rule execution."""
    r = _write(store, [_counted_line(quantity_source="rule_execution",
                                       rule_execution_id="re-123",
                                       quantity_reference="should not win")],
               "out/prec.xlsx")
    sources = [p.source for p in r.provenance]
    assert "rule_execution:re-123" in sources
    assert "should not win" not in sources
