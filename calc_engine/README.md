# calc_engine

Deterministic engineering maths, separate from the AI layer. Ten modules, each
returning a `CalcResult` with inputs, steps, assumptions, warnings, references
and a pass/fail — `result.report()` prints a calc sheet you can paste into a
design basis or TBE annex.

```
AI layer   decides a calculation is needed, gathers inputs
KB layer   supplies manufacturer data (quiescent current, PoE class, bitrate)
engine     does the maths and shows its working
```

No module imports an AI/LLM library or makes a network call.

## Modules

| Module | Computes | Bound to rules |
|---|---|---|
| `fire_alarm_battery` | FACP standby + alarm battery | FA-18, B-11 |
| `nac_end_of_line` | NAC / sounder circuit end-of-line voltage | FA-19 |
| `poe_budget` | PoE class demand vs switch budget | CC-07, NW-01, NW-02, C-02, C-03 |
| `network_bandwidth` | Stream aggregation and link utilisation | CC-06, LP-24 |
| `video_storage` | Retention → TB, RAID and disk count | CC-04, KSA-CCTV-04, LP-07, LP-20, LP-21 |
| `ups_sizing` | kVA selection + runtime battery | UP-01 |
| `dc_battery_bank` | Battery bank Ah | UP-02, LP-19, LP-30, LP-31 |
| `voltage_drop` | AC 1ph/3ph and DC volt drop | *(no rule yet)* |
| `load_schedule` | Demand, phase balance, design current | *(no rule yet)* |
| `cable_sizing` | Ampacity, derating, VD, adiabatic check | *(no rule yet)* |

The last three are new capability: nothing in the 181 rules covers LV cable
sizing or load scheduling. Worth adding rules for them, or they stay invisible
to anyone reading a pack.

## Verified against the rules library

`fire_alarm_battery` reproduces the FA-18 calculator exactly — 0.45 A standby,
2.8 A alarm, 24 h + 5 min, ×1.2 → **13.24 Ah**, the workbook's own example value.

## Known gaps

- **`safety_factor` default is 1.25; rule FA-18 says 1.2.** Both are defensible
  (1.2–1.25 is the common band) but the default and the rule disagree. Pass the
  factor explicitly, or align one to the other.
- **`cable_sizing` auto-upsizes for voltage drop but not for short-circuit.**
  It warns and returns `passed = False`, leaving the engineer to choose between
  a bigger cable and a faster disconnection. Deliberate-looking, but undocumented.
- **`video_storage` has no upper bound on array growth.** A large enough `need`
  walks `n` up indefinitely; there is no cap and no "use multiple arrays" exit.
- **`load_schedule` places a whole line on one phase.** `Load(qty=2, watts=800)`
  puts all 1600 W on a single phase rather than splitting two units across two.
  Model each unit separately if you want them balanced.
- **`tables.py` carries the standing warning**: values are transcribed as commonly
  published and are fit for pre-sales sizing. Verify against a licensed copy
  before an IFC issue.

## Use

```python
import calc_engine as ce
from calc_engine import DeviceLoad

res = ce.fire_alarm_battery(
    [DeviceLoad("Panel + devices", 1, standby_ma=450, alarm_ma=2800)],
    preset="nfpa72", safety_factor=1.2)

print(res.outputs["required_ah"])   # 13.24
print(res.report())                  # full calc sheet
```

The AI layer should call modules by name through `calc_engine.REGISTRY` only.
