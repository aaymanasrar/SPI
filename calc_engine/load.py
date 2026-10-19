"""Electrical load schedule — demand, per-phase balancing, design current."""
from __future__ import annotations

import math
from dataclasses import dataclass
from .core import CalcResult, CalcInputError, require_positive, r


@dataclass
class Load:
    name: str
    qty: int
    watts: float                  # per unit
    power_factor: float = 0.9
    demand_factor: float = 1.0    # fraction of connected load expected to run
    phase: str = "auto"           # 'L1','L2','L3','3ph','auto'


def load_schedule(loads: list[Load], voltage_ll_v: float = 400.0,
                  diversity_factor: float = 1.0, spare_pct: float = 20.0) -> CalcResult:
    """
    Single-phase loads on 'auto' are placed on the least-loaded phase (largest first).
    Design current per phase I = S_phase / U_phase ; balanced 3ph I = S / (√3 × U_LL).
    """
    if not loads:
        raise CalcInputError("Load list is empty")
    require_positive(voltage_ll_v=voltage_ll_v, diversity_factor=diversity_factor)
    u_ph = voltage_ll_v / math.sqrt(3)
    res = CalcResult("load_schedule", inputs=dict(
        voltage_ll_v=voltage_ll_v, diversity_factor=diversity_factor, spare_pct=spare_pct,
        loads=[l.__dict__ for l in loads]), outputs={})
    ph = {"L1": 0.0, "L2": 0.0, "L3": 0.0}   # kVA per phase (demand)
    conn_kw = dem_kw = 0.0
    order = sorted(loads, key=lambda l: -(l.qty * l.watts))
    for l in order:
        ck = l.qty * l.watts / 1000
        dk = ck * l.demand_factor
        dkva = dk / l.power_factor
        conn_kw += ck
        dem_kw += dk
        if l.phase == "3ph":
            for p in ph:
                ph[p] += dkva / 3
            where = "3ph"
        elif l.phase in ph:
            ph[l.phase] += dkva
            where = l.phase
        elif l.phase == "auto":
            where = min(ph, key=ph.get)
            ph[where] += dkva
        else:
            raise CalcInputError(f"{l.name}: phase must be L1/L2/L3/3ph/auto")
        res.step(f"{l.name}: {r(ck,3)} kW conn × DF {l.demand_factor} = {r(dk,3)} kW / PF {l.power_factor} "
                 f"= {r(dkva,3)} kVA → {where}")
    for p in ph:
        ph[p] *= diversity_factor / 1.0
    total_kva = sum(ph.values())
    i_ph = {p: v * 1000 / u_ph for p, v in ph.items()}
    i_max = max(i_ph.values())
    i_avg = sum(i_ph.values()) / 3
    imb = (i_max - i_avg) / i_avg * 100 if i_avg else 0
    res.step(f"Diversity {diversity_factor} applied; phase kVA = { {p: r(v,3) for p, v in ph.items()} }")
    res.step(f"I_phase = S_phase / {r(u_ph,1)} V → { {p: r(v,2) for p, v in i_ph.items()} } A")
    res.step(f"Imbalance = (Imax − Iavg)/Iavg = {r(imb,1)} %")
    design_i = i_max * (1 + spare_pct / 100)
    res.outputs = {"connected_kw": r(conn_kw, 3), "demand_kw": r(dem_kw * diversity_factor, 3),
                   "demand_kva": r(total_kva, 3),
                   "phase_kva": {p: r(v, 3) for p, v in ph.items()},
                   "phase_current_a": {p: r(v, 2) for p, v in i_ph.items()},
                   "imbalance_pct": r(imb, 1),
                   "design_current_a_incl_spare": r(design_i, 2)}
    res.passed = imb <= 10
    if imb > 10:
        res.warnings.append("Phase imbalance > 10 % — re-assign single-phase loads")
    res.references.append("Demand/diversity per project design basis (e.g. SBC 401 / SAES-P-100)")
    return res
