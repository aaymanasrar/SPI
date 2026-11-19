"""The small set of Excel formulas GridCraft is allowed to write.

Deliberately tiny. The engine computes every value in Python; the formula exists
so the HUMAN can recalculate in Excel after editing a rate. We never depend on a
formula evaluator (that is why HyperFormula is on the forbidden list) -- if the
formula and the Python value ever disagree, the Python value is the one with
provenance, and the test suite asserts both.
"""
from __future__ import annotations

from ..core.errors import InvalidInput

ALLOWED = frozenset({"SUM", "ROUND", "ROUNDUP", "IF", "VLOOKUP"})


def guard(formula: str) -> str:
    """Reject any function outside the allowlist before it reaches a cell."""
    import re
    used = set(re.findall(r"([A-Z][A-Z0-9.]*)\s*\(", formula.upper()))
    forbidden = used - ALLOWED
    if forbidden:
        raise InvalidInput(
            f"Formula uses functions outside the allowed set {sorted(ALLOWED)}: {sorted(forbidden)}")
    return formula


def product(qty_cell: str, rate_cell: str, dp: int = 2) -> str:
    """Line amount = qty x rate, rounded to the currency's minor unit."""
    return guard(f"=ROUND({qty_cell}*{rate_cell},{dp})")


def total(first: str, last: str) -> str:
    return guard(f"=SUM({first}:{last})")


def roundup_boxes(length_cell: str, per_box: float) -> str:
    """Whole boxes of cable, never a fraction (rule SC-02)."""
    return guard(f"=ROUNDUP({length_cell}/{per_box},0)")
