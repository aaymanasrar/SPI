"""Cable sizing — ampacity with derating, protective-device coordination, VD and short-circuit checks."""
from __future__ import annotations

import math
from .core import CalcResult, CalcInputError, require_positive, r
from . import tables as T
from .voltage_drop import voltage_drop


def _lookup_factor(tbl: dict, key: float, name: str) -> float:
    # conservative: next higher temperature / next larger group count
    keys = sorted(tbl)
    for k in keys:
        if key <= k:
            return tbl[k]
    raise CalcInputError(f"{name} {key} outside table range {keys[0]}–{keys[-1]}")


def cable_sizing(design_current_a: float, length_m: float, system: str = "3ph",
                 voltage_v: float = 400.0, power_factor: float = 0.85,
                 insulation: str = "xlpe", method: str = "C",
                 ambient_c: float = 40.0, grouped_circuits: int = 1,
                 other_factor: float = 1.0, vd_limit_pct: float = 4.0,
                 fault_current_ka: float | None = None, disconnect_time_s: float = 0.1,
                 breaker_a: float | None = None) -> CalcResult:
    """
    1. In ≥ Ib (next standard rating unless breaker_a given)
    2. Iz = It × Ca × Cg × Ci ≥ In   (IEC 60364-4-43 §433.1; I2 ≤ 1.45 Iz is met for
       breakers to IEC 60898/60947-2 where I2 = 1.45 In)
    3. Voltage drop ≤ limit — upsize if not
    4. Optional adiabatic check: S ≥ √(I²t)/k
    Ambient 40 °C default reflects Gulf indoor plant rooms — use 50 °C+ for outdoor/roof.
    Copper only.
    """
    require_positive(design_current_a=design_current_a, length_m=length_m, voltage_v=voltage_v)
    loaded = 3 if system == "3ph" else 2
    key = (insulation, method, loaded)
    if key not in T.AMPACITY_CU:
        raise CalcInputError(f"No ampacity table for {key}. Available: {list(T.AMPACITY_CU)}")
    res = CalcResult("cable_sizing", inputs=dict(
        design_current_a=design_current_a, length_m=length_m, system=system, voltage_v=voltage_v,
        power_factor=power_factor, insulation=insulation, method=method, ambient_c=ambient_c,
        grouped_circuits=grouped_circuits, other_factor=other_factor, vd_limit_pct=vd_limit_pct,
        fault_current_ka=fault_current_ka, disconnect_time_s=disconnect_time_s,
        breaker_a=breaker_a), outputs={})

    In = breaker_a or next((b for b in T.STANDARD_BREAKER_A if b >= design_current_a), None)
    if In is None or In < design_current_a:
        raise CalcInputError("Protective device rating must be ≥ design current")
    res.step(f"Ib = {design_current_a} A → In = {In} A")

    ca = _lookup_factor(T.TEMP_CORRECTION_AIR[insulation], ambient_c, "Ambient")
    cg = _lookup_factor(T.GROUPING_BUNCHED, grouped_circuits, "Group count")
    k_all = ca * cg * other_factor
    res.step(f"Ca({ambient_c}°C, {insulation.upper()}) = {ca} ; Cg({grouped_circuits}) = {cg} ; Ci = {other_factor} → {r(k_all,3)}")
    it_req = In / k_all
    res.step(f"Required tabulated It ≥ In / factors = {In} / {r(k_all,3)} = {r(it_req,1)} A")

    table = T.AMPACITY_CU[key]
    size_amp = next((s for s in sorted(table) if table[s] >= it_req), None)
    if size_amp is None:
        raise CalcInputError(f"No single cable in table meets {r(it_req,1)} A — use parallel runs")
    res.step(f"Smallest size by ampacity: {size_amp} mm² (It {table[size_amp]} A, method {method}, {loaded} loaded)")

    size = size_amp
    vd = voltage_drop(design_current_a, length_m, size, system if system != "dc" else "dc",
                      voltage_v, power_factor, "cu", 90 if insulation == "xlpe" else 70,
                      limit_pct=vd_limit_pct)
    while not vd.passed:
        bigger = [s for s in sorted(table) if s > size]
        if not bigger:
            res.warnings.append("VD limit not met even at largest size — parallel conductors needed")
            break
        size = bigger[0]
        vd = voltage_drop(design_current_a, length_m, size, system, voltage_v, power_factor, "cu",
                          90 if insulation == "xlpe" else 70, limit_pct=vd_limit_pct)
    if size != size_amp:
        res.step(f"Upsized to {size} mm² for voltage drop")
    res.step(f"VD at {size} mm² = {vd.outputs['voltage_drop_pct']} % (limit {vd_limit_pct} %)")

    sc_ok = True
    s_min = None
    if fault_current_ka:
        kf = T.K_FACTOR[("cu", insulation)]
        s_min = math.sqrt((fault_current_ka * 1000) ** 2 * disconnect_time_s) / kf
        sc_ok = size >= s_min
        res.step(f"Adiabatic: S ≥ √(I²t)/k = √({fault_current_ka} kA² × {disconnect_time_s} s)/{kf} = {r(s_min,1)} mm² → {'OK' if sc_ok else 'FAIL'}")
        res.references.append("IEC 60364-5-54 / 4-43 §434.5.2 adiabatic equation")
        if not sc_ok:
            res.warnings.append(f"Short-circuit withstand requires ≥ {r(s_min,1)} mm² or faster disconnection")

    iz = table[size] * k_all
    res.outputs = {"breaker_in_a": In, "selected_size_mm2": size, "size_by_ampacity_mm2": size_amp,
                   "derated_iz_a": r(iz, 1), "voltage_drop_pct": vd.outputs["voltage_drop_pct"],
                   "min_size_short_circuit_mm2": r(s_min, 1) if s_min else None}
    res.passed = vd.passed and sc_ok and iz >= In
    res.assumptions.append("Copper conductors; earth/CPC sizing not included")
    res.references += ["IEC 60364-5-52 Annex B (ampacity & correction factors)",
                       "IEC 60364-4-43 §433.1 (Ib ≤ In ≤ Iz)"] + vd.references
    return res
