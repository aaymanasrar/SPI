"""BMS automation-station selection — fit a points schedule to the smallest station."""
from __future__ import annotations

import math
from dataclasses import dataclass
from .core import CalcResult, CalcInputError, require_range, r


@dataclass
class StationModel:
    model: str
    part_number: str
    io_max: int | None            # physical I/O points on modules
    integration_max: int | None   # integration (e.g. BACnet) data points
    mstp_max: int | None          # MS/TP field devices


def bms_station_select(stations: list[StationModel], io_points: int,
                       integration_points: int = 0, mstp_devices: int = 0,
                       spare_pct: float = 20.0) -> CalcResult:
    """
    Each demand is grossed up by spare_pct, then the smallest station meeting ALL
    three limits is chosen. If none fits, the count of the largest station needed
    for the governing limit is reported — splitting by plant/area is a design decision.
    """
    if not stations:
        raise CalcInputError("No station models given")
    require_range("spare_pct", spare_pct, 0, 100)
    for v, n in ((io_points, "io_points"), (integration_points, "integration_points"),
                 (mstp_devices, "mstp_devices")):
        if v is None or v < 0:
            raise CalcInputError(f"{n} must be ≥ 0")
    missing = [f"{s.model}.{f}" for s in stations for f in ("io_max", "integration_max", "mstp_max")
               if getattr(s, f) is None]
    if missing:
        raise CalcInputError("Capacity not captured for: " + ", ".join(missing))

    res = CalcResult("bms_station_select", inputs=dict(
        io_points=io_points, integration_points=integration_points, mstp_devices=mstp_devices,
        spare_pct=spare_pct, stations=[s.__dict__ for s in stations]), outputs={})
    k = 1 + spare_pct / 100
    need = {"io": math.ceil(io_points * k), "integration": math.ceil(integration_points * k),
            "mstp": math.ceil(mstp_devices * k)}
    res.step(f"With {spare_pct}% spare: I/O {need['io']}, integration {need['integration']}, MS/TP {need['mstp']}")

    ordered = sorted(stations, key=lambda s: (s.io_max, s.integration_max, s.mstp_max))
    for s in ordered:
        fits = s.io_max >= need["io"] and s.integration_max >= need["integration"] and s.mstp_max >= need["mstp"]
        res.step(f"{s.model}: I/O {s.io_max}, integ {s.integration_max}, MS/TP {s.mstp_max} → {'fits' if fits else 'no'}")
        if fits:
            res.outputs = {"selected_model": s.model, "part_number": s.part_number, "quantity": 1,
                           "io_utilisation_pct": r(io_points / s.io_max * 100, 1),
                           "integration_utilisation_pct": r(integration_points / s.integration_max * 100, 1),
                           "mstp_utilisation_pct": r(mstp_devices / s.mstp_max * 100, 1)}
            res.passed = True
            return res

    big = ordered[-1]
    counts = {"io": math.ceil(need["io"] / big.io_max),
              "integration": math.ceil(need["integration"] / big.integration_max),
              "mstp": math.ceil(need["mstp"] / big.mstp_max)}
    qty = max(counts.values())
    gov = max(counts, key=counts.get)
    res.step(f"No single station fits → {qty} × {big.model} (governed by {gov})")
    res.outputs = {"selected_model": big.model, "part_number": big.part_number, "quantity": qty,
                   "governing_limit": gov}
    res.passed = True
    res.warnings.append("Multiple stations required — split points by plant/area, not evenly by count")
    return res
