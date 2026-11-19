"""HTTP surface tests.

This is what src/modules/craft/client.ts actually calls, and it had a defect the
unit tests could not see: craft/api.py imported only `grid`, so GET /tools
served 2 tools instead of 13.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from craft.api import app
from craft.core import TOOL_REGISTRY
from craft.word import templates

client = TestClient(app)


def test_health_reports_the_whole_registry():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["tools"] == len(TOOL_REGISTRY)


def test_every_engine_is_registered_on_the_http_surface():
    names = {t["name"] for t in client.get("/tools").json()}
    assert {n.split(".")[0] for n in names} == {"grid", "pdf", "cad", "word", "bim", "review"}
    assert names == set(TOOL_REGISTRY)


def test_each_tool_exposes_an_input_schema():
    for t in client.get("/tools").json():
        assert t["input_schema"]["type"] == "object"
        assert t["input_schema"]["properties"], t["name"]


def test_unknown_tool_is_404():
    assert client.post("/tools/grid.nope", json={"input": {}}).status_code == 404


def test_a_phase_2_stub_is_501_not_a_crash():
    r = client.post("/tools/cad.measure_route", json={
        "input": {"document_id": "d", "storage_key": "a.dxf",
                  "from_point": [0, 0], "to_point": [1, 1]}})
    assert r.status_code == 501
    assert "not implemented" in r.json()["detail"]


def test_a_preview_only_tool_refuses_commit_mode():
    r = client.post("/tools/pdf.extract", json={
        "input": {"document_id": "d", "storage_key": "a.pdf"}, "mode": "commit"})
    assert r.status_code == 400
    assert "does not support mode" in r.json()["detail"]


def test_malformed_input_is_invalid_input_not_a_500():
    r = client.post("/tools/pdf.extract", json={"input": {"pages": "all"}})
    assert r.status_code == 200
    assert r.json()["status"] == "invalid_input"


def test_operation_id_is_echoed_back(tmp_path):
    r = client.post("/tools/word.compliance_sheet", json={
        "operation_id": "op-123",
        "storage_root": str(tmp_path),
        "input": {"project_name": "P", "product_model": "M", "clauses": [],
                  "spec_source": "s"}})
    assert r.json()["operation_id"] == "op-123"


def test_status_error_always_carries_an_error_message(tmp_path, monkeypatch):
    """Migration 0023 constrains (status='error') = (error is not null). A null
    here makes the craft_operations insert fail, losing the record of the
    failure itself."""
    import sys
    monkeypatch.setattr(sys.modules["craft.word.to_pdf"], "find_soffice",
                        lambda: None)
    (tmp_path / "a.docx").write_bytes(templates.build("transmittal"))
    r = client.post("/tools/word.to_pdf", json={
        "storage_root": str(tmp_path),
        "input": {"storage_key": "a.docx"}})
    body = r.json()
    assert body["status"] == "error"
    assert body["error"]
    assert "LibreOffice" in body["error"]


def test_tool_result_refuses_to_be_constructed_in_the_forbidden_shapes():
    from pydantic import ValidationError
    from craft.core import ToolResult
    with pytest.raises(ValidationError):
        ToolResult(tool="t", status="error")                 # error without a message
    with pytest.raises(ValidationError):
        ToolResult(tool="t", status="ok", error="something") # message without the status
    assert ToolResult(tool="t", status="error", error="boom").error == "boom"


def test_a_missing_data_result_survives_the_http_round_trip(tmp_path):
    (tmp_path / "t.docx").write_bytes(templates.build("transmittal"))
    r = client.post("/tools/word.fill_template", json={
        "storage_root": str(tmp_path),
        "input": {"template_key": "t.docx", "values": {"recipient": "X"},
                  "output_key": "out.docx"}})
    body = r.json()
    assert body["status"] == "missing_data"
    assert body["files"] == []
    assert {m["field"] for m in body["missing"]} >= {"project_name", "revision"}
    assert not (tmp_path / "out.docx").exists()
