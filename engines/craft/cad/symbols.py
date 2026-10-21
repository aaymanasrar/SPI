"""Symbol mapping — supplied as DATA, never hard-coded.

A block called `FD` is a smoke detector on one job and a fire damper on another.
There is no universal symbol library, so this module holds no mappings of its
own: it loads one, records where it came from, and refuses to guess at a block
it was not told about. An unmapped block is a reported gap, not a zero.
"""
from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field, field_validator

from ..core import InvalidInput


class SymbolRule(BaseModel):
    """One mapping line. At least one of block/layer must be set."""
    block: str | None = Field(None, description="block name, or a regex if is_regex")
    layer: str | None = Field(None, description="layer name, or a regex if is_regex")
    is_regex: bool = False
    system: str = Field(description="e.g. fire_alarm, cctv, access_control")
    device_type: str = Field(description="what to count it as")
    unit: str = "no"
    note: str | None = None

    @field_validator("device_type", "system")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v

    def matches(self, block: str, layer: str) -> bool:
        def one(pattern: str | None, value: str) -> bool:
            if pattern is None:
                return True
            if self.is_regex:
                return re.fullmatch(pattern, value, re.IGNORECASE) is not None
            return pattern.casefold() == value.casefold()
        if self.block is None and self.layer is None:
            return False
        return one(self.block, block) and one(self.layer, layer)


class SymbolMap(BaseModel):
    """A client's or project's drawing standard, as data."""
    name: str
    version: str
    source_document: str = Field(
        description="where this mapping came from — a drawing standard, a legend "
                    "sheet, an email. Required: a mapping with no stated origin "
                    "cannot be audited later.")
    rules: list[SymbolRule]

    @field_validator("source_document")
    @classmethod
    def _needs_origin(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(
                "source_document is required — every mapping must say where it "
                "came from")
        return v

    @field_validator("rules")
    @classmethod
    def _not_empty(cls, v: list[SymbolRule]) -> list[SymbolRule]:
        if not v:
            raise ValueError("a symbol map with no rules would map nothing")
        return v

    def resolve(self, block: str, layer: str) -> SymbolRule | None:
        """First matching rule wins, so order expresses precedence."""
        for rule in self.rules:
            if rule.matches(block, layer):
                return rule
        return None

    @classmethod
    def load(cls, raw: str | bytes | dict) -> "SymbolMap":
        if isinstance(raw, (str, bytes)):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError as e:
                raise InvalidInput(f"Symbol map is not valid JSON: {e}") from e
        return cls.model_validate(raw)
