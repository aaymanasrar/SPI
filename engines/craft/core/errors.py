"""Typed failures. Mirrors calc_engine.CalcInputError and knowledge_base.KBMissingData.

The distinction that matters: MissingData is not an error. It is the engine
declining to invent a value, which is a correct and expected outcome. It carries
the itemised list of what was missing so the caller can go and capture it.
"""
from __future__ import annotations


class CraftError(Exception):
    """Base for every failure the engines raise deliberately."""


class MissingData(CraftError):
    """A value the tool needed was not captured. NEVER substitute a guess.

    items: list of {"field": ..., "record": ..., "note": ...}
    """

    def __init__(self, items: list[dict], message: str | None = None):
        self.items = items
        summary = ", ".join(f"{i.get('record', '?')}.{i.get('field', '?')}" for i in items)
        super().__init__(message or f"Value not captured for: {summary}")


class InvalidInput(CraftError):
    """The caller asked for something malformed or impossible."""


class LicenseViolation(CraftError):
    """A code path requires a dependency outside the allowed licence set."""
