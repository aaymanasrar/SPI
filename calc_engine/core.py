"""
Core result object shared by every calculation module.

Design rule: AI decides WHICH calculation is needed and gathers inputs.
This engine does the maths — deterministically, with a full audit trail.
No module in calc_engine imports an AI/LLM library or makes network calls.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any
import json


class CalcInputError(ValueError):
    """Raised when inputs are missing, out of range or physically impossible."""


@dataclass
class CalcResult:
    module: str                      # e.g. "voltage_drop"
    inputs: dict[str, Any]           # exactly what was fed in (after defaults)
    outputs: dict[str, Any]          # the answers
    passed: bool | None = None       # compliance verdict, None if not applicable
    steps: list[str] = field(default_factory=list)      # human-readable formula trace
    assumptions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)  # standards / clauses used

    def step(self, text: str) -> None:
        self.steps.append(text)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def report(self) -> str:
        """Plain-text calc sheet — paste into a design basis or TBE annex."""
        line = "=" * 64
        out = [line, f"CALCULATION: {self.module.upper()}", line, "INPUTS:"]
        out += [f"  {k}: {v}" for k, v in self.inputs.items()]
        out.append("METHOD / STEPS:")
        out += [f"  {i+1}. {s}" for i, s in enumerate(self.steps)]
        out.append("RESULTS:")
        out += [f"  {k}: {v}" for k, v in self.outputs.items()]
        if self.passed is not None:
            out.append(f"VERDICT: {'PASS' if self.passed else 'FAIL'}")
        if self.assumptions:
            out.append("ASSUMPTIONS:")
            out += [f"  - {a}" for a in self.assumptions]
        if self.warnings:
            out.append("WARNINGS:")
            out += [f"  ! {w}" for w in self.warnings]
        if self.references:
            out.append("REFERENCES:")
            out += [f"  - {r}" for r in self.references]
        out.append(line)
        return "\n".join(out)


def require_positive(**kwargs: float) -> None:
    for name, val in kwargs.items():
        if val is None:
            raise CalcInputError(f"'{name}' is required")
        if not isinstance(val, (int, float)):
            raise CalcInputError(f"'{name}' must be a number, got {type(val).__name__}")
        if val <= 0:
            raise CalcInputError(f"'{name}' must be > 0, got {val}")


def require_range(name: str, val: float, lo: float, hi: float) -> None:
    if val is None or not (lo <= val <= hi):
        raise CalcInputError(f"'{name}' must be between {lo} and {hi}, got {val}")


def r(x: float, n: int = 3) -> float:
    return round(x, n)
