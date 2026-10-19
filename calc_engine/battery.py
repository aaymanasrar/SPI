"""Battery sizing — fire alarm standby batteries and general DC / UPS battery banks."""
from __future__ import annotations

import math
from dataclasses import dataclass
from .core import CalcResult, CalcInputError, require_positive, r
from . import tables as T

# Standby/alarm duration presets. Factors are configurable — confirm against the
# project spec and the authority having jurisdiction (AHJ).
PRESETS = {
    "nfpa72":        {"standby_h": 24, "alarm_min": 5,  "ref": "NFPA 72 §10.6.7.2 (24 h + 5 min)"},
    "nfpa72_evacs":  {"standby_h": 24, "alarm_min": 15, "ref": "NFPA 72 §10.6.7.2 (EVACS: 24 h + 15 min)"},
    "en54_4":        {"standby_h": 24, "alarm_min": 30, "ref": "EN 54-4 / BS 5839-1 typical (24 h + 30 min)"},
    "en54_4_72h":    {"standby_h": 72, "alarm_min": 30, "ref": "EN 54-4 / BS 5839-1 unmonitored (72 h + 30 min)"},
}


@dataclass
class DeviceLoad:
    name: str
    qty: int
    standby_ma: float | None      # per device; None = not captured (never treated as 0)
    alarm_ma: float | None        # per device; None = not captured (never treated as 0)
    part_number: str = ""  # optional: ties the line to the knowledge base


def fire_alarm_battery(devices: list[DeviceLoad], preset: str = "nfpa72",
                       standby_h: float | None = None, alarm_min: float | None = None,
                       safety_factor: float = 1.25, battery_voltage_v: float = 24.0) -> CalcResult:
    """
    C (Ah) = [ΣI_standby × T_standby + ΣI_alarm × T_alarm] × safety_factor
    Result is rounded up to the next standard 12 V VRLA block (2 in series for 24 V).
    safety_factor: 1.2–1.25 is common practice (ageing/temperature). Use the value
    in the project spec or the panel manufacturer's battery calculation.
    """
    if preset not in PRESETS and (standby_h is None or alarm_min is None):
        raise CalcInputError(f"Unknown preset '{preset}'. Use {list(PRESETS)} or pass standby_h & alarm_min")
    p = PRESETS.get(preset, {})
    t_sb = standby_h if standby_h is not None else p["standby_h"]
    t_al = (alarm_min if alarm_min is not None else p["alarm_min"]) / 60
    require_positive(t_standby=t_sb, t_alarm=t_al, safety_factor=safety_factor)
    if not devices:
        raise CalcInputError("Device list is empty")
    # A missing current is NOT a zero. The catalogue stores NULL for "not
    # captured", and a detector with no alarm figure silently contributing 0 A
    # would undersize the battery on the one duty that matters.
    missing = [f"{d.name}.{f}" for d in devices for f in ("standby_ma", "alarm_ma")
               if getattr(d, f) is None]
    if missing:
        raise CalcInputError(
            "Current not captured for: " + ", ".join(missing) +
            ". Take the figure from the manufacturer datasheet or the panel "
            "battery calculation tool. A missing current is not zero.")

    res = CalcResult("fire_alarm_battery", inputs=dict(
        preset=preset, standby_h=t_sb, alarm_h=r(t_al, 4), safety_factor=safety_factor,
        battery_voltage_v=battery_voltage_v,
        devices=[d.__dict__ for d in devices]), outputs={})
    i_sb = sum(d.qty * d.standby_ma for d in devices) / 1000
    i_al = sum(d.qty * d.alarm_ma for d in devices) / 1000
    for d in devices:
        res.step(f"{d.name} ×{d.qty}: standby {r(d.qty*d.standby_ma,3)} mA, alarm {r(d.qty*d.alarm_ma,3)} mA")
    res.step(f"ΣI_standby = {r(i_sb,4)} A ; ΣI_alarm = {r(i_al,4)} A")
    ah_sb = i_sb * t_sb
    ah_al = i_al * t_al
    res.step(f"Standby Ah = {r(i_sb,4)} × {t_sb} h = {r(ah_sb)} Ah")
    res.step(f"Alarm Ah = {r(i_al,4)} × {r(t_al,4)} h = {r(ah_al)} Ah")
    c = (ah_sb + ah_al) * safety_factor
    res.step(f"C = ({r(ah_sb)} + {r(ah_al)}) × {safety_factor} = {r(c)} Ah")
    std = next((a for a in T.STANDARD_BATTERY_AH if a >= c), None)
    n_series = math.ceil(battery_voltage_v / 12)
    res.outputs = {"standby_current_a": r(i_sb, 4), "alarm_current_a": r(i_al, 4),
                   "required_ah": r(c, 2),
                   "selected_battery": f"{n_series} × 12 V {std} Ah" if std else "exceeds table — split or use larger bank",
                   "selected_ah": std}
    res.passed = std is not None
    if std is None:
        res.warnings.append("Required capacity exceeds largest standard block in table")
    res.assumptions.append("Panel's own quiescent and alarm current must be included as a device line")
    res.references.append(p.get("ref", "User-defined durations"))
    return res


def dc_battery_bank(load_w: float, runtime_h: float, bank_voltage_v: float,
                    inverter_eff: float = 1.0, depth_of_discharge: float = 0.8,
                    ageing_factor: float = 1.25, temp_factor: float = 1.0,
                    design_margin: float = 1.0) -> CalcResult:
    """
    Ah = (P × t) / (V × η × DoD) × ageing × temperature × margin
    Constant-power approximation. ageing 1.25 per IEEE 485 (end-of-life at 80 %).
    For UPS runtime, set inverter_eff to the UPS DC→AC efficiency (e.g. 0.92).
    """
    require_positive(load_w=load_w, runtime_h=runtime_h, bank_voltage_v=bank_voltage_v,
                     inverter_eff=inverter_eff, depth_of_discharge=depth_of_discharge)
    res = CalcResult("dc_battery_bank", inputs=dict(
        load_w=load_w, runtime_h=runtime_h, bank_voltage_v=bank_voltage_v,
        inverter_eff=inverter_eff, depth_of_discharge=depth_of_discharge,
        ageing_factor=ageing_factor, temp_factor=temp_factor, design_margin=design_margin),
        outputs={})
    wh = load_w * runtime_h / inverter_eff
    res.step(f"Energy from battery = {load_w} W × {runtime_h} h / {inverter_eff} = {r(wh,1)} Wh")
    ah = wh / bank_voltage_v / depth_of_discharge
    res.step(f"Ah = {r(wh,1)} / {bank_voltage_v} V / DoD {depth_of_discharge} = {r(ah,2)} Ah")
    ah_final = ah * ageing_factor * temp_factor * design_margin
    res.step(f"× ageing {ageing_factor} × temp {temp_factor} × margin {design_margin} = {r(ah_final,2)} Ah")
    std = next((a for a in T.STANDARD_BATTERY_AH if a >= ah_final), None)
    n_series = math.ceil(bank_voltage_v / 12)
    strings = 1
    if std is None:
        strings = math.ceil(ah_final / T.STANDARD_BATTERY_AH[-1])
        std = next(a for a in T.STANDARD_BATTERY_AH if a * strings >= ah_final)
    res.outputs = {"energy_wh": r(wh, 1), "required_ah": r(ah_final, 2),
                   "blocks_in_series": n_series, "parallel_strings": strings,
                   "block_ah": std, "total_blocks": n_series * strings,
                   "discharge_current_a": r(load_w / inverter_eff / bank_voltage_v, 2)}
    res.passed = True
    res.assumptions.append("Constant-power discharge; Peukert effect not modelled — confirm with battery "
                           "manufacturer constant-power (W/cell) discharge tables for runtimes < 1 h")
    res.references.append("IEEE 485 (ageing factor 1.25, temperature correction)")
    return res
