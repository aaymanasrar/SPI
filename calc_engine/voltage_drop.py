"""Voltage drop — AC single/three phase and DC (incl. fire-alarm NAC end-of-line)."""
from __future__ import annotations

import math
from .core import CalcResult, CalcInputError, require_positive, require_range, r
from . import tables as T


def conductor_resistance(size_mm2: float, material: str = "cu",
                         temp_c: float = 70.0) -> float:
    """Ohm/km at operating temperature from IEC 60228 20 °C values."""
    tbl = T.CU_RESISTANCE_20C_OHM_PER_KM if material == "cu" else T.AL_RESISTANCE_20C_OHM_PER_KM
    if size_mm2 not in tbl:
        raise CalcInputError(f"{size_mm2} mm² not in {material} resistance table: {sorted(tbl)}")
    return tbl[size_mm2] * (1 + T.ALPHA_20[material] * (temp_c - 20))


def voltage_drop(current_a: float, length_m: float, size_mm2: float,
                 system: str = "3ph", voltage_v: float = 400.0,
                 power_factor: float = 0.85, material: str = "cu",
                 conductor_temp_c: float = 70.0,
                 reactance_ohm_per_km: float | None = None,
                 limit_pct: float = 5.0) -> CalcResult:
    """
    system: '1ph' | '3ph' | 'dc'
    voltage_v: line-to-line for 3ph, line-to-neutral for 1ph, nominal for dc
    """
    require_positive(current_a=current_a, length_m=length_m, size_mm2=size_mm2,
                     voltage_v=voltage_v, limit_pct=limit_pct)
    if system not in ("1ph", "3ph", "dc"):
        raise CalcInputError("system must be '1ph', '3ph' or 'dc'")
    require_range("power_factor", power_factor, 0.1, 1.0)

    x = T.DEFAULT_REACTANCE_OHM_PER_KM if reactance_ohm_per_km is None else reactance_ohm_per_km
    res = CalcResult("voltage_drop", inputs=dict(
        current_a=current_a, length_m=length_m, size_mm2=size_mm2, system=system,
        voltage_v=voltage_v, power_factor=power_factor, material=material,
        conductor_temp_c=conductor_temp_c, reactance_ohm_per_km=x, limit_pct=limit_pct),
        outputs={})
    rk = conductor_resistance(size_mm2, material, conductor_temp_c)
    res.step(f"R({conductor_temp_c}°C) = R20 × [1 + α(θ−20)] = {r(rk,4)} Ω/km")
    L = length_m / 1000

    if system == "dc":
        dv = 2 * current_a * L * rk
        res.step(f"ΔU = 2 × I × L × R = 2 × {current_a} × {L} × {r(rk,4)} = {r(dv)} V")
        res.assumptions.append("DC: resistive only, go-and-return conductors")
    else:
        phi = math.acos(power_factor)
        z_eff = rk * power_factor + x * math.sin(phi)
        k = 2 if system == "1ph" else math.sqrt(3)
        dv = k * current_a * L * z_eff
        res.step(f"(R cosφ + X sinφ) = {r(rk,4)}×{power_factor} + {x}×{r(math.sin(phi),3)} = {r(z_eff,4)} Ω/km")
        res.step(f"ΔU = {'2' if system=='1ph' else '√3'} × I × L × (R cosφ + X sinφ) = {r(dv)} V")
        if reactance_ohm_per_km is None:
            res.assumptions.append(f"Reactance {x} Ω/km assumed (typical LV multicore) — replace with cable datasheet value")

    pct = dv / voltage_v * 100
    res.step(f"ΔU% = {r(dv)} / {voltage_v} × 100 = {r(pct,2)} %")
    res.outputs = {"voltage_drop_v": r(dv), "voltage_drop_pct": r(pct, 2),
                   "voltage_at_load_v": r(voltage_v - dv, 2), "limit_pct": limit_pct}
    res.passed = pct <= limit_pct
    res.references += ["IEC 60228 (conductor resistance)", "IEC 60364-5-52 Annex G (VD method & limits)"]
    return res


def nac_end_of_line(panel_voltage_v: float, devices_current_a: list[float],
                    length_m: float, awg: int | None = None,
                    size_mm2: float | None = None,
                    min_device_voltage_v: float = 16.0,
                    lumped: bool = True) -> CalcResult:
    """
    Fire-alarm notification appliance circuit (NAC) / sounder circuit end-of-line check.
    lumped=True: worst case, all load assumed at the end of line (conservative).
    Default min device voltage 16 V = typical UL 1971/464 regulated 24 V appliance —
    confirm against the appliance datasheet.
    """
    require_positive(panel_voltage_v=panel_voltage_v, length_m=length_m)
    if not devices_current_a:
        raise CalcInputError("devices_current_a must list at least one device")
    i_total = sum(devices_current_a)
    res = CalcResult("nac_end_of_line", inputs=dict(
        panel_voltage_v=panel_voltage_v, device_count=len(devices_current_a),
        total_current_a=r(i_total, 4), length_m=length_m, awg=awg, size_mm2=size_mm2,
        min_device_voltage_v=min_device_voltage_v, lumped=lumped), outputs={})
    if awg is not None:
        if awg not in T.AWG_RESISTANCE_OHM_PER_KFT_75C:
            raise CalcInputError(f"AWG {awg} not in table")
        r_per_m = T.AWG_RESISTANCE_OHM_PER_KFT_75C[awg] / 304.8
        res.step(f"R = {T.AWG_RESISTANCE_OHM_PER_KFT_75C[awg]} Ω/kft (NEC Ch.9 T8, 75°C) = {r(r_per_m*1000,3)} Ω/km")
        res.references.append("NFPA 70 (NEC) Chapter 9 Table 8")
    elif size_mm2 is not None:
        r_per_m = conductor_resistance(size_mm2, "cu", 75) / 1000
        res.step(f"R = {r(r_per_m*1000,3)} Ω/km at 75°C (IEC 60228)")
    else:
        raise CalcInputError("Give either awg or size_mm2")

    loop_r = 2 * length_m * r_per_m
    res.step(f"Loop resistance = 2 × {length_m} m × {r(r_per_m,6)} Ω/m = {r(loop_r,3)} Ω")
    if lumped:
        dv = i_total * loop_r
        res.step(f"ΔU (lumped at EOL) = {r(i_total,4)} A × {r(loop_r,3)} Ω = {r(dv)} V")
        res.assumptions.append("All appliance load lumped at end of line (conservative)")
    else:
        # evenly distributed: ΔU ≈ I_total × R_loop × (n+1)/(2n)
        n = len(devices_current_a)
        dv = i_total * loop_r * (n + 1) / (2 * n)
        res.step(f"ΔU (evenly distributed, n={n}) = I × R × (n+1)/2n = {r(dv)} V")
        res.assumptions.append("Appliances evenly spaced along circuit")
    v_eol = panel_voltage_v - dv
    res.step(f"V at last device = {panel_voltage_v} − {r(dv)} = {r(v_eol,2)} V")
    res.outputs = {"voltage_drop_v": r(dv), "voltage_at_eol_v": r(v_eol, 2),
                   "voltage_drop_pct": r(dv / panel_voltage_v * 100, 2),
                   "max_length_m_for_min_voltage": r((panel_voltage_v - min_device_voltage_v)
                                                     / (i_total * 2 * r_per_m) *
                                                     (1 if lumped else 2 * len(devices_current_a) / (len(devices_current_a) + 1)), 1)}
    res.passed = v_eol >= min_device_voltage_v
    res.warnings.append("Use panel end-of-battery-discharge voltage (e.g. 20.4 V for 24 V systems) "
                        "as panel_voltage_v for the worst case, not nominal 24 V")
    res.references.append("NFPA 72 §10.14 / manufacturer NAC wiring tables")
    return res
