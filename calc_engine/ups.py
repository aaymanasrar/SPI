"""UPS sizing — kVA/kW rating selection plus runtime battery (delegates to battery module)."""
from __future__ import annotations

from dataclasses import dataclass
from .core import CalcResult, CalcInputError, require_positive, require_range, r
from . import tables as T
from .battery import dc_battery_bank


@dataclass
class UPSLoad:
    name: str
    qty: int
    watts: float
    power_factor: float = 0.9


def ups_sizing(loads: list[UPSLoad], runtime_min: float, ups_output_pf: float = 0.9,
               growth_pct: float = 20.0, max_loading_pct: float = 80.0,
               battery_bus_v: float = 192.0, inverter_eff: float = 0.92,
               depth_of_discharge: float = 0.8, redundancy: str = "N") -> CalcResult:
    """
    Required kVA = max(ΣkW / UPS output PF, ΣkVA) × (1+growth) / max_loading.
    redundancy: 'N' or 'N+1' (adds one module of the selected rating).
    """
    if not loads:
        raise CalcInputError("Load list is empty")
    require_positive(runtime_min=runtime_min, battery_bus_v=battery_bus_v)
    require_range("ups_output_pf", ups_output_pf, 0.5, 1.0)
    res = CalcResult("ups_sizing", inputs=dict(
        runtime_min=runtime_min, ups_output_pf=ups_output_pf, growth_pct=growth_pct,
        max_loading_pct=max_loading_pct, battery_bus_v=battery_bus_v,
        inverter_eff=inverter_eff, depth_of_discharge=depth_of_discharge,
        redundancy=redundancy, loads=[l.__dict__ for l in loads]), outputs={})
    kw = sum(l.qty * l.watts for l in loads) / 1000
    kva = sum(l.qty * l.watts / l.power_factor for l in loads) / 1000
    res.step(f"ΣP = {r(kw,3)} kW ; ΣS = {r(kva,3)} kVA")
    kva_from_kw = kw / ups_output_pf
    base = max(kva, kva_from_kw)
    res.step(f"Governing = max(ΣS {r(kva,3)}, ΣP/PF_ups {r(kva_from_kw,3)}) = {r(base,3)} kVA")
    req = base * (1 + growth_pct / 100) / (max_loading_pct / 100)
    res.step(f"× (1 + {growth_pct}%) / {max_loading_pct}% = {r(req,3)} kVA required rating")
    sel = next((k for k in T.STANDARD_UPS_KVA if k >= req), None)
    if sel is None:
        raise CalcInputError(f"{r(req,1)} kVA exceeds standard table — use parallel modules")
    modules = 2 if redundancy == "N+1" else 1
    res.step(f"Selected {sel} kVA ({redundancy}{', 2 modules' if modules == 2 else ''})")

    bat = dc_battery_bank(load_w=kw * 1000 * (1 + growth_pct / 100), runtime_h=runtime_min / 60,
                          bank_voltage_v=battery_bus_v, inverter_eff=inverter_eff,
                          depth_of_discharge=depth_of_discharge)
    res.step(f"Battery: {bat.outputs['total_blocks']} × 12 V {bat.outputs['block_ah']} Ah "
             f"({bat.outputs['blocks_in_series']}S{bat.outputs['parallel_strings']}P) for {runtime_min} min")
    res.outputs = {"load_kw": r(kw, 3), "load_kva": r(kva, 3), "required_kva": r(req, 2),
                   "selected_ups_kva": sel, "selected_ups_kw": r(sel * ups_output_pf, 2),
                   "modules": modules, "loading_at_day1_pct": r(base / sel * 100, 1),
                   "battery": bat.outputs}
    res.passed = True
    res.assumptions += bat.assumptions
    res.references += ["IEC 62040-3 (UPS performance)"] + bat.references
    return res
