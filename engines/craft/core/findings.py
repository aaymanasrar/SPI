"""Assumptions, findings and the provenance grade of a value.

Three things the result envelope could not previously say, all of which the
engineering workflow depends on.

**An assumption is not a fact.** A ceiling height of 3.0 m used because nobody
supplied one is a different object from a ceiling height of 3.0 m read off a
section. Both produce the same number and only one can be relied on, so the
difference has to travel with the result rather than live in a sentence someone
wrote once.

**A finding is actionable.** `warnings` is a list of strings nobody can act on
programmatically. A finding names what is wrong, how bad it is, and what a
person has to do about it.

**Evidence has a grade.** A quantity counted off a drawing, one computed from a
rule, one typed by a person and one signed off by an engineer are four different
kinds of thing. Losing the difference is how a proposal becomes a quotation.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

#: Where a value came from, in increasing order of authority.
#: - extracted: read off a drawing or document. Evidence.
#: - calculated: produced by a rule or a calculator. A recommendation.
#: - manual:    entered by a person. Their judgement, not yet reviewed.
#: - approved:  signed off by an engineer. The only grade that is truth.
Evidence = Literal["extracted", "calculated", "manual", "approved"]

#: review  - a person must look, but work can continue
#: blocker - the result cannot be relied on until it is resolved
Severity = Literal["info", "review", "blocker"]


class Assumption(BaseModel):
    """A value used because nothing authoritative supplied one."""
    key: str
    value: Any
    unit: str | None = None
    basis: str = Field(description="why this value was used at all")
    status: Literal["assumed", "verified"] = "assumed"
    verify_from: str = Field(
        description="the document that would settle it, e.g. 'architectural "
                    "sections or the reflected ceiling plan'")

    @field_validator("basis", "verify_from")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(
                "an assumption with no stated basis or no way to verify it is "
                "indistinguishable from an invented number")
        return v


class Finding(BaseModel):
    """Something a person has to do something about."""
    code: str = Field(description="stable identifier, e.g. 'DIM-CHAIN-CONFLICT'")
    severity: Severity
    subject: str = Field(description="what it is about, e.g. 'document:L01.dxf'")
    detail: str = Field(description="what is wrong, in full")
    action: str = Field(description="what a person must do to resolve it")

    @field_validator("action")
    @classmethod
    def _actionable(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(
                "a finding with no action is a warning wearing a better name")
        return v


def worst(findings: list[Finding]) -> Severity | None:
    order = {"info": 0, "review": 1, "blocker": 2}
    if not findings:
        return None
    return max(findings, key=lambda f: order[f.severity]).severity
