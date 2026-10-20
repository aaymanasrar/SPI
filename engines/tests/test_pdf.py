"""PDFCraft tests.

Fixtures are generated, not stored: a PDF embeds a creation timestamp, so a
committed golden file would compare unequal on every run. The same reason the
grid tests assert cell values and formulas instead of zip bytes.
"""
from __future__ import annotations

import io

import pytest
from PIL import Image
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from craft.core import InvalidInput, LocalStorage
from craft.pdf import ExtractInput, PackInput, StampSpec, extract, pack

DATASHEET_LINES = [
    "SIEMENS FDO221 Optical Smoke Detector",
    "Operating voltage        12 - 33 V DC",
    "Quiescent current        0.25 mA",
    "Alarm current            2.0 mA",
]


def _text_pdf(pages: list[list[str]]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for lines in pages:
        c.setFont("Helvetica", 11)
        y = A4[1] - 72
        for line in lines:
            c.drawString(72, y, line)
            y -= 16
        c.showPage()
    c.save()
    return buf.getvalue()


def _table_pdf() -> bytes:
    """A ruled table — pdfplumber needs the rules to find cell boundaries."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    rows = [["Item", "Qty", "Unit"],
            ["FDO221 detector", "48", "no"],
            ["FDM221 call point", "12", "no"]]
    x0, y0, w, h = 72, 700, 150, 20
    c.setFont("Helvetica", 10)
    for r, row in enumerate(rows):
        for col, val in enumerate(row):
            x = x0 + col * w
            y = y0 - r * h
            c.rect(x, y, w, h)
            c.drawString(x + 4, y + 6, val)
    c.save()
    return buf.getvalue()


def _image_only_pdf() -> bytes:
    """Stands in for a scanned page: pixels, no text layer."""
    img = Image.new("RGB", (600, 800), "white")
    for x in range(100, 500):          # a black bar, so it is not a blank page
        for y in range(380, 420):
            img.putpixel((x, y), (0, 0, 0))
    png = io.BytesIO()
    img.save(png, format="PNG")
    png.seek(0)

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawImage(ImageReaderShim(png), 50, 50, width=500, height=700)
    c.save()
    return buf.getvalue()


class ImageReaderShim:
    """reportlab wants a path or ImageReader; wrap the in-memory PNG."""
    def __init__(self, fp):
        from reportlab.lib.utils import ImageReader
        self._r = ImageReader(fp)

    def __getattr__(self, name):
        return getattr(self._r, name)


@pytest.fixture
def storage(tmp_path):
    s = LocalStorage(tmp_path)
    s.write("src/datasheet.pdf", _text_pdf([DATASHEET_LINES, ["Page two body text"]]))
    s.write("src/table.pdf", _table_pdf())
    s.write("src/scan.pdf", _image_only_pdf())
    s.write("src/cover.pdf", _text_pdf([["Submittal Cover"]]))
    return s


# --------------------------------------------------------------------------
# extract
# --------------------------------------------------------------------------

def test_extract_reads_text_from_every_page(storage):
    r = extract(ExtractInput(document_id="d1", storage_key="src/datasheet.pdf"), storage)
    assert r.status == "ok"
    assert r.outputs["page_count"] == 2
    assert "FDO221" in r.outputs["pages"][0]["text"]
    assert "0.25 mA" in r.outputs["pages"][0]["text"]
    assert "Page two" in r.outputs["pages"][1]["text"]


def test_extract_honours_page_selection(storage):
    r = extract(ExtractInput(document_id="d1", storage_key="src/datasheet.pdf", pages=[2]), storage)
    assert r.outputs["pages_read"] == 1
    assert r.outputs["pages"][0]["page"] == 2
    assert "FDO221" not in r.outputs["pages"][0]["text"]


def test_extract_rejects_a_page_that_does_not_exist(storage):
    with pytest.raises(InvalidInput) as e:
        extract(ExtractInput(document_id="d1", storage_key="src/datasheet.pdf", pages=[7]), storage)
    assert "7" in str(e.value)


def test_extract_finds_table_cells(storage):
    r = extract(ExtractInput(document_id="d2", storage_key="src/table.pdf"), storage)
    assert r.outputs["table_count"] >= 1
    flat = [c for t in r.outputs["pages"][0]["tables"] for row in t["data"] for c in row]
    assert "48" in flat
    assert "FDM221 call point" in flat


def test_extract_writes_no_file_at_all(storage):
    r = extract(ExtractInput(document_id="d1", storage_key="src/datasheet.pdf"), storage)
    assert r.files == []


def test_scanned_page_is_missing_data_not_empty_text(storage):
    """The point of the engine: no text layer is a reported gap, not a blank."""
    r = extract(ExtractInput(document_id="d3", storage_key="src/scan.pdf"), storage)
    assert r.status == "missing_data"
    assert r.missing[0].field == "text_layer"
    assert "OCR" in r.missing[0].note
    assert r.outputs["pages_without_text_layer"] == [1]


def test_partly_scanned_document_warns_and_still_returns_text(storage):
    storage.write("src/mixed.pdf", _text_pdf([DATASHEET_LINES]) )
    # page 1 has text, page 2 does not
    merged = pack(PackInput(storage_keys=["src/mixed.pdf", "src/scan.pdf"],
                            output_key="src/merged_mixed.pdf",
                            output_name="mixed.pdf"), storage)
    assert merged.status == "ok"
    r = extract(ExtractInput(document_id="d4", storage_key="src/merged_mixed.pdf"), storage)
    assert r.status == "ok"
    assert r.outputs["pages_without_text_layer"] == [2]
    assert any("no text layer" in w for w in r.warnings)


def test_vectors_are_opt_in(storage):
    off = extract(ExtractInput(document_id="d2", storage_key="src/table.pdf"), storage)
    assert "vectors" not in off.outputs["pages"][0]
    on = extract(ExtractInput(document_id="d2", storage_key="src/table.pdf",
                              include_vectors=True), storage)
    assert len(on.outputs["pages"][0]["vectors"]["rects"]) == 9  # 3 rows x 3 cols


# --------------------------------------------------------------------------
# pack
# --------------------------------------------------------------------------

def test_pack_merges_in_the_given_order(storage):
    r = pack(PackInput(storage_keys=["src/cover.pdf", "src/datasheet.pdf"],
                       output_key="out/pack.pdf"), storage)
    assert r.status == "ok"
    assert r.outputs["page_count"] == 3
    reader = PdfReader(io.BytesIO(storage.read("out/pack.pdf")))
    assert "Submittal Cover" in reader.pages[0].extract_text()
    assert "FDO221" in reader.pages[1].extract_text()


def test_pack_stamps_every_page_with_running_numbers(storage):
    r = pack(PackInput(storage_keys=["src/cover.pdf", "src/datasheet.pdf"],
                       stamp=StampSpec(text="Rev 03 - For Approval"),
                       output_key="out/stamped.pdf"), storage)
    reader = PdfReader(io.BytesIO(storage.read("out/stamped.pdf")))
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text()
        assert "Rev 03 - For Approval" in text
        assert f"Page {i} of 3" in text


def test_stamp_does_not_erase_the_original_content(storage):
    r = pack(PackInput(storage_keys=["src/datasheet.pdf"],
                       stamp=StampSpec(text="DRAFT"),
                       output_key="out/kept.pdf"), storage)
    reader = PdfReader(io.BytesIO(storage.read("out/kept.pdf")))
    text = reader.pages[0].extract_text()
    assert "Alarm current" in text and "DRAFT" in text


def test_pack_never_touches_the_originals(storage):
    before = storage.read("src/datasheet.pdf")
    pack(PackInput(storage_keys=["src/datasheet.pdf"],
                   stamp=StampSpec(text="DRAFT"),
                   output_key="out/x.pdf"), storage)
    assert storage.read("src/datasheet.pdf") == before


def test_pack_records_file_hash_and_size(storage):
    r = pack(PackInput(storage_keys=["src/cover.pdf"], output_key="out/h.pdf"), storage)
    f = r.files[0]
    assert f.mime == "application/pdf"
    assert f.byte_size == len(storage.read("out/h.pdf"))
    assert len(f.sha256) == 64


def test_pack_with_no_sources_is_invalid_input_not_an_empty_pdf(storage):
    r = pack(PackInput(storage_keys=[]), storage)
    assert r.status == "invalid_input"
    assert r.files == []


def test_pack_refuses_to_overwrite_an_existing_output(storage):
    pack(PackInput(storage_keys=["src/cover.pdf"], output_key="out/once.pdf"), storage)
    with pytest.raises(InvalidInput) as e:
        pack(PackInput(storage_keys=["src/cover.pdf"], output_key="out/once.pdf"), storage)
    assert "overwrite" in str(e.value)


def test_pack_refuses_an_encrypted_source(storage, tmp_path):
    from pypdf import PdfWriter
    w = PdfWriter(clone_from=io.BytesIO(_text_pdf([["secret"]])))
    w.encrypt("pw")
    buf = io.BytesIO()
    w.write(buf)
    storage.write("src/locked.pdf", buf.getvalue())
    with pytest.raises(InvalidInput) as e:
        pack(PackInput(storage_keys=["src/locked.pdf"], output_key="out/no.pdf"), storage)
    assert "encrypted" in str(e.value)


def test_both_tools_are_registered_with_schemas():
    from craft.core import tool_schemas
    names = {s["name"] for s in tool_schemas()}
    assert {"pdf.extract", "pdf.pack"} <= names
    ex = next(s for s in tool_schemas() if s["name"] == "pdf.extract")
    assert ex["modes"] == ["preview"]          # extract can never write
