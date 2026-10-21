"""Phase 2: device placement and cable routing — deliberately not implemented.

These are the two tools where an engine cannot avoid inventing engineering
values, so they stop rather than produce something plausible.

`place_devices` needs a spacing rule: how far apart smoke detectors go, what a
camera covers, the throw of a speaker. Those numbers belong to a standard or a
project specification and must come from the rules engine with a citation.
Nothing in this package holds a spacing figure, by design.

`measure_route` needs tray and containment routes, slack and drop allowances,
and a vertical path through the building. Measuring a straight line between two
symbols and calling it a cable length produces a number that is always wrong and
always low.
"""
from __future__ import annotations

from pydantic import BaseModel

from ..core import register


class PlaceDevicesInput(BaseModel):
    document_id: str
    storage_key: str
    system: str
    rule_id: str


class MeasureRouteInput(BaseModel):
    document_id: str
    storage_key: str
    from_point: tuple[float, float]
    to_point: tuple[float, float]


@register("cad.place_devices", "cad", PlaceDevicesInput,
          "Phase 2 — place devices from a spacing rule (not implemented)",
          implemented=False)
def place_devices(data: PlaceDevicesInput, storage=None):
    raise NotImplementedError(
        "cad.place_devices is not implemented. Placement requires a spacing rule "
        f"(requested: {data.rule_id}) supplied by the rules engine with its "
        "citation. This package holds no spacing values and will not assume one.")


@register("cad.measure_route", "cad", MeasureRouteInput,
          "Phase 2 — measure a cable route (not implemented)",
          implemented=False)
def measure_route(data: MeasureRouteInput, storage=None):
    raise NotImplementedError(
        "cad.measure_route is not implemented. A cable length needs the "
        "containment route, vertical risers and the project's slack allowance. "
        "A straight line between two symbols is not a cable length.")
