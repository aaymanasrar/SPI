"""Check a device layout against a spacing rule.

This verifies ANY layout -- one this engine proposed, or one an engineer drew --
against the spacing figures of a named rule. It is deliberately separate from
placement so that checking is not the same act as proposing.

**What this is not.** It is not proof of code compliance and must never be
reported as one. It tests the two geometric limits a spacing rule states: no
point further from a device than the rule allows, and no device further from a
wall than the rule allows. A real compliance assessment covers ceiling
obstructions and beam depths, airflow and diffuser positions, stratification and
ceiling height, listed spacing for the specific detector, survey and
commissioning. None of that is tested here and none of it is inferable from a
floor plan.

A clean result means the layout passes these two checks. It does not mean the
installation complies.
"""
from __future__ import annotations

import math
import time

from pydantic import BaseModel, Field

from ..core import ENGINE_VERSION, Finding, InvalidInput, ToolResult, register
from .place import SpacingRule
from .rooms import point_in_polygon


class RoomOutline(BaseModel):
    name: str | None = None
    boundary_m: list[tuple[float, float]]


class DevicePoint(BaseModel):
    x_m: float
    y_m: float
    room: str | None = None


class CheckCoverageInput(BaseModel):
    document_id: str
    rooms: list[RoomOutline]
    devices: list[DevicePoint]
    rule: SpacingRule
    grid_step_m: float = Field(
        0.5, gt=0,
        description="sampling pitch for the uncovered-point test. Finer is "
                    "slower and finds smaller gaps.")


@register("cad.check_coverage", "cad", CheckCoverageInput,
          "Check a device layout against a spacing rule's geometric limits",
          modes=("preview",))
def check_coverage(data: CheckCoverageInput, storage=None) -> ToolResult:
    started = time.perf_counter()
    res = ToolResult(tool="cad.check_coverage", engine_version=ENGINE_VERSION)
    if not data.rooms:
        raise InvalidInput("No rooms supplied; there is nothing to check")

    # The rule's spacing S permits a device to serve a point up to S/2 away on
    # each axis, so the furthest legal point is the diagonal of that half-cell.
    reach = math.hypot(data.rule.max_spacing_m / 2, data.rule.max_spacing_m / 2)
    per_room: list[dict] = []
    total_gaps = 0

    for room in data.rooms:
        poly = [(float(x), float(y)) for x, y in room.boundary_m]
        if len(poly) < 3:
            continue
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        here = [d for d in data.devices
                if point_in_polygon(d.x_m, d.y_m, poly)]

        gaps: list[tuple[float, float]] = []
        step = data.grid_step_m
        y = min(ys) + step / 2
        while y < max(ys):
            x = min(xs) + step / 2
            while x < max(xs):
                if point_in_polygon(x, y, poly):
                    if not here or min(math.hypot(x - d.x_m, y - d.y_m)
                                       for d in here) > reach:
                        gaps.append((round(x, 2), round(y, 2)))
                x += step
            y += step

        # The wall limit binds each WALL, not each device: every wall must have
        # a device within reach of it. Applying it to every device would fail
        # the interior detectors of any room wider than twice the limit, which
        # is the opposite of what the rule says.
        far_from_wall = []
        for i in range(len(poly)):
            a, b = poly[i], poly[(i + 1) % len(poly)]
            if math.hypot(b[0] - a[0], b[1] - a[1]) < 1e-6:
                continue
            nearest = min((_point_to_segment(d.x_m, d.y_m, a, b) for d in here),
                          default=float("inf"))
            if nearest > data.rule.max_wall_distance_m + 1e-6:
                far_from_wall.append({
                    "wall": [list(a), list(b)],
                    "nearest_device_m": (round(nearest, 3)
                                         if nearest != float("inf") else None)})

        total_gaps += len(gaps)
        per_room.append({
            "room": room.name, "devices": len(here),
            "uncovered_samples": len(gaps),
            "uncovered_examples": gaps[:5],
            "walls_beyond_device_limit": far_from_wall,
            "passes": not gaps and not far_from_wall and bool(here),
        })

        if not here:
            res.findings.append(Finding(
                code="COVERAGE-NO-DEVICE", severity="blocker",
                subject=f"room:{room.name or '(unnamed)'}",
                detail="No device falls inside this room, so nothing covers it.",
                action="Place a device, or record why this room is excluded from "
                       f"{data.rule.rule_code}."))
        elif gaps:
            res.findings.append(Finding(
                code="COVERAGE-GAP", severity="review",
                subject=f"room:{room.name or '(unnamed)'}",
                detail=f"{len(gaps)} sampled point(s) lie further than "
                       f"{reach:.2f} m from the nearest device, which is the reach "
                       f"implied by {data.rule.rule_code}'s {data.rule.max_spacing_m} m "
                       f"spacing. First: {gaps[:3]}.",
                action="Add or move a device to close the gap, or record the "
                       "departure with an engineer's justification."))
        for f in far_from_wall:
            res.findings.append(Finding(
                code="COVERAGE-WALL-DISTANCE", severity="review",
                subject=f"room:{room.name or '(unnamed)'}",
                detail=f"The wall from {f['wall'][0]} to {f['wall'][1]} has no "
                       f"device within {data.rule.max_wall_distance_m} m of it; "
                       f"the nearest is {f['nearest_device_m']} m away, beyond "
                       f"what {data.rule.rule_code} allows.",
                action="Add or move a device so this wall is served within the "
                       "limit."))

    res.outputs = {
        "rule": {"code": data.rule.rule_code, "source": data.rule.source,
                 "max_spacing_m": data.rule.max_spacing_m,
                 "max_wall_distance_m": data.rule.max_wall_distance_m},
        "reach_m": round(reach, 3),
        "rooms_checked": len(per_room),
        "rooms_passing": sum(1 for r in per_room if r["passes"]),
        "uncovered_samples": total_gaps,
        "per_room": per_room,
        "checks_performed": ["spacing reach from each device",
                             "every wall served within the wall limit"],
        "checks_NOT_performed": [
            "ceiling obstructions, beams and bulkheads",
            "airflow, diffuser positions and stratification",
            "ceiling height and slope",
            "listed spacing for the specific detector model",
            "survey and commissioning"],
        "is_compliance_assessment": False,
    }
    res.warnings.append(
        "This is a geometric check against two limits in "
        f"{data.rule.rule_code}, NOT a compliance assessment. Ceiling "
        "obstructions, airflow, ceiling height and the detector's own listed "
        "spacing are not tested and cannot be read off a floor plan.")
    res.duration_ms = int((time.perf_counter() - started) * 1000)
    return res


def _point_to_segment(px, py, a, b) -> float:
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))
