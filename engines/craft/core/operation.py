"""The result shape every craft tool returns. No tool returns a bare value."""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator

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
    # Set iff status == 'error'. Migration 0023 constrains
    # (status = 'error') = (error is not null) on craft_operations, so a failure
    # with no message cannot be recorded at all.
    error: str | None = None
    engine_version: str = ENGINE_VERSION
    duration_ms: int | None = None

    @model_validator(mode="after")
    def _error_iff_failed(self) -> "ToolResult":
        if (self.status == "error") != (self.error is not None):
            raise ValueError(
                "status='error' and a non-null `error` must agree: the database "
                "constraint on craft_operations rejects anything else, which "
                "would lose the record of the failure itself.")
        return self
