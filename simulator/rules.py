"""Pull the rules the simulator applies out of the rules library migration.

The simulator turns a handful of rules into numbers — a 6.37 m detection
radius, 250 px/m for identification. Those numbers are written in sim code, and
the rule text they come from lives in supabase/migrations/0017. This script
copies the rule text into the page verbatim, and refuses to build if the text
no longer says what the code assumes. A library edit then breaks the build
instead of silently disagreeing with the page.

    python simulator/rules.py > out/simulator/rules.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "0017_spt_engineering_rules_library.sql"

COLUMNS = ["system_code", "rule_code", "source_rule_id", "rule_name", "confidence",
           "jurisdiction", "standard_reference", "priority", "source_verified",
           "verification_note", "jurisdiction_overlay", "conditions", "inputs",
           "calculation", "outputs", "exceptions"]

# rule code -> text that must appear in its value_limit or calculation, because
# simulator code depends on it. Keep in step with simulator/sim/20-analysis.js.
EXPECT = {
    "SPT-FA-01": ["9.1 m"],
    "SPT-FA-02": ["0.7 x S", "6.37 m"],
    "SPT-FA-04": ["3-3.7 m:0.91", "8.5-9.1:0.34"],
    "SPT-FA-13": ["15 dB above avg ambient", "5 dB above max ambient", "max 110 dBA"],
    "SPT-FA-15": ["2.03-2.44 m"],
    "SPT-CC-01": ["Detect 25 px/m", "Observe 62.5", "Recognise 125", "Identify 250"],
    "SPT-CC-03": ["d_max = H_res / (PPM x 2 tan(HFOV/2))", "2688 px, 90 deg HFOV, 250 px/m -> 5.4 m"],
    "SPT-CC-09": ["1.6"],
    # Placement rules used to propose a device layout (--device-rules).
    "SPT-FA-03": ["<= S/2 (4.55 m) from walls"],
    "SPT-FA-11": ["Within 1.5 m (5 ft) of each exit door"],
    "SPT-FA-12": ["1.07-1.22 m"],
    "SPT-FA-16": ["20.7x20.7"],
    "SPT-FA-17": ["<= 4.6 m from end", "<= 30.5 m apart"],
    "SPT-AC-02": ["within 1.5 m of door at 1.0-1.2 m AFF"],
    "SPT-AC-06": ["<= 1.22 m AFF"],
    "SPT-AC-08": ["Door position switch + REX on every controlled door"],
    "SPT-SC-10": [">= 2 outlets per work area (~10 m2)"],
}


def device_rules(page: dict) -> dict:
    """The placement rules as data for bim.prototype's device proposal.

    Where a rule gives a band, the height used is a point inside it, and the
    basis says so; the band itself travels with the device.
    """
    src = lambda c: page[c]["source"]  # noqa: E731
    return {
        "smoke": {"rule": "SPT-FA-01, SPT-FA-03, SPT-FA-02", "source": src("SPT-FA-01"),
                  "spacing_m": 9.1, "max_wall_distance_m": 4.55, "radius_m": 6.37},
        "call_point": {"rule": "SPT-FA-11, SPT-FA-12", "source": src("SPT-FA-11"),
                       "max_from_exit_m": 1.5, "height_m": 1.15, "band": "1.07-1.22 m AFF"},
        "strobe": {"rule": "SPT-FA-15, SPT-FA-16, SPT-FA-17", "source": src("SPT-FA-15"),
                   "height_m": 2.2, "band": "2.03-2.44 m AFF", "max_room_side_m": 20.7,
                   "corridor_end_m": 4.6, "corridor_spacing_m": 30.5},
        "access": {"rule": "SPT-AC-06", "source": src("SPT-AC-06"), "height_m": 1.1,
                   "band": "<= 1.22 m AFF", "exit_rule": "SPT-AC-02",
                   "contact_rule": "SPT-AC-08 (practice, not code)", "head_m": 2.1},
        "data_outlets": {"rule": "SPT-SC-10 (code - verify)", "source": src("SPT-SC-10"),
                         "area_per_group_m2": 10, "outlets_per_group": 2, "height_m": 0.3,
                         "height_basis": "not in the rules library; a common outlet height, assumed"},
    }

_VALUE = re.compile(r"'(?:[^']|'')*'|null|true|false|-?\d+(?:\.\d+)?")


def rows() -> dict[str, dict]:
    sql = MIGRATION.read_text(encoding="utf-8")
    out: dict[str, dict] = {}
    for code in EXPECT:
        m = re.search(r"\n\('[a-z_]+', '" + re.escape(code) + r"', ", sql)
        if not m:
            raise SystemExit(f"{code} is not in {MIGRATION.name}")
        # A row ends at the first ')' that closes it: '),' or ')' then newline.
        body, depth, i, in_str = [], 0, m.start() + 1, False
        while i < len(sql):
            ch = sql[i]
            if in_str:
                if ch == "'" and sql[i + 1:i + 2] == "'":
                    body.append("''")
                    i += 2
                    continue
                if ch == "'":
                    in_str = False
            elif ch == "'":
                in_str = True
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    body.append(ch)
                    break
            body.append(ch)
            i += 1
        values = _VALUE.findall("".join(body)[1:-1])
        if len(values) != len(COLUMNS):
            raise SystemExit(f"{code}: expected {len(COLUMNS)} values, found {len(values)}")
        row = {}
        for col, raw in zip(COLUMNS, values):
            if raw.startswith("'"):
                text = raw[1:-1].replace("''", "'")
                row[col] = json.loads(text) if col in ("conditions", "inputs", "calculation",
                                                       "outputs", "exceptions") else text
            else:
                row[col] = None if raw == "null" else raw
        out[code] = row
    return out


def main() -> int:
    library = rows()
    page: dict[str, dict] = {}
    for code, row in library.items():
        calc = row["calculation"] or {}
        stated = f"{calc.get('value_limit', '')} || {calc.get('calculation', '')}"
        for needle in EXPECT[code]:
            if needle not in stated:
                print(f"{code} no longer states {needle!r}. The simulator applies that "
                      f"value; update simulator/sim/20-analysis.js and EXPECT together.\n"
                      f"  library text: {stated}", file=sys.stderr)
                return 1
        page[code] = {
            "code": code,
            "name": row["rule_name"],
            "source": row["standard_reference"],
            "overlay": row["jurisdiction_overlay"],
            "condition": (row["conditions"] or {}).get("condition_text"),
            "value_limit": calc.get("value_limit"),
            "calculation": calc.get("calculation"),
            "confidence": row["confidence"],
            "verification_note": row["verification_note"],
        }
    if "--device-rules" in sys.argv:
        json.dump(device_rules(page), sys.stdout, ensure_ascii=False, indent=1)
    else:
        json.dump(page, sys.stdout, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
