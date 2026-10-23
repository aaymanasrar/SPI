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


needs_soffice = pytest.mark.skipif(
    __import__("craft.word.to_pdf", fromlist=["x"]).find_soffice() is None,
    reason="LibreOffice is not installed on this machine")


def _pdf_text(storage, key: str) -> tuple[str, int]:
    """Read the converted PDF back. Asserting bytes start with %PDF proves a
    file appeared, not that the content survived the conversion."""
    from craft.pdf import ExtractInput, extract
    r = extract(ExtractInput(document_id="x", storage_key=key), storage)
    assert r.status == "ok", r.missing
    pages = r.outputs["pages"]
    return "\n".join(p["text"] for p in pages), len(pages)


@needs_soffice
def test_to_pdf_produces_a_pdf(storage):
    storage.write("a.docx", templates.build("transmittal"))
    r = to_pdf(ToPdfInput(storage_key="a.docx", output_key="out/a.pdf"), storage)
    assert r.status == "ok"
    assert storage.read("out/a.pdf").startswith(b"%PDF")
    assert r.outputs["converted_from"] == "a.docx"


@needs_soffice
def test_converted_pdf_keeps_every_filled_value(storage):
    """The conversion must not silently drop content."""
    values = {k: f"VALUE-{k.upper()}" for k in templates.placeholders("submittal_cover")}
    fill_template(FillInput(template_key="templates/submittal_cover.docx",
                            values=values, output_key="filled.docx"), storage)
    to_pdf(ToPdfInput(storage_key="filled.docx", output_key="out/filled.pdf"), storage)

    text, pages = _pdf_text(storage, "out/filled.pdf")
    assert pages == 1
    for key, value in values.items():
        assert value in text, f"{key} ({value}) did not survive conversion"


@needs_soffice
def test_converted_pdf_keeps_the_metadata_labels(storage):
    """The label/value table is a real table; a conversion that flattened it
    would lose the labels and leave bare values."""
    values = {k: f"v-{k}" for k in templates.placeholders("submittal_cover")}
    fill_template(FillInput(template_key="templates/submittal_cover.docx",
                            values=values, output_key="m.docx"), storage)
    to_pdf(ToPdfInput(storage_key="m.docx", output_key="out/m.pdf"), storage)
    text, _ = _pdf_text(storage, "out/m.pdf")
    for label in ("Project", "Project number", "Package", "Specification section",
                  "Manufacturer", "Model", "Prepared by"):
        assert label in text, f"label {label!r} lost"
    assert "Material Submittal" in text          # the title


@needs_soffice
def test_converted_compliance_sheet_keeps_the_table(storage):
    """Every clause, verdict and remark must appear. A compliance sheet whose
    table was dropped in conversion would be issued as if complete."""
    r = compliance_sheet(ComplianceInput(
        project_name="Riyadh Commercial Tower", product_model="FDO221",
        clauses=CLAUSES,
        captured_specs={"operating_voltage_v": 24.0, "quiescent_current_ma": 0.9},
        spec_source="Siemens capture 0020", output_key="c.docx"), storage)
    assert r.status == "ok"
    to_pdf(ToPdfInput(storage_key="c.docx", output_key="out/c.pdf"), storage)

    text, pages = _pdf_text(storage, "out/c.pdf")
    assert pages == 1
    for ref in ("2.3.A", "2.3.B", "2.4.A"):
        assert ref in text, f"clause {ref} lost"
    assert "Comply" in text and "Deviate" in text and "Clarify" in text
    assert "0.9" in text and "0.5" in text              # the deviation figures
    assert "Siemens capture 0020" in text               # provenance
    assert "not a submittal until signed" in text       # the caveat
    assert "Riyadh Commercial Tower" in text


@needs_soffice
def test_converted_pdf_keeps_the_footer(storage):
    """A footer lives in a separate XML part; it is the thing most often lost."""
    values = {k: f"v-{k}" for k in templates.placeholders("transmittal")}
    values["project_number"] = "RYD-001"
    fill_template(FillInput(template_key="templates/transmittal.docx",
                            values=values, output_key="f.docx"), storage)
    to_pdf(ToPdfInput(storage_key="f.docx", output_key="out/f.pdf"), storage)
    text, _ = _pdf_text(storage, "out/f.pdf")
    assert "RYD-001" in text


@needs_soffice
def test_converted_pdf_has_no_missing_glyphs(storage):
    """A missing font renders as tofu. The templates ask for Calibri, which is
    absent on Linux unless fonts-crosextra-carlito is installed."""
    values = {k: f"v-{k}" for k in templates.placeholders("compliance")}
    fill_template(FillInput(template_key="templates/compliance.docx",
                            values=values, output_key="g.docx"), storage)
    to_pdf(ToPdfInput(storage_key="g.docx", output_key="out/g.pdf"), storage)
    text, _ = _pdf_text(storage, "out/g.pdf")
    assert text.strip(), "conversion produced a page with no extractable text"
    for tofu in ("\ufffd", "\u25a1", "\u25a0"):
        assert tofu not in text, f"missing-glyph character {tofu!r} in output"
    # The middle dot in the footer separator is non-ASCII and a good canary.
    assert "\u00b7" in text or "Rev" in text


@needs_soffice
def test_multi_page_document_converts_every_page(storage):
    """A long document must not be truncated to its first page."""
    import docx as _docx
    from craft.word import style as _style
    doc = _style.new_document()
    _style.add_title(doc, "Long Document")
    for i in range(1, 121):
        doc.add_paragraph(f"Line {i} of one hundred and twenty.")
    buf = io.BytesIO(); doc.save(buf)
    storage.write("long.docx", buf.getvalue())

    to_pdf(ToPdfInput(storage_key="long.docx", output_key="out/long.pdf"), storage)
    text, pages = _pdf_text(storage, "out/long.pdf")
    assert pages >= 2, f"120 paragraphs rendered on {pages} page(s)"
    assert "Line 1 of" in text and "Line 120 of" in text


@needs_soffice
def test_to_pdf_refuses_to_overwrite_and_leaves_the_source_alone(storage):
    storage.write("src.docx", templates.build("transmittal"))
    before = storage.read("src.docx")
    to_pdf(ToPdfInput(storage_key="src.docx", output_key="out/once.pdf"), storage)
    with pytest.raises(InvalidInput):
        to_pdf(ToPdfInput(storage_key="src.docx", output_key="out/once.pdf"), storage)
    assert storage.read("src.docx") == before


@needs_soffice
def test_two_conversions_in_a_row_both_succeed(storage):
    """A shared LibreOffice profile makes the second call exit silently; to_pdf
    isolates the profile per call with -env:UserInstallation."""
    storage.write("x.docx", templates.build("transmittal"))
    a = to_pdf(ToPdfInput(storage_key="x.docx", output_key="out/x1.pdf"), storage)
    b = to_pdf(ToPdfInput(storage_key="x.docx", output_key="out/x2.pdf"), storage)
    assert a.status == "ok" and b.status == "ok"
    assert storage.read("out/x1.pdf")[:5] == b"%PDF-"
    assert storage.read("out/x2.pdf")[:5] == b"%PDF-"


@needs_soffice
def test_the_whole_chain_word_to_pdf_to_pack(storage):
    """Cover and compliance, converted, merged and stamped, then read back."""
    from craft.pdf import PackInput, StampSpec, pack
    cover = {k: f"v-{k}" for k in templates.placeholders("submittal_cover")}
    fill_template(FillInput(template_key="templates/submittal_cover.docx",
                            values=cover, output_key="ch.docx"), storage)
    compliance_sheet(ComplianceInput(
        project_name="P", product_model="M", clauses=[CLAUSES[0]],
        captured_specs={"operating_voltage_v": 24.0},
        spec_source="src", output_key="cc.docx"), storage)
    for name in ("ch", "cc"):
        to_pdf(ToPdfInput(storage_key=f"{name}.docx", output_key=f"{name}.pdf"), storage)

    p = pack(PackInput(storage_keys=["ch.pdf", "cc.pdf"],
                       stamp=StampSpec(text="Rev 03 - FOR APPROVAL"),
                       output_key="out/chain.pdf"), storage)
    assert p.status == "ok"
    assert p.outputs["page_count"] == 2
    text, pages = _pdf_text(storage, "out/chain.pdf")
    assert pages == 2
    assert text.count("Rev 03 - FOR APPROVAL") == 2     # stamped on both
    assert "Page 1 of 2" in text and "Page 2 of 2" in text
    assert "Material Submittal" in text and "Compliance Statement" in text
