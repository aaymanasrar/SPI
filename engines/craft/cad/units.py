"""DXF units.

A DXF can declare no units at all ($INSUNITS = 0). Drawing coordinates are then
bare numbers, and 3000.0 is 3 metres, 3 metres in millimetres, or 3000 feet
depending on a convention held in someone's head. Anything that converts a
length into a real-world figure must stop there rather than assume millimetres.
Counting does not need units; measuring does.
"""
from __future__ import annotations

# $INSUNITS code -> (name, metres per drawing unit)
INSUNITS: dict[int, tuple[str, float | None]] = {
    0: ("unitless", None),
    1: ("inches", 0.0254),
    2: ("feet", 0.3048),
    4: ("millimetres", 0.001),
    5: ("centimetres", 0.01),
    6: ("metres", 1.0),
    7: ("kilometres", 1000.0),
    8: ("microinches", 0.0254e-6),
    9: ("mils", 0.0254e-3),
    10: ("yards", 0.9144),
    11: ("angstroms", 1e-10),
    12: ("nanometres", 1e-9),
    13: ("microns", 1e-6),
    14: ("decimetres", 0.1),
    15: ("decametres", 10.0),
    16: ("hectometres", 100.0),
    17: ("gigametres", 1e9),
    18: ("astronomical units", 1.495978707e11),
    19: ("light years", 9.4607304725808e15),
    20: ("parsecs", 3.0856775814913673e16),
}


def describe(code: int) -> tuple[str, float | None]:
    return INSUNITS.get(code, (f"unrecognised ($INSUNITS={code})", None))
