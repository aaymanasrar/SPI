"""cad.render_svg: a picture of a DXF, with the DXF left alone."""
from __future__ import annotations

import pytest

from craft.cad import RenderSvgInput, render_svg
from craft.core import InvalidInput, LocalStorage

from test_cad import _dxf


@pytest.fixture
def storage(tmp_path):
    s = LocalStorage(tmp_path)
    s.write("fp.dxf", _dxf())
    return s


def test_renders_an_svg_sized_from_the_drawing(storage):
    before = storage.read("fp.dxf")
    r = render_svg(RenderSvgInput(document_id="d", storage_key="fp.dxf",
                                  output_key="out/fp.svg"), storage)
    assert r.status == "ok"
    assert storage.read("fp.dxf") == before
    svg = storage.read("out/fp.svg").decode("utf-8")
    assert svg.lstrip().startswith("<?xml") and "<svg" in svg
    assert 'width="420mm"' in svg
    f = r.files[0]
    assert (f.mime, f.storage_key, f.byte_size) == ("image/svg+xml", "out/fp.svg", len(svg.encode()))
    w, h = r.outputs["width_mm"], r.outputs["height_mm"]
    (x0, y0), (x1, y1) = r.outputs["extents_model"]
    assert h == pytest.approx(w * (y1 - y0) / (x1 - x0), abs=0.01)


def test_background_is_the_one_asked_for(storage):
    # Text is drawn as outlines, so the picture looks the same without the fonts.
    render_svg(RenderSvgInput(document_id="d", storage_key="fp.dxf", output_key="w.svg"), storage)
    render_svg(RenderSvgInput(document_id="d", storage_key="fp.dxf", background="black",
                              output_key="b.svg"), storage)
    assert "#ffffff" in storage.read("w.svg").decode().lower()
    assert "#000000" in storage.read("b.svg").decode().lower()
    assert storage.read("w.svg") != storage.read("b.svg")


def test_refuses_to_overwrite(storage):
    render_svg(RenderSvgInput(document_id="d", storage_key="fp.dxf", output_key="o.svg"), storage)
    with pytest.raises(Exception):
        render_svg(RenderSvgInput(document_id="d", storage_key="fp.dxf", output_key="o.svg"), storage)


def test_empty_drawing_is_invalid(tmp_path):
    import io

    import ezdxf
    s = LocalStorage(tmp_path)
    doc = ezdxf.new()
    buf = io.StringIO(); doc.write(buf)
    s.write("empty.dxf", buf.getvalue().encode())
    with pytest.raises(InvalidInput):
        render_svg(RenderSvgInput(document_id="d", storage_key="empty.dxf"), s)
