"""The result shape every craft tool returns. No tool returns a bare value."""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field

ENGINE_VERSION = "engines@0.1.0"

Status = Literal["ok", "missing_data", "invalid_input", "error"]


class Provenance(BaseModel):
    """Answers 'where did you come from?' for one value in the output."""
    value_ref: str = Field(description="What was produced, e.g. 'boq_item:123.qty'")
    source: str = Field(description="Where it came from, e.g. 'rule_execution:456'")


class MissingItem(BaseModel):
    field: str
    record: str
    note: str | None = None


class OutputFile(BaseModel):
    name: str
    mime: str
    storage_key: str | None = None
    document_id: str | None = None
    byte_size: int | None = None
    sha256: str | None = None


class ToolResult(BaseModel):
    """The standard envelope. `missing` non-empty with status='missing_data' is a
    normal outcome, not a failure -- see ARCHITECTURE.md 4.2 `unknowns`."""
    operation_id: str | None = None      # assigned by the caller (TS), not the engine
    tool: str
    status: Status = "ok"
    outputs: dict[str, Any] = Field(default_factory=dict)
    files: list[OutputFile] = Field(default_factory=list)
    provenance: list[Provenance] = Field(default_factory=list)
    missing: list[MissingItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    engine_version: str = ENGINE_VERSION
    duration_ms: int | None = None
