"""review.read_spec and review.check on the fixture office (fixtures/elv_office.py).

The spec and the BOQ below are written to disagree with the drawing in known
ways, so every check has something to find — and the things that agree must
not be flagged.
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import docx
import ezdxf
import pytest
from openpyxl import Workbook, load_workbook
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from craft.core import LocalStorage
from craft.review import CheckInput, ReadSpecInput, check, read_spec

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engines" / "fixtures"))
from elv_office import DEVICE_LAYERS, elv_ground_floor_dxf  # noqa: E402

SPEC = [
    "1.1 The fire alarm system shall be analogue addressable to NFPA 72, Siemens or approved equal.",
    "1.2 Optical smoke detectors shall be provided in all rooms.",
    "1.3 Manual call points shall be mounted at 1.4 m AFF.",
    "2.1 Provide 4 IP cameras, 4MP, IP66 rated.",
    "3.1 Provide 2 data outlets per 10 m2 in all offices.",
    "3.2 Horizontal cabling shall be Cat6A.",
    "3.3 All data cabling shall be Cat6.",
    "4.1 A public address system shall be provided.",
    "5.1 The building is a single storey office.",
]


def _pdf(lines: list[str]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 800
    for ln in lines:
        c.drawString(40, y, ln)
        y -= 18
    c.save()
    return buf.getvalue()


def _docx(lines: list[str]) -> bytes:
    d = docx.Document()
    for ln in lines:
        d.add_paragraph(ln)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def _boq() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["Item", "Description", "Unit", "Qty", "Rate"])
    rows = [
        ("1", "Addressable optical smoke detector, Siemens", "no", 10),
        ("2", "Heat detector, rate of rise", "no", 1),
        ("3", "Manual call point", "no", 2),
        ("4", "IP dome camera 2MP, Hikvision", "no", 3),
        ("5", "Cat6 data outlet", "no", 6),
        ("6", "Card reader", "no", 2),
        ("7", "Fire alarm control panel, conventional", "no", 1),
        ("8", "Containment and sundries", "lot", 1),
    ]
    for r in rows:
        ws.append(list(r) + [None])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture(scope="module")
def device_rules() -> dict:
    out = subprocess.run([sys.executable, str(ROOT / "simulator" / "rules.py"), "--device-rules"],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


@pytest.fixture
def storage(tmp_path):
    s = LocalStorage(tmp_path)
    s.write("plan.dxf", elv_ground_floor_dxf())
    s.write("spec.pdf", _pdf(SPEC))
    s.write("spec.docx", _docx(SPEC))
    s.write("boq.xlsx", _boq())
    return s


def _check(storage, device_rules, **kw):
    base = dict(document_id="r", project_name="Fixture office", layers=DEVICE_LAYERS,
                device_rules=device_rules, output_key="out/review.xlsx", markup_key="out/rec.dxf",
                drawing={"document_id": "plan", "storage_key": "plan.dxf", "filename": "plan.dxf"})
    base.update(kw)
    return check(CheckInput(**base), storage)


def codes(r):
    return [i["code"] for i in r.outputs["issues"]]


# ---------------------------------------------------------------- spec reader
@pytest.mark.parametrize("key", ["spec.pdf", "spec.docx"])
def test_spec_reader_reads_pdf_and_docx_alike(storage, key):
    r = read_spec(ReadSpecInput(document_id="s", storage_key=key, filename=key), storage)
    reqs = r.outputs["requirements"]
    kinds = {(q["kind"], q.get("device_type"), q.get("attribute")) for q in reqs}
    assert ("quantity", "camera", None) in kinds
    assert ("coverage", "smoke_detector", None) in kinds
    assert ("rate", "data_outlet", None) in kinds
    assert ("height", "manual_call_point", None) in kinds
    assert ("attribute", "camera", "resolution") in kinds
    cam = next(q for q in reqs if q["kind"] == "quantity" and q["device_type"] == "camera")
    assert cam["value"] == 4 and cam["clause"] == "2.1"
    # "5.1 … single storey office" requires nothing.
    assert not any(q["clause"] == "5.1" for q in reqs)


def test_clause_numbers_are_not_quantities(storage):
    r = read_spec(ReadSpecInput(document_id="s", storage_key="spec.pdf"), storage)
    assert not any(q["kind"] == "quantity" and q["device_type"] == "smoke_detector"
                   for q in r.outputs["requirements"])


# ---------------------------------------------------------------- 1. drawing alone
def test_drawing_alone_gives_a_boq_with_recommendations_where_and_why(storage, device_rules):
    r = _check(storage, device_rules)
    boq = {l["device_type"]: l for l in r.outputs["boq"]}
    assert boq["smoke_detector"]["drawn"] == 11
    assert boq["camera"]["drawn"] == 3 and boq["camera"]["recommended"] is None
    assert boq["camera"]["status"] == "no rule"
    so = boq["sounder_strobe"]
    assert so["drawn"] == 2 and so["recommended"] > 2 and so["status"] == "fewer than recommended"
    assert "SPT-FA-15" in so["why"] and so["where_recommended"]
    assert "DRAWING-BELOW-RULE" in codes(r)
    # Every proposed position is in a room and carries its rule.
    assert all(p["room_id"] and p["rule"] for p in r.outputs["recommended_positions"])


def test_recommended_positions_go_on_their_own_layer_in_a_copy(storage, device_rules):
    before = storage.read("plan.dxf")
    r = _check(storage, device_rules)
    assert storage.read("plan.dxf") == before
    names = [f.name for f in r.files]
    assert names == ["review.xlsx", "recommended.dxf"]
    doc = ezdxf.read(io.StringIO(storage.read("out/rec.dxf").decode()))
    original = {e.dxf.handle for e in ezdxf.read(io.StringIO(before.decode())).modelspace()}
    added = [e for e in doc.modelspace() if e.dxf.handle not in original]
    assert added and {e.dxf.layer for e in added} == {"SPI_RECOMMEND"}


def test_workbook_has_the_sheets_a_person_needs(storage, device_rules):
    _check(storage, device_rules, specs=[{"document_id": "s", "storage_key": "spec.pdf"}],
           boq={"document_id": "b", "storage_key": "boq.xlsx"})
    wb = load_workbook(io.BytesIO(storage.read("out/review.xlsx")))
    assert wb.sheetnames == ["Summary", "BOQ", "Issues", "By room", "Recommended positions",
                             "Spec requirements", "Client BOQ", "Not checked"]
    head = [c.value for c in wb["BOQ"][1]]
    assert head[3:7] == ["Drawn qty", "SPI recommended", "Spec qty", "Client BOQ qty"]


def test_no_rules_means_no_recommendation_and_says_so(storage):
    r = _check(storage, None)
    assert all(l["recommended"] is None for l in r.outputs["boq"])
    assert any("no rules supplied" in n["why"] for n in r.outputs["not_checked"])


# ---------------------------------------------------------------- 2. drawing + spec
def test_spec_against_drawing(storage, device_rules):
    r = _check(storage, device_rules, specs=[{"document_id": "s", "storage_key": "spec.pdf",
                                               "filename": "spec.pdf"}])
    issues = r.outputs["issues"]
    qty = next(i for i in issues if i["code"] == "SPEC-VS-DRAWING-QUANTITY")
    assert "spec 4, drawing 3" in qty["title"].lower()
    assert {s["doc"] for s in qty["sources"]} == {"spec", "drawing"}
    assert any(s["ref"].startswith("clause 2.1") for s in qty["sources"])
    # Data outlets: 2 per 10 m² in offices; the 36 m² offices have 2 each.
    rate = next(i for i in issues if i["code"] == "SPEC-VS-DRAWING-RATE")
    assert "OFFICE 1" in rate["detail"] and "needs 8" in rate["detail"]
    # Public address is required and not drawn.
    assert any(i["code"] == "SPEC-SYSTEM-NOT-DRAWN" and "public address" in i["title"] for i in issues)
    # Smoke detection in all rooms: the kitchen's heat detector counts, so no room lacks one.
    assert not any(i["code"] == "SPEC-VS-DRAWING-COVERAGE" for i in issues)


def test_spec_against_itself_and_the_code(storage, device_rules):
    r = _check(storage, device_rules, specs=[{"document_id": "s", "storage_key": "spec.pdf"}])
    issues = r.outputs["issues"]
    cat = [i for i in issues if i["code"] == "SPEC-CONTRADICTS-ITSELF" and "cable category" in i["title"]]
    assert cat and "Cat6 and Cat6A" in cat[0]["title"]
    band = next(i for i in issues if i["code"] == "SPEC-OUTSIDE-CODE-BAND")
    assert "1.4 m" in band["title"] and "1.07-1.22" in band["title"]


def test_coverage_gap_is_found_when_a_room_has_nothing(storage, device_rules):
    spec = _pdf(["1.1 Cameras shall be provided in all meeting rooms."])
    storage.write("cams.pdf", spec)
    r = _check(storage, device_rules, specs=[{"document_id": "c", "storage_key": "cams.pdf"}])
    cov = next(i for i in r.outputs["issues"] if i["code"] == "SPEC-VS-DRAWING-COVERAGE")
    assert "MEETING" in cov["detail"]


# ---------------------------------------------------------------- 3. BOQ + drawing + spec
def test_boq_against_drawing_and_spec(storage, device_rules):
    r = _check(storage, device_rules, specs=[{"document_id": "s", "storage_key": "spec.pdf"}],
               boq={"document_id": "b", "storage_key": "boq.xlsx", "filename": "boq.xlsx"})
    issues = r.outputs["issues"]
    c = codes(r)
    smoke = next(i for i in issues if i["code"] == "BOQ-VS-DRAWING-QUANTITY" and "smoke" in i["title"].lower())
    assert "boq 10, drawing 11" in smoke["title"].lower()
    assert any(s["doc"] == "boq" and "rows" in s["ref"] for s in smoke["sources"])
    # BOQ cameras: 3 vs spec 4, 2MP vs 4MP.
    assert any(i["code"] == "BOQ-VS-SPEC-QUANTITY" and "camera" in i["title"].lower() for i in issues)
    res = next(i for i in issues if i["code"] == "BOQ-VS-SPEC-ATTRIBUTE" and "resolution" in i["title"])
    assert "2 MP" in res["title"] and "4 MP" in res["title"]
    # Conventional panel against an addressable spec.
    assert any(i["code"] == "BOQ-VS-SPEC-ATTRIBUTE" and "conventional" in i["title"] for i in issues)
    # Hikvision against a spec with no camera brand: not a contradiction.
    assert not any("Hikvision" in i["title"] for i in issues)
    # Data outlets: Cat6 against a spec that says both Cat6 and Cat6A — Cat6 is stated, so no flag.
    assert not any(i["code"] == "BOQ-VS-SPEC-ATTRIBUTE" and "Cat6" in i["title"] for i in issues)
    # Things that agree are not flagged: call points 2 = 2, card readers 2 = 2.
    assert not any("call point" in i["title"].lower() and i["code"].startswith("BOQ-VS-DRAWING")
                   for i in issues)
    # The unmatched sundries line is listed as not checked, not guessed at.
    assert any("Containment and sundries" in n["what"] for n in r.outputs["not_checked"])
    assert "DRAWING-NOT-IN-BOQ" in c   # the fire alarm panel is in the BOQ, not drawn: and vice versa
    boq = {l["device_type"]: l for l in r.outputs["boq"]}
    assert boq["camera"]["client_boq"] == 3 and boq["camera"]["spec"] == 4 and boq["camera"]["drawn"] == 3


def test_boq_alone_against_spec(storage):
    r = check(CheckInput(document_id="r", specs=[{"document_id": "s", "storage_key": "spec.docx"}],
                         boq={"document_id": "b", "storage_key": "boq.xlsx"},
                         output_key="out/r.xlsx"), storage)
    assert r.files[0].name == "review.xlsx" and len(r.files) == 1
    assert any(i["code"] == "BOQ-VS-SPEC-QUANTITY" for i in r.outputs["issues"])
    assert not any(i["code"].startswith("DRAWING") for i in r.outputs["issues"])


def test_issues_are_also_findings(storage, device_rules):
    r = _check(storage, device_rules, specs=[{"document_id": "s", "storage_key": "spec.pdf"}])
    assert len(r.findings) >= len(r.outputs["issues"])
    assert all(f.severity in ("review", "info") for f in r.findings)


def test_nothing_to_check_is_invalid(storage):
    from craft.core import InvalidInput
    with pytest.raises(InvalidInput):
        check(CheckInput(document_id="r"), storage)


def test_rule_shortfalls_are_one_issue_per_device_listing_the_rooms(storage, device_rules):
    r = _check(storage, device_rules)
    below = [i for i in r.outputs["issues"] if i["code"] == "DRAWING-BELOW-RULE"]
    titles = [i["title"] for i in below]
    assert len(titles) == len(set(t.split(":")[0] for t in titles))
    so = next(i for i in below if i["title"].startswith("Sounder strobe"))
    assert "room(s)" in so["title"] and "OFFICE 1: 0 of 1" in so["detail"]


def test_a_matching_total_does_not_hide_a_short_room(storage, device_rules):
    r = _check(storage, device_rules)
    smoke = next(l for l in r.outputs["boq"] if l["device_type"] == "smoke_detector")
    if smoke["drawn"] == smoke["recommended"]:
        short = [l for l in r.outputs["rooms"] if l["device_type"] == "smoke_detector"
                 and l["recommended"] is not None and l["drawn"] < l["recommended"]]
        assert (smoke["status"] == "matches") == (not short)
