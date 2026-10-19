"""Access-control lock/reader power supply sizing (rule AC-09) with release-surge check."""
from __future__ import annotations

from dataclasses import dataclass
from .core import CalcResult, CalcInputError, require_positive, r

STANDARD_ACCESS_PSU_A = [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10, 12, 15, 20]


@dataclass
class LockLoad:
    name: str
    qty: int
    holding_ma: float | None            # steady current while energised
    inrush_ma: float | None = None      # release/energise surge (electric strikes); None = same as holding
    part_number: str = ""


@dataclass
class ReaderLoad:
    name: str
    qty: int
    current_ma: float | None            # max operating current
    part_number: str = ""


def lock_psu(locks: list[LockLoad], readers: list[ReaderLoad], voltage_v: float,
             controller_on_same_psu: bool, controller_ma: float | None = None,
             controller_qty: int = 1, margin: float = 1.25,
             simultaneous_releases: int = 0,
             psu_rating_a: float | None = None) -> CalcResult:
    """
    AC-09 (as extended):  I_PSU ≥ margin × (Σ I_lock + Σ I_reader [+ Σ I_controller])
    controller_on_same_psu must be stated explicitly — there is no default, because
    silently leaving the controller out undersizes the supply.
    Surge check: steady + (inrush − holding) for the N largest-surge locks released
    together must not exceed the PSU rating.
    psu_rating_a: check a proposed PSU; if None, the next standard rating is selected.
    """
    require_positive(voltage_v=voltage_v, margin=margin)
    missing = [f"{l.name}.holding_ma" for l in locks if l.holding_ma is None]
    missing += [f"{rd.name}.current_ma" for rd in readers if rd.current_ma is None]
    if controller_on_same_psu and controller_ma is None:
        missing.append("controller_ma")
    if missing:
        raise CalcInputError("Current not captured for: " + ", ".join(missing) +
                             ". Take the figure from the manufacturer datasheet. A missing current is not zero.")
    if not locks and not readers:
        raise CalcInputError("No loads given")

    res = CalcResult("lock_psu", inputs=dict(
        voltage_v=voltage_v, controller_on_same_psu=controller_on_same_psu,
        controller_ma=controller_ma, controller_qty=controller_qty, margin=margin,
        simultaneous_releases=simultaneous_releases, psu_rating_a=psu_rating_a,
        locks=[l.__dict__ for l in locks], readers=[x.__dict__ for x in readers]), outputs={})

    i_lock = sum(l.qty * l.holding_ma for l in locks) / 1000
    i_rdr = sum(x.qty * x.current_ma for x in readers) / 1000
    i_ctl = controller_qty * controller_ma / 1000 if controller_on_same_psu else 0.0
    for l in locks:
        res.step(f"{l.name} ×{l.qty}: {r(l.qty*l.holding_ma,1)} mA holding")
    for x in readers:
        res.step(f"{x.name} ×{x.qty}: {r(x.qty*x.current_ma,1)} mA")
    if controller_on_same_psu:
        res.step(f"Controller ×{controller_qty}: {r(controller_qty*controller_ma,1)} mA (same PSU)")
    else:
        res.assumptions.append("Controller powered from a separate supply — confirm on the wiring diagram")
    steady = i_lock + i_rdr + i_ctl
    required = margin * steady
    res.step(f"Steady = {r(i_lock,3)} + {r(i_rdr,3)} + {r(i_ctl,3)} = {r(steady,3)} A")
    res.step(f"Required = {margin} × {r(steady,3)} = {r(required,3)} A")

    # surge: largest (inrush - holding) deltas, one per released door
    deltas = sorted([max((l.inrush_ma or l.holding_ma) - l.holding_ma, 0) for l in locks
                     for _ in range(l.qty)], reverse=True)
    n = min(simultaneous_releases, len(deltas))
    peak = steady + sum(deltas[:n]) / 1000
    if simultaneous_releases:
        res.step(f"Peak = steady + {n} largest release surges = {r(peak,3)} A")
    if simultaneous_releases and all(l.inrush_ma is None for l in locks):
        res.warnings.append("No lock inrush current captured — surge check equals steady state")

    need = max(required, peak)
    if psu_rating_a is None:
        sel = next((a for a in STANDARD_ACCESS_PSU_A if a >= need), None)
        if sel is None:
            raise CalcInputError(f"{r(need,2)} A exceeds largest standard PSU — split across supplies")
        res.step(f"Selected next standard rating ≥ {r(need,3)} A → {sel} A")
    else:
        sel = psu_rating_a
    ac09 = sel >= required
    surge_ok = sel >= peak
    res.outputs = {"steady_a": r(steady, 3), "required_a_ac09": r(required, 3), "peak_a": r(peak, 3),
                   "psu_rating_a": sel, "psu_voltage_v": voltage_v,
                   "ac09_pass": ac09, "surge_pass": surge_ok, "spare_a": r(sel - need, 3)}
    res.passed = ac09 and surge_ok
    if not surge_ok:
        res.warnings.append("PSU meets AC-09 steady rule but not the simultaneous-release surge")
    res.assumptions.append("All locks treated as energised together (AC-09 as written) — conservative "
                           "for fail-secure strikes, exact for fail-safe maglocks")
    res.references.append("Project rule AC-09 (margin configurable)")
    return res
