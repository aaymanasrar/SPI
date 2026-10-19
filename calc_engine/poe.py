"""PoE budget — per-port class assignment and switch total budget check."""
from __future__ import annotations

from dataclasses import dataclass
from .core import CalcResult, CalcInputError, require_positive, r
from . import tables as T


@dataclass
class PoEDevice:
    name: str
    qty: int
    poe_class: int | None = None      # IEEE class 0-8 (preferred)
    max_draw_w: float | None = None   # datasheet max consumption at PD (if class unknown)
    cable_m: float = 90.0
    part_number: str = ""


def poe_budget(devices: list[PoEDevice], switch_budget_w: float,
               port_count: int | None = None, max_port_class: int | None = None,
               port_classes: list[int] | None = None,
               allocation: str = "class", headroom_pct: float = 20.0) -> CalcResult:
    """
    Port capability — give ONE of:
      port_classes   : max class of each PoE port, e.g. XC208G = [6, 6, 4, 4, 4, 4]  (preferred)
      port_count + max_port_class : legacy uniform model (every port same capability)
    Devices are assigned highest class first to the most capable free port;
    a device that finds no capable port fails the check.
    allocation='class' : switch reserves the PSE power of the class (IEEE worst case)
    allocation='actual': PD draw + cable loss estimate (LLDP/actual power mode)
    """
    require_positive(switch_budget_w=switch_budget_w)
    if allocation not in ("class", "actual"):
        raise CalcInputError("allocation must be 'class' or 'actual'")
    if port_classes is None:
        if port_count is None or max_port_class is None:
            raise CalcInputError("Give port_classes, or port_count and max_port_class")
        require_positive(port_count=port_count)
        port_classes = [max_port_class] * port_count
        uniform = True
    else:
        if not port_classes or any(c not in T.POE_CLASSES for c in port_classes):
            raise CalcInputError("port_classes must list classes 0-8, one per PoE port")
        uniform = False

    res = CalcResult("poe_budget", inputs=dict(
        switch_budget_w=switch_budget_w, port_classes=port_classes, allocation=allocation,
        headroom_pct=headroom_pct, devices=[d.__dict__ for d in devices]), outputs={})
    if uniform:
        res.assumptions.append("Uniform port model — every port assumed capable of Class "
                               f"{port_classes[0]}; use port_classes for mixed at/bt switches")

    # 1. resolve each device's class
    units = []   # one entry per physical device
    total_w = 0.0
    ok = True
    for d in devices:
        if d.poe_class is None and d.max_draw_w is None:
            raise CalcInputError(f"{d.name}: give poe_class or max_draw_w")
        cls = d.poe_class
        if cls is None:
            cls = next((c for c in (1, 2, 3, 4, 5, 6, 7, 8) if T.POE_CLASSES[c]["pd_w"] >= d.max_draw_w), None)
            if cls is None:
                raise CalcInputError(f"{d.name}: {d.max_draw_w} W exceeds 802.3bt Class 8 (71.3 W at PD)")
            res.step(f"{d.name}: {d.max_draw_w} W at PD → needs Class {cls}")
        c = T.POE_CLASSES[cls]
        if d.cable_m > T.POE_MAX_CHANNEL_M:
            ok = False
            res.warnings.append(f"{d.name}: {d.cable_m} m exceeds 100 m channel limit")
        if allocation == "class":
            per = c["pse_w"]
        else:
            draw = d.max_draw_w if d.max_draw_w is not None else c["pd_w"]
            per = draw + (c["pse_w"] - c["pd_w"]) * min(d.cable_m, 100) / 100
        total_w += per * d.qty
        res.step(f"{d.name} ×{d.qty}: Class {cls} ({c['std']}) → {r(per,2)} W/port → {r(per*d.qty,2)} W")
        units += [(cls, d.name)] * d.qty

    # 2. port assignment: most demanding device → most capable free port
    free = sorted(port_classes, reverse=True)
    unplaced = {}
    for cls, name in sorted(units, key=lambda u: -u[0]):
        if free and free[0] >= cls:
            free.pop(0)
        else:
            unplaced[name] = unplaced.get(name, 0) + 1
            ok = False
    cap = {k: port_classes.count(k) for k in sorted(set(port_classes), reverse=True)}
    res.step(f"Ports by max class: { {f'Class {k}': v for k, v in cap.items()} }")
    for name, n in unplaced.items():
        res.warnings.append(f"{name}: {n} device(s) have no port able to deliver their class")

    usable = switch_budget_w * (1 - headroom_pct / 100)
    res.step(f"Total PSE demand = {r(total_w,2)} W vs usable {switch_budget_w} × (1 − {headroom_pct}%) = {r(usable,2)} W")
    budget_ok = total_w <= usable
    if not budget_ok:
        res.warnings.append("PoE budget exceeded — add a switch or a higher-budget PSU")
    res.outputs = {"total_poe_demand_w": r(total_w, 2), "usable_budget_w": r(usable, 2),
                   "utilisation_pct": r(total_w / switch_budget_w * 100, 1),
                   "ports_used": len(units) - sum(unplaced.values()),
                   "ports_available": len(port_classes),
                   "devices_unplaced": sum(unplaced.values()),
                   "spare_w": r(usable - total_w, 2)}
    res.passed = ok and budget_ok
    res.references += ["IEEE 802.3af/at/bt (Clause 33 & 145) power classes"]
    return res
