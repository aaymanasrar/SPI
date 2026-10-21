"""WordCraft tests.

Templates are the PLACEHOLDER ones from craft/word/templates.py. SmartPage's
real .docx files have not been supplied -- see docs/data-requests.
"""
from __future__ import annotations

import io
import sys

import docx
import pytest

from craft.core import InvalidInput, LocalStorage, ToolUnavailable
from craft.word import (Clause, ComplianceInput, FillInput, ToPdfInput,
                        compliance_sheet, fill_template, placeholders, templates,
                        to_pdf)

FULL_VALUES = {
    "project_name": "Riyadh Commercial Tower", "project_number": "RYD-001",
    "package": "Fire Alarm", "spec_section": "28 31 00",
    "manufacturer": "PLACEHOLDER Mfr", "product_model": "PLACEHOLDER-100",
    "revision": "03", "date": "2026-10-21", "prepared_by": "A. Engineer",
}


@pytest.fixture
def storage(tmp_path):
    s = LocalStorage(tmp_path)
    for kind in ("transmittal", "submittal_cover", "compliance"):
        s.write(f"templates/{kind}.docx", templates.build(kind))
    return s


def _read(storage, key):
    return docx.Document(io.BytesIO(storage.read(key)))


def _all_text(doc) -> str:
    return "\n".join(p.text for p in placeholders.iter_all_paragraphs(doc))


# ------------------------------------------------------- placeholder mechanics
def test_placeholder_split_across_runs_is_still_replaced():
    """The reason this module exists instead of a str.replace."""
    doc = docx.Document()
    par = doc.add_paragraph()
    for chunk in ("Project: {{proj", "ect_na", "me}} end"):
        par.add_run(chunk)
    assert not any("{{project_name}}" in r.text for r in par.runs)

    used, remaining = placeholders.fill(doc, {"project_name": "RYD-001"})
    assert used == {"project_name"}
    assert remaining == set()
    assert doc.paragraphs[0].text == "Project: RYD-001 end"


def test_placeholders_inside_tables_are_filled():
    doc = docx.Document()
    t = doc.add_table(rows=1, cols=2)
    t.rows[0].cells[0].text = "Model"
    t.rows[0].cells[1].text = "{{product_model}}"
    used, remaining = placeholders.fill(doc, {"product_model": "FDO221"})
    assert used == {"product_model"} and remaining == set()
    assert t.rows[0].cells[1].text == "FDO221"


def test_placeholders_in_the_footer_are_found_and_filled(storage):
    doc = _read(storage, "templates/submittal_cover.docx")
    assert "project_number" in placeholders.scan(doc)
    placeholders.fill(doc, FULL_VALUES)
    assert "{{" not in _all_text(doc)


def test_whitespace_inside_the_braces_is_tolerated():
    doc = docx.Document()
    doc.add_paragraph("{{ project_name }}")
    used, remaining = placeholders.fill(doc, {"project_name": "X"})
    assert used == {"project_name"} and remaining == set()
    assert doc.paragraphs[0].text == "X"


def test_an_unknown_key_is_left_in_place_not_blanked():
    doc = docx.Document()
    doc.add_paragraph("A {{known}} and a {{unknown}}")
    used, remaining = placeholders.fill(doc, {"known": "yes"})
    assert used == {"known"}
    assert remaining == {"unknown"}
    assert doc.paragraphs[0].text == "A yes and a {{unknown}}"


# ------------------------------------------------------------- fill_template
def test_fill_writes_a_document_when_every_value_is_supplied(storage):
    r = fill_template(FillInput(template_key="templates/submittal_cover.docx",
                                values=FULL_VALUES, output_key="out/cover.docx",
                                output_name="Cover.docx"), storage)
    assert r.status == "ok"
    assert r.files[0].name == "Cover.docx"
    text = _all_text(_read(storage, "out/cover.docx"))
    assert "Riyadh Commercial Tower" in text
    assert "{{" not in text


def test_a_missing_value_writes_no_file_at_all(storage):
    partial = {k: v for k, v in FULL_VALUES.items() if k != "project_number"}
    r = fill_template(FillInput(template_key="templates/submittal_cover.docx",
                                values=partial, output_key="out/x.docx"), storage)
    assert r.status == "missing_data"
    assert r.files == []
    assert [m.field for m in r.missing] == ["project_number"]
    assert not storage.exists("out/x.docx")


def test_allow_unfilled_writes_but_says_not_to_issue_it(storage):
    partial = {k: v for k, v in FULL_VALUES.items() if k != "project_number"}
    r = fill_template(FillInput(template_key="templates/submittal_cover.docx",
                                values=partial, output_key="out/draft.docx",
                                allow_unfilled=True), storage)
    assert r.status == "ok"
    assert r.files
    assert any("Do not issue" in w for w in r.warnings)
    assert "{{project_number}}" in _all_text(_read(storage, "out/draft.docx"))


def test_a_value_the_template_does_not_use_is_reported(storage):
    r = fill_template(FillInput(template_key="templates/submittal_cover.docx",
                                values={**FULL_VALUES, "clinet_name": "typo"},
                                output_key="out/c.docx"), storage)
    assert r.outputs["values_not_used_by_template"] == ["clinet_name"]
    assert any("typo in the key" in w for w in r.warnings)


def test_fill_rejects_a_file_that_is_not_docx(storage):
    storage.write("notes.txt", b"this is not a docx")
    with pytest.raises(InvalidInput) as e:
        fill_template(FillInput(template_key="notes.txt", values={}), storage)
    assert ".docx" in str(e.value)


def test_fill_never_overwrites_the_template(storage):
    before = storage.read("templates/submittal_cover.docx")
    fill_template(FillInput(template_key="templates/submittal_cover.docx",
                            values=FULL_VALUES, output_key="out/a.docx"), storage)
    assert storage.read("templates/submittal_cover.docx") == before


@pytest.mark.parametrize("kind", ["transmittal", "submittal_cover", "compliance"])
def test_every_default_template_fills_completely(storage, kind):
    """The declared field set must be exactly enough to produce a clean file."""
    values = {k: f"value-{k}" for k in templates.placeholders(kind)}
    r = fill_template(FillInput(template_key=f"templates/{kind}.docx",
                                values=values, output_key=f"out/{kind}.docx"),
                      storage)
    assert r.status == "ok", r.missing
    text = _all_text(_read(storage, f"out/{kind}.docx"))
    assert "{{" not in text


@pytest.mark.parametrize("kind", ["transmittal", "submittal_cover", "compliance"])
def test_declared_placeholders_match_the_document(storage, kind):
    """templates.placeholders() is what a form would be built from; it must not
    drift from what the .docx actually contains."""
    doc = _read(storage, f"templates/{kind}.docx")
    assert placeholders.scan(doc) == templates.placeholders(kind)


def test_a_default_template_invents_no_identity(storage):
    """No logo, no letterhead, no company name: that artwork is SmartPage's and
    a made-up one would go out on a document sent to a client."""
    for kind in templates.names():
        text = _all_text(_read(storage, f"templates/{kind}.docx"))
        assert "SmartPage" not in text.replace(
            "Generated by SmartPage Intelligence", "")


def test_documents_that_state_a_conclusion_say_they_are_proposals(storage):
    values = {k: f"v-{k}" for k in templates.placeholders("submittal_cover")}
    fill_template(FillInput(template_key="templates/submittal_cover.docx",
                            values=values, output_key="out/sc.docx"), storage)
    assert "not a submittal until signed" in _all_text(_read(storage, "out/sc.docx"))


def test_the_transmittal_carries_no_proposal_note(storage):
    """A transmittal makes no engineering claim, so the caveat would be noise."""
    values = {k: f"v-{k}" for k in templates.placeholders("transmittal")}
    fill_template(FillInput(template_key="templates/transmittal.docx",
                            values=values, output_key="out/tr.docx"), storage)
    assert "not a submittal until signed" not in _all_text(_read(storage, "out/tr.docx"))


def test_an_unknown_template_name_is_rejected():
    with pytest.raises(KeyError) as e:
        templates.build("letterhead")
    assert "Known:" in str(e.value)


# ---------------------------------------------------------- compliance sheet
CLAUSES = [
    Clause(reference="2.3.A", text="Operating voltage shall be at least 12 V DC",
           parameter="operating_voltage_v", operator=">=", value=12, unit="V DC"),
    Clause(reference="2.3.B", text="Quiescent current shall not exceed 0.5 mA",
           parameter="quiescent_current_ma", operator="<=", value=0.5, unit="mA"),
    Clause(reference="2.4.A", text="Finish shall be agreed with the architect"),
]


def test_a_clause_with_no_captured_value_is_never_comply(storage):
    """The rule that shapes this module."""
    r = compliance_sheet(ComplianceInput(
        project_name="P", product_model="PLACEHOLDER-100", clauses=CLAUSES,
        captured_specs={"operating_voltage_v": 24.0},     # 2.3.B not captured
        spec_source="PLACEHOLDER capture", output_key="out/c.docx"), storage)
    assert r.status == "missing_data"
    assert r.files == []
    assert [m.field for m in r.missing] == ["quiescent_current_ma"]
    assert "will not be marked Comply" in r.missing[0].note


def test_verdicts_when_everything_is_captured(storage):
    r = compliance_sheet(ComplianceInput(
        project_name="P", product_model="PLACEHOLDER-100", clauses=CLAUSES,
        captured_specs={"operating_voltage_v": 24.0, "quiescent_current_ma": 0.9},
        spec_source="PLACEHOLDER capture", output_key="out/c.docx"), storage)
    assert r.status == "ok"
    got = {row["reference"]: row["verdict"] for row in r.outputs["rows"]}
    assert got == {"2.3.A": "Comply", "2.3.B": "Deviate", "2.4.A": "Clarify"}
    assert r.outputs["counts"] == {"Comply": 1, "Deviate": 1, "Clarify": 1}


def test_a_deviation_states_both_numbers(storage):
    r = compliance_sheet(ComplianceInput(
        project_name="P", product_model="M", clauses=[CLAUSES[1]],
        captured_specs={"quiescent_current_ma": 0.9},
        spec_source="src", output_key="out/d.docx"), storage)
    row = r.outputs["rows"][0]
    assert "0.9" in row["remark"] and "0.5" in row["remark"]


def test_a_prose_clause_is_routed_to_a_person(storage):
    r = compliance_sheet(ComplianceInput(
        project_name="P", product_model="M", clauses=[CLAUSES[2]],
        captured_specs={}, spec_source="src", output_key="out/p.docx"), storage)
    assert r.status == "ok"            # nothing numeric is missing
    assert r.outputs["rows"][0]["verdict"] == "Clarify"


def test_the_sheet_records_where_the_specs_came_from(storage):
    r = compliance_sheet(ComplianceInput(
        project_name="P", product_model="M", clauses=[CLAUSES[0]],
        captured_specs={"operating_voltage_v": 24.0},
        spec_source="Siemens capture 0020", output_key="out/s.docx"), storage)
    assert all(p.source == "Siemens capture 0020" for p in r.provenance)
    assert "Siemens capture 0020" in _all_text(_read(storage, "out/s.docx"))


def test_the_sheet_says_it_is_a_proposal(storage):
    r = compliance_sheet(ComplianceInput(
        project_name="P", product_model="M", clauses=[CLAUSES[0]],
        captured_specs={"operating_voltage_v": 24.0},
        spec_source="src", output_key="out/s.docx"), storage)
    assert "not a submittal until signed" in _all_text(_read(storage, "out/s.docx"))


def test_no_clauses_is_invalid_input(storage):
    r = compliance_sheet(ComplianceInput(
        project_name="P", product_model="M", clauses=[],
        captured_specs={}, spec_source="src"), storage)
    assert r.status == "invalid_input"
    assert r.files == []


def test_boundary_values_are_compliant(storage):
    """>= 12 with exactly 12 must comply, not deviate."""
    r = compliance_sheet(ComplianceInput(
        project_name="P", product_model="M", clauses=[CLAUSES[0]],
        captured_specs={"operating_voltage_v": 12.0},
        spec_source="src", output_key="out/b.docx"), storage)
    assert r.outputs["rows"][0]["verdict"] == "Comply"


# -------------------------------------------------------------------- to_pdf
def test_to_pdf_names_the_missing_program_rather_than_crashing(storage, monkeypatch):
    # craft.word re-exports to_pdf, so the name craft.word.to_pdf resolves to the
    # function, not the module. Reach the module through sys.modules.
    monkeypatch.setattr(sys.modules["craft.word.to_pdf"], "find_soffice",
                        lambda: None)
    storage.write("a.docx", templates.build("transmittal"))
    with pytest.raises(ToolUnavailable) as e:
        to_pdf(ToPdfInput(storage_key="a.docx"), storage)
    msg = str(e.value)
    assert "LibreOffice" in msg and "SOFFICE_PATH" in msg


def test_soffice_path_env_is_honoured(monkeypatch, tmp_path):
    from craft.word.to_pdf import find_soffice
    fake = tmp_path / "soffice"
    fake.write_text("#!/bin/sh\n")
    monkeypatch.setenv("SOFFICE_PATH", str(fake))
    assert find_soffice() == str(fake)


@pytest.mark.skipif(__import__("craft.word.to_pdf", fromlist=["x"]).find_soffice() is None,
                    reason="LibreOffice is not installed on this machine")
def test_to_pdf_really_converts(storage):
    storage.write("a.docx", templates.build("transmittal"))
    r = to_pdf(ToPdfInput(storage_key="a.docx", output_key="out/a.pdf"), storage)
    assert r.status == "ok"
    assert storage.read("out/a.pdf").startswith(b"%PDF")
