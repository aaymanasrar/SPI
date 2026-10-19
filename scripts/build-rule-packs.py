#!/usr/bin/env python3
"""Build LLM-ready rule packs from the encoded rules.

  ./scripts/build-rule-packs.py "postgres://..."      or set DATABASE_URL

Writes knowledge/rule-packs/<system>.md, one per system, plus an index.
These are GENERATED. Edit the rules or the source files, then re-run.

Why they exist: the database is the auditable record, with UUIDs, approval
lifecycle, provenance columns and a conflict registry. None of that helps a
model apply a rule. These packs strip it to what you need at the moment of
answering, and mark the two things a model cannot safely work out for itself:
which rules are contradicted, and which cannot become a quantity on their own.
"""
import json, os, subprocess, sys, collections

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "knowledge", "rule-packs")

QUERY = r"""
select json_agg(x order by sys_order, rank, rule_code) from (
  select
    coalesce(s.name, 'Cross-discipline')            as system,
    coalesce(s.code, 'cross')                       as system_code,
    case coalesce(s.code,'zzz')
      when 'fire_alarm' then 1 when 'cctv' then 2 when 'acs' then 3
      when 'structured_cabling' then 4 when 'network' then 5
      when 'ups' then 6 when 'outdoor_infrastructure' then 7 else 8 end as sys_order,
    case er.confidence when 'code' then 1 when 'local' then 2 else 3 end as rank,
    er.rule_code, er.source_rule_id, er.name,
    er.confidence::text                              as confidence,
    er.calculator_module,
    er.standard_reference, er.jurisdiction, er.jurisdiction_overlay,
    er.source_verified, er.verification_note,
    rv.calculation, rv.conditions, rv.exceptions,
    (select json_agg(json_build_object(
              'other', o.rule_code, 'kind', rr.kind::text, 'note', rr.note))
       from rule_relationships rr
       join engineering_rules o
         on o.id = case when rr.from_rule_id = er.id
                        then rr.to_rule_id else rr.from_rule_id end
      where (rr.from_rule_id = er.id or rr.to_rule_id = er.id)
        and rr.kind in ('conflicts','supersedes')
        and rr.resolved_at is null)               as blockers
  from engineering_rules er
  join rule_versions rv on rv.rule_id = er.id and rv.version = 1
  left join systems s on s.id = er.system_id
) x;
"""


def psql(url, sql):
    out = subprocess.run(["psql", url, "-tA", "-c", sql],
                         capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit("psql failed:\n" + out.stderr)
    return out.stdout.strip()


# Units that appear as a trailing key segment, so max_spacing_m -> "max spacing: 9.1 m"
UNITS = {"m": "m", "mm": "mm", "ft": "ft", "in": "in", "km": "km", "db": "dB",
         "ns": "ns", "s": "s", "v": "V", "w": "W", "n": "N", "c": "\u00b0C",
         "hz": "Hz", "percent": "%", "days": "days", "hours": "h", "ah": "Ah",
         "cd": "cd", "deg": "\u00b0", "multiplier": "\u00d7"}

NOISE = {"kind", "evaluator", "value_limit", "calculation", "plain_english",
         "plain_english_provenance", "plain_english_example_invented",
         "library_basis", "status", "portable", "retention_source",
         "resolution_source"}


def humanise(key, v):
    """Turn max_spacing_m = 9.1 into ('max spacing', '9.1 m')."""
    parts = key.split("_")
    unit = ""
    if len(parts) > 1 and parts[-1] in UNITS and not isinstance(v, (dict, list)):
        unit = UNITS[parts[-1]]
        parts = parts[:-1]
        if parts and parts[-1] in ("per", "por"):
            parts = parts[:-1]
    label = " ".join(parts).replace("-", " ")
    if isinstance(v, (dict, list)):
        text = json.dumps(v, separators=(", ", ": "))
    elif isinstance(v, bool):
        text = "yes" if v else "no"
    else:
        text = str(v)
        if unit == "\u00d7":
            return label, text + "\u00d7"
    return label, (text + " " + unit).strip()


def readable_limits(calc, cap=8):
    """Numbers first, then flags, then structures. Keeps the important bit up front."""
    items = [(k, v) for k, v in calc.items() if k not in NOISE]

    def order(kv):
        k, v = kv
        numeric = isinstance(v, (int, float)) and not isinstance(v, bool)
        keyed = any(t in k for t in ("max", "min", "limit", "required"))
        if numeric and keyed:
            return 0
        if numeric:
            return 1
        if isinstance(v, str):
            return 2
        return 3

    items.sort(key=order)
    shown = items[:cap]
    parts = []
    for k, v in shown:
        label, text = humanise(k, v)
        parts.append(f"{label} {text}" if text else label)
    rest = len(items) - len(shown)
    body = "; ".join(parts)
    if rest > 0:
        body += f"; (+{rest} more, see the source file)"
    return body


def val(calc, *keys):
    for k in keys:
        if calc.get(k):
            return calc[k]
    return None


def fmt(r):
    calc = r["calculation"] or {}
    cond = r["conditions"] or {}
    exc = (r["exceptions"] or {}).get("notes") or []
    out = [f"### {r['source_rule_id']} — {r['name']}"]

    # The two things a model cannot work out for itself.
    if r["blockers"]:
        for b in r["blockers"]:
            out.append(f"**DO NOT USE — {b['kind']} with {b['other']}.** {b['note']}")
        out.append("")
    if r["confidence"] == "code":
        scope = "binds on its own"
    elif r["confidence"] == "local":
        j = r["jurisdiction"] or "a single jurisdiction"
        scope = (f"applies only in {j}; cite the instrument before it becomes a "
                 f"quantity")
    else:
        scope = "NOT scope on its own — needs a drawing or SOW clause to be priced"

    limit = val(calc, "value_limit")
    if limit:
        out.append(f"- **Limit:** {limit}")
    else:
        body = readable_limits(calc)
        if body:
            out.append("- **Limit:** " + body)

    when = cond.get("condition_text") or ""
    if not when and cond.get("applies_when"):
        when = "; ".join(
            f"{c.get('fact')} {c.get('op')} {json.dumps(c.get('value'))}"
            for c in cond["applies_when"])
    if when:
        out.append(f"- **When:** {when}")
    if calc.get("calculation"):
        out.append(f"- **Calculation:** {calc['calculation']}")
    if r.get("calculator_module"):
        out.append(f"- **Calculator:** `calc_engine.{r['calculator_module']}()` \u2014 do not do "
                   "this arithmetic yourself; call the module and quote its CalcResult.")
    if calc.get("plain_english"):
        tag = " *(example invented, not from the workbook)*" \
            if calc.get("plain_english_example_invented") else ""
        out.append(f"- **In plain English:** {calc['plain_english']}{tag}")
    if exc:
        out.append("- **Does not apply / exception:** " + "; ".join(str(e) for e in exc))

    src = r["standard_reference"] or "—"
    line = f"- **Basis:** {r['confidence'].upper()} · {src}"
    if r["jurisdiction_overlay"]:
        line += f" · KSA/client: {r['jurisdiction_overlay']}"
    out.append(line)
    out.append(f"- **Scope:** {scope}")
    if not r["source_verified"]:
        out.append("- **Unverified:** the cited source was not read, or is a "
                   "superseded edition. Do not quote to a client without checking.")
    out.append("")
    return "\n".join(out)



LOC_QUERY = r"""
select json_agg(x order by facility_context, applies_at_location, rule_code) from (
  select er.rule_code, er.source_rule_id, er.applies_at_location, er.facility_context,
         er.confidence::text as confidence, er.standard_reference, er.source_verified,
         er.calculator_module,
         rv.calculation, rv.conditions,
         (select json_agg(json_build_object('other', o.rule_code,
                   'kind', rr.kind::text, 'note', rr.note))
            from rule_relationships rr
            join engineering_rules o
              on o.id = case when rr.from_rule_id = er.id
                             then rr.to_rule_id else rr.from_rule_id end
           where (rr.from_rule_id = er.id or rr.to_rule_id = er.id)
             and rr.kind in ('conflicts','supersedes')
             and rr.resolved_at is null)  as blockers
  from engineering_rules er
  join rule_versions rv on rv.rule_id = er.id and rv.version = 1
  where er.applies_at_location is not null
) x;
"""


def build_location_pack(url):
    rows = json.loads(psql(url, LOC_QUERY) or "[]")
    if not rows:
        return
    out = [
        "# By location \u2014 what goes where (Saudi projects)", "",
        f"{len(rows)} rules, indexed by **where you are**, not by system. Use this when the",
        "question is *\"we are designing a hospital ward / a perimeter fence / a gatehouse \u2014",
        "what goes in it?\"* For a limit on a specific system, use the system packs instead.", "",
        "Everything here is a **Saudi client or authority standard** (Aramco SAES, HCIS SEC/SAF,",
        "MOH) or an SBC threshold. It applies on a Saudi project and nowhere else. Confirm the",
        "standard is called out by the project SOW before pricing from it.", "",
        "See [`README.md`](README.md) for the output format.", "", "---", "",
    ]
    by = collections.OrderedDict()
    for r in rows:
        by.setdefault(r["facility_context"], []).append(r)
    for ctx, rs in by.items():
        out.append(f"## {ctx}")
        out.append("")
        for r in rs:
            calc = r["calculation"] or {}
            out.append(f"### {r['applies_at_location']} \u2014 {(r['conditions'] or {}).get('system_text','')}")
            out.append(f"`{r['source_rule_id']}`")
            if r["blockers"]:
                for b in r["blockers"]:
                    out.append(f"**DO NOT USE \u2014 {b['kind']} with {b['other']}.** {b['note']}")
            if calc.get("what_is_used"):
                out.append(f"- **Install:** {calc['what_is_used']}")
            if calc.get("key_numbers"):
                out.append(f"- **Key numbers:** {calc['key_numbers']}")
            if r.get("calculator_module"):
                out.append(f"- **Calculator:** `calc_engine.{r['calculator_module']}()`")
            if calc.get("why"):
                out.append(f"- **Why:** {calc['why']}")
            out.append(f"- **Basis:** {r['confidence'].upper()} \u00b7 {r['standard_reference']}")
            scope = ("binds on its own" if r["confidence"] == "code"
                     else "applies only in SA; cite the standard before it becomes a quantity"
                     if r["confidence"] == "local"
                     else "NOT scope on its own \u2014 needs a drawing or SOW clause")
            out.append(f"- **Scope:** {scope}")
            if not r["source_verified"]:
                out.append("- **Unverified:** summary, keyword extract, or an old public edition. "
                           "Verify against the current controlled copy before citing.")
            out.append("")
    path = os.path.join(OUT, "by-location.md")
    open(path, "w").write("\n".join(out))
    print("wrote", path, f"({len(rows)} rules)")


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("Pass a connection string or set DATABASE_URL.")
    rows = json.loads(psql(url, QUERY) or "[]")
    if not rows:
        sys.exit("No rules found. Seed them first.")
    os.makedirs(OUT, exist_ok=True)

    by = collections.OrderedDict()
    for r in rows:
        by.setdefault((r["system"], r["system_code"]), []).append(r)

    index = [
        "# Rule packs", "",
        "Generated by `scripts/build-rule-packs.py`. **Do not edit by hand.**", "",
        f"{len(rows)} rules, ready to hand to a model. One file per system: give it the",
        "pack for the system it is working on, not all of them.", "",
        "## How to use a pack", "",
        "1. Read the rules for the system in question.",
        "2. Skip anything marked **DO NOT USE** — those are contradicted by another",
        "   rule and no one has decided which wins yet.",
        "3. Apply the rule. Use **Limit** and **Calculation** for the number; the plain",
        "   English is there to explain it, never to derive a value from.",
        "4. Check **When** and the exception line before applying it.", "",
        "## When a rule has a calculator", "",
        "Some rules carry a **Calculator:** line naming a `calc_engine` module. When it is there,",
        "**call the module \u2014 do not do the arithmetic in your head.** The engine is",
        "deterministic and returns a CalcResult with the inputs, the steps, the assumptions, the",
        "standards referenced and a pass/fail. Quote that, and paste `result.report()` into the",
        "design basis. If you are missing an input the module needs, ask for it; do not assume a",
        "value.", "",
        "## What to output", "",
        "Answer in this shape, every time:", "",
        "```",
        "Value:       <number + unit>",
        "Rule:        <rule id> — <rule name>",
        "Basis:       CODE | SPEC | LOCAL",
        "Citation:    required | not required",
        "Assumptions: <anything you had to assume>",
        "```", "",
        "- **CODE** stands on its own.",
        "- **SPEC** and **LOCAL** need a drawing or SOW clause before the number can be",
        "  priced. Say `Citation: required` and name what is needed.",
        "- If a rule is marked **Unverified**, say so in Assumptions.",
        "- **If no rule covers the question, say so. Do not invent a number.** An invented",
        "  value looks exactly like a real one by the time it reaches a customer.", "",
        "## Packs", "", "| System | Rules | File |", "|---|---|---|",
    ]
    for (system, code), rs in by.items():
        name = f"{code}.md"
        blocked = sum(1 for r in rs if r["blockers"])
        head = [
            f"# {system} — rule pack", "",
            f"{len(rs)} rules. Generated from the database; see",
            "[`../rule-packs/README.md`](README.md) for how to use these and what to output.",
            "",
        ]
        if blocked:
            head += [f"**{blocked} rule(s) in this pack are marked DO NOT USE.** They are "
                     "contradicted by another rule and the conflict is unresolved. Skip them.", ""]
        head += ["---", ""]
        open(os.path.join(OUT, name), "w").write(
            "\n".join(head) + "\n".join(fmt(r) for r in rs))
        index.append(f"| {system} | {len(rs)} | [`{name}`]({name}) |")
        print("wrote", os.path.join(OUT, name), f"({len(rs)} rules)")

    build_location_pack(url)
    index.append("")
    index.append("Plus [`by-location.md`](by-location.md) \u2014 the same knowledge indexed by "
                 "**where you are** (perimeter, gatehouse, hospital ward, mosque) rather than by "
                 "system. Use it to answer \"what goes in this room?\"")
    open(os.path.join(OUT, "README.md"), "w").write("\n".join(index) + "\n")
    print("wrote", os.path.join(OUT, "README.md"))


if __name__ == "__main__":
    main()
