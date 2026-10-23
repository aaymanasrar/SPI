"""Propose device positions from a cited spacing rule.

This was a NotImplementedError stub, deliberately, because placement cannot be
done without a spacing figure and nothing in this package holds one. It is
implemented now because the rules library carries the figures WITH their
citations, and the rule is passed in as data: the caller supplies
`max_spacing_m`, `max_wall_distance_m` and the rule that says so. There is still
no spacing value anywhere in this file.

Everything produced here is a PROPOSAL. Rows are shaped for `drawing_objects`
with `source='ai_extracted'` and `review_status='pending'` -- a detector counted
off a drawing is evidence, one computed from a rule is a suggestion, and the two
must not arrive in the same state.

`measure_route` remains unimplemented: cable length needs containment routes,
risers and a slack allowance, which is open decision D-7.
"""
from __future__ import annotations

import math
import time

from pydantic import BaseModel, Field

from ..core import (ENGINE_VERSION, Assumption, Finding, InvalidInput, Provenance,
                    Storage, ToolResult, register)
from .read_dxf import open_dxf
from .rooms import RoomsInput, extract_rooms, point_in_polygon
from .units import describe


class SpacingRule(BaseModel):
    """A spacing figure and the rule it comes from. Both required.

    Every number here arrives from the rules library. None is defaulted, because
    a default spacing is an invented engineering value wearing a sensible face.
    """
    rule_code: str = Field(description="e.g. 'ELV-B-01'")
    source: str = Field(description="e.g. 'NFPA 72' -- a figure with no citation "
                                    "cannot be defended on site")
    max_spacing_m: float = Field(gt=0)
    max_wall_distance_m: float = Field(gt=0)
    confidence: str | None = Field(
        None, description="the rule's confidence grade: code, spec or local. A "
                          "spec or local rule produces a weaker recommendation "
                          "and the finding says so.")
    conditions: str | None = Field(
        None, description="when the rule applies, e.g. 'smooth flat ceiling, no "
                          "high airflow'. Carried onto every placement, because a "
                          "spacing that assumed a flat ceiling is wrong under a "
                          "beamed one.")
    min_wall_offset_m: float | None = Field(
        None, gt=0,
        description="how far a device must stand OFF a wall, where the rule says "
                    "so. Omitted means the rule gives no minimum and none is "
                    "assumed.")


class Obstruction(BaseModel):
    """Something a device cannot sit on or too close to.

    Supplied as data: columns, beams, diffusers and bulkheads are on the
    architectural and mechanical drawings, not inferable from a room outline.
    """
    kind: str = Field(description="e.g. 'column', 'beam', 'supply diffuser'")
    x_m: float
    y_m: float
    radius_m: float = Field(gt=0, description="keep-clear radius around it")
    source: str = Field(description="the drawing it was read from")


class PlaceDevicesInput(BaseModel):
    document_id: str
    storage_key: str
    boundary_layers: list[str]
    label_layers: list[str] | None = None
    device_type: str
    system: str
    rule: SpacingRule
    obstructions: list[Obstruction] = Field(
        default_factory=list,
        description="keep-clear zones. A position landing inside one is moved to "
                    "the nearest clear point that still satisfies the rule, or "
                    "reported if none exists.")
    skip_rooms: list[str] = Field(
        default_factory=list,
        description="room names to leave out. Which rooms need a device is an "
                    "engineering decision, so it is the caller's, not this tool's.")
    min_room_area_m2: float = 0.0


def _blocking(x: float, y: float, obs: list["Obstruction"]):
    for o in obs:
        if math.hypot(x - o.x_m, y - o.y_m) < o.radius_m:
            return o
    return None


def _nudge_clear(x: float, y: float, poly, obs, max_spacing: float):
    """Move off an obstruction by the smallest step that stays legal.

    A detector displaced further than a quarter of the permitted spacing is no
    longer the position the rule asked for, so it is reported instead.
    """
    limit = max_spacing / 4
    step = limit / 6
    for ring in range(1, 7):
        d = step * ring
        if d > limit:
            break
        for k in range(12):
            a = k * math.pi / 6
            nx, ny = x + math.cos(a) * d, y + math.sin(a) * d
            if _blocking(nx, ny, obs) is None and point_in_polygon(nx, ny, poly):
                return (round(nx, 3), round(ny, 3))
    return None


def _axis_positions(length: float, max_spacing: float, max_wall: float,
                    min_offset: float = 0.0) -> list[float]:
    """Positions along one axis satisfying both limits, evenly spread.

    One detector serves a room narrow enough that both walls are already within
    the wall limit. Otherwise use the fewest points whose even pitch does not
    exceed max_spacing, starting and ending within max_wall of each wall.
    """
    if length <= 2 * max_wall:
        return [length / 2]
    # A wall offset, where the rule gives one, narrows the band the end points
    # may sit in; it never widens it.
    start = max(min_offset, 0.0)
    if start >= max_wall:
        start = max_wall
    usable = length - 2 * max_wall
    n = int(math.ceil(usable / max_spacing)) + 1
    pitch = usable / (n - 1)
    return [max_wall + i * pitch for i in range(n)]


@register("cad.place_devices", "cad", PlaceDevicesInput,
          "Propose device positions in each room from a cited spacing rule")
def place_devices(data: PlaceDevicesInput,
                  storage: Storage | None = None) -> ToolResult:
    started = time.perf_counter()
    res = ToolResult(tool="cad.place_devices", engine_version=ENGINE_VERSION)
    if storage is None:
        raise InvalidInput("cad.place_devices needs storage to fetch the document")

    doc = open_dxf(storage.read(data.storage_key), data.storage_key)
    insunits = int(doc.header.get("$INSUNITS", 0))
    unit_name, mpu = describe(insunits)
    if mpu is None:
        raise InvalidInput(
            f"$INSUNITS is {insunits} ({unit_name}). Spacing is a real-world "
            "distance and cannot be applied to a drawing with no units.")

    rooms = extract_rooms(RoomsInput(
        document_id=data.document_id, storage_key=data.storage_key,
        boundary_layers=data.boundary_layers,
        label_layers=data.label_layers), storage)

    skip = {s.casefold() for s in data.skip_rooms}
    proposals: list[dict] = []
    per_room: list[dict] = []

    for room in rooms.outputs.get("rooms", []):
        name = room["name"]
        area = room["area_m2"]
        if name and name.casefold() in skip:
            continue
        if area is not None and area < data.min_room_area_m2:
            continue
        poly_m = [(x * mpu, y * mpu) for x, y in room["boundary"]]
        xs = [p[0] for p in poly_m]
        ys = [p[1] for p in poly_m]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)

        off = data.rule.min_wall_offset_m or 0.0
        pts = [(x0 + dx, y0 + dy)
               for dx in _axis_positions(x1 - x0, data.rule.max_spacing_m,
                                         data.rule.max_wall_distance_m, off)
               for dy in _axis_positions(y1 - y0, data.rule.max_spacing_m,
                                         data.rule.max_wall_distance_m, off)]
        inside = [p for p in pts if point_in_polygon(p[0], p[1], poly_m)]

        cleared, displaced, blocked = [], 0, 0
        for px, py in inside:
            hit = _blocking(px, py, data.obstructions)
            if hit is None:
                cleared.append((px, py))
                continue
            moved = _nudge_clear(px, py, poly_m, data.obstructions,
                                 data.rule.max_spacing_m)
            if moved is None:
                blocked += 1
                res.findings.append(Finding(
                    code="PLACEMENT-OBSTRUCTED", severity="review",
                    subject=f"room:{name}",
                    detail=f"A position required by {data.rule.rule_code} at "
                           f"({px:.2f}, {py:.2f}) falls inside the keep-clear zone "
                           f"of a {hit.kind} from {hit.source}, and no clear point "
                           "near it satisfies the rule.",
                    action="Relocate the obstruction, accept a local deviation, or "
                           "add a device and record the departure from "
                           f"{data.rule.rule_code}."))
            else:
                displaced += 1
                cleared.append(moved)

        per_room.append({"room": name, "area_m2": area,
                         "proposed": len(cleared),
                         "outside_boundary": len(pts) - len(inside),
                         "displaced_by_obstruction": displaced,
                         "blocked_by_obstruction": blocked})
        for px, py in cleared:
            proposals.append({
                "object_type": data.device_type,
                "geometry": {"type": "Point",
                             "coordinates": [round(px, 3), round(py, 3)]},
                "extracted_value": {
                    "system": data.system, "room": name,
                    "basis": data.rule.rule_code,
                    # Every placement carries the rule, the conditions under
                    # which it holds, and the fact that nobody has approved it.
                    "rule": {"code": data.rule.rule_code,
                             "source": data.rule.source,
                             "confidence": data.rule.confidence,
                             "conditions": data.rule.conditions,
                             "max_spacing_m": data.rule.max_spacing_m,
                             "max_wall_distance_m": data.rule.max_wall_distance_m,
                             "min_wall_offset_m": data.rule.min_wall_offset_m},
                    "evidence": "calculated",
                    "validation_status": "unreviewed"},
                # A proposal, not an observation. count_devices uses 'imported'
                # for a device actually drawn; this one was never drawn.
                "source": "ai_extracted",
                "confidence": None,
                "source_reference": f"{data.rule.rule_code} ({data.rule.source}) "
                                    f"max {data.rule.max_spacing_m} m spacing, "
                                    f"max {data.rule.max_wall_distance_m} m to wall",
                "review_status": "pending",
            })

    res.outputs = {
        "device_type": data.device_type,
        "system": data.system,
        "proposed_count": len(proposals),
        "objects": proposals,
        "per_room": per_room,
        "rule": data.rule.model_dump(),
        "rooms_skipped": sorted(skip),
    }
    res.provenance = [Provenance(
        value_ref=f"placement:{data.device_type}",
        source=f"{data.rule.rule_code} ({data.rule.source}): max spacing "
               f"{data.rule.max_spacing_m} m, max {data.rule.max_wall_distance_m} m "
               f"from any wall")]
    res.assumptions.append(Assumption(
        key="placement_basis", value=data.rule.rule_code,
        basis=f"{data.rule.source}"
              + (f"; applies under: {data.rule.conditions}" if data.rule.conditions else ""),
        status="assumed",
        verify_from="the engineer's review of ceiling geometry, airflow and "
                    "obstructions against the rule's own conditions"))
    if data.rule.confidence and data.rule.confidence != "code":
        res.findings.append(Finding(
            code="PLACEMENT-RULE-NOT-CODE", severity="review",
            subject=f"rule:{data.rule.rule_code}",
            detail=f"{data.rule.rule_code} is '{data.rule.confidence}' confidence, "
                   "not a code requirement, so these positions rest on practice "
                   "rather than on a standard.",
            action="Confirm the rule against the governing standard before the "
                   "layout is issued."))
    if data.rule.conditions:
        res.findings.append(Finding(
            code="PLACEMENT-CONDITIONS", severity="review",
            subject=f"rule:{data.rule.rule_code}",
            detail=f"{data.rule.rule_code} applies under: {data.rule.conditions}. "
                   "Nothing in this tool checks that the rooms actually meet those "
                   "conditions.",
            action="Confirm each room's ceiling geometry and airflow against those "
                   "conditions, and re-run with a different rule where they differ."))
    res.warnings.append(
        f"{len(proposals)} position(s) PROPOSED from {data.rule.rule_code}, not "
        "counted from the drawing. Spacing is a maximum, not a design: ceiling "
        "geometry, airflow, beams and obstructions all move detectors, and an "
        "engineer must review each one before it becomes scope.")
    res.warnings.extend(rooms.warnings)
    res.duration_ms = int((time.perf_counter() - started) * 1000)
    return res


class MeasureRouteInput(BaseModel):
    document_id: str
    storage_key: str
    from_point: tuple[float, float]
    to_point: tuple[float, float]


@register("cad.measure_route", "cad", MeasureRouteInput,
          "Phase 2 - measure a cable route (not implemented)",
          implemented=False)
def measure_route(data: MeasureRouteInput, storage=None):
    raise NotImplementedError(
        "cad.measure_route is not implemented. A cable length needs the "
        "containment route, vertical risers and the project's slack allowance. "
        "A straight line between two symbols is not a cable length. This is "
        "open decision D-7.")
