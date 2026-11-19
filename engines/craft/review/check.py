"""Check a drawing, specification(s) and a client BOQ against each other and
against SPI's rules, and write the result as a BOQ workbook plus a marked-up
drawing.

Give any of them:

* a **drawing** alone — the takeoff, SPI's recommended quantities by room with
  the rule behind each, and where the two differ;
* a drawing and **specs** — the same, plus every place the drawing does not do
  what a clause requires (quantity, per-area rate, rooms covered, a system);
* a **BOQ** too — its quantities against the drawing and the spec, and its
  descriptions against the spec's attributes (addressable, 4 MP, Cat6A, brand).

Every issue cites both sides: the room or block on the drawing, the clause and
page in the spec, the row in the BOQ, the rule in the library. Nothing is
resolved here — which side is right is an engineer's call — and nothing is
guessed: a requirement the reader could not check is listed as not checked.
"""
from __future__ import annotations

import io
import math
import re
import time
from collections import Counter, defaultdict

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from pydantic import BaseModel, Field

from ..cad.read_dxf import open_dxf
from ..core import (ENGINE_VERSION, Finding, InvalidInput, MissingItem, OutputFile, Storage,
                    ToolResult, register, sha256)
from ..grid.reader import ReadClientBoqInput, read_client_boq
from . import ai, vocab
from .drawing import DETECTORS, compare, review_drawing
from .spec import read_spec_bytes

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DXF_MIME = "application/dxf"
RECOMMEND_LAYER = "SPI_RECOMMEND"
WORK_ROOMS = {"office", "open_office", "meeting", "classroom", "reception", "room"}


class DocRef(BaseModel):
    document_id: str
    storage_key: str
    filename: str | None = None


class BoqRef(DocRef):
    sheet: str | None = None


class CheckInput(BaseModel):
    document_id: str = Field(description="the record this check is filed under")
    project_name: str = "Project"
    drawing: DocRef | None = Field(None, description="a DXF floor plan")
    specs: list[DocRef] = Field(default_factory=list, description="specification PDF/DOCX/TXT files")
    boq: BoqRef | None = Field(None, description="a client BOQ workbook")
    symbol_map: dict | None = None
    layers: list[str] | None = Field(None, description="count only inserts on these layers")
    device_rules: dict | None = Field(None, description="SPI rules to recommend with; omitted: no recommendation")
    storey_height_m: float | None = Field(None, gt=1.5, lt=20)
    ai_read_specs: bool = Field(False, description="also have the configured language model read the "
                                                   "specs (SPI_AI_* on the engine); its readings are checked "
                                                   "against the clause text before use")
    output_key: str | None = None
    output_name: str = Field("review.xlsx", pattern=r"^[\w.-]+\.xlsx$")
    markup_key: str | None = None
    markup_name: str = Field("recommended.dxf", pattern=r"^[\w.-]+\.dxf$")


# ---- issues -----------------------------------------------------------------

def _issue(issues: list, code: str, severity: str, title: str, detail: str, action: str,
           sources: list[dict]) -> None:
    issues.append({"code": code, "severity": severity, "title": title, "detail": detail,
                   "action": action, "sources": sources})


READ_BY = {"rules": "", "both": " · read by rules and AI"}


def _spec_src(r: dict, spec_names: dict) -> dict:
    where = f"clause {r['clause']}, {r['location']}" if r.get("clause") else r["location"]
    by = r.get("read_by", "rules")
    where += READ_BY.get(by, f" · read by AI only ({by.split(':', 1)[-1]}) — check it")
    return {"doc": "spec", "name": spec_names.get(r["spec_id"], "specification"), "ref": where,
            "text": r["text"][:400]}


def _band(text: str | None) -> tuple[float | None, float | None]:
    """'1.07-1.22 m AFF' -> (1.07, 1.22); '<= 1.22 m AFF' -> (None, 1.22)."""
    if not text:
        return None, None
    m = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)", text)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.search(r"<=?\s*(\d+(?:\.\d+)?)", text)
    return (None, float(m.group(1))) if m else (None, None)


RULE_BAND_KEY = {"manual_call_point": "call_point", "sounder_strobe": "strobe", "strobe": "strobe",
                 "card_reader": "access", "exit_button": "access"}


@register("review.check", "review", CheckInput,
          "Check a drawing, specifications and a client BOQ against each other and SPI's rules: "
          "a BOQ of drawn vs recommended quantities with where and why, and every contradiction "
          "with both sources cited")
def check(data: CheckInput, storage: Storage | None = None) -> ToolResult:
    started = time.perf_counter()
    res = ToolResult(tool="review.check", engine_version=ENGINE_VERSION)
    if storage is None:
        raise InvalidInput("review.check needs storage to fetch the documents")
    if not (data.drawing or data.specs or data.boq):
        raise InvalidInput("Give at least a drawing, a specification or a BOQ to check.")

    issues: list[dict] = []
    not_checked: list[dict] = []

    # ---- drawing --------------------------------------------------------------
    dr = None
    room_lines: list[dict] = []
    device_lines: list[dict] = []
    drawing_name = (data.drawing.filename or data.drawing.storage_key) if data.drawing else None
    if data.drawing:
        dr = review_drawing(storage, data.drawing.document_id, data.drawing.storage_key,
                            data.symbol_map, data.layers, data.device_rules, data.storey_height_m)
        if dr["units"]["metres_per_unit"] is None:
            res.missing.append(MissingItem(
                field="drawing_units", record=f"document:{data.drawing.document_id}",
                note=f"{drawing_name} has no units ($INSUNITS {dr['units']['insunits']}), so rooms "
                     "and devices cannot be located in metres. Set the units and run again."))
        res.missing += [MissingItem(**m) for m in dr["prototype_missing"]]
        res.assumptions += [a for a in _assumptions(dr["prototype_assumptions"])]
        room_lines, device_lines = compare(dr)
        for u in dr["unmapped"]:
            not_checked.append({"what": f"block {u['block']} on {u['layer']} ×{u['count']}",
                                "why": "not in the symbol map, so not counted"})
        if not data.device_rules:
            not_checked.append({"what": "SPI recommended quantities",
                                "why": "no rules supplied, so nothing was recommended"})
        _drawing_vs_rules(issues, room_lines, device_lines, drawing_name)

    # ---- specs ------------------------------------------------------------------
    reqs: list[dict] = []
    ai_runs: list[dict] = []
    spec_names: dict[str, str] = {}
    for s in data.specs:
        name = s.filename or s.storage_key
        spec_names[s.document_id] = name
        out = read_spec_bytes(storage.read(s.storage_key), name)
        if out["pages_without_text_layer"] and len(out["pages_without_text_layer"]) == out["pages_read"]:
            res.missing.append(MissingItem(field="text_layer", record=f"document:{s.document_id}",
                                           note=f"{name} has no text layer (a scan); it was not read."))
        found = [{**r, "read_by": "rules"} for r in out["requirements"]]
        if data.ai_read_specs:
            got = ai.read_clauses(out["clauses"])
            if got["run"] is None:
                not_checked.append({"what": f"{name}: AI reading",
                                    "why": "no model is configured on the engine (SPI_AI_PROVIDER)"})
            else:
                ai_runs.append({"spec": name, **got["run"]})
                found = ai.merge(out["requirements"], got["requirements"])
                for e in got["run"]["errors"]:
                    not_checked.append({"what": f"{name}: AI reading {e.split(':')[0]}",
                                        "why": "the model did not answer: " + e.split(":", 1)[1].strip()[:160]})
                for x in got["rejected"]:
                    not_checked.append({"what": f"{name}: AI reading of {x.get('clause')} "
                                                f"({x.get('kind')} {x.get('device_type') or ''}): "
                                                f"“{(x.get('quote') or '')[:80]}”",
                                        "why": f"refused — {x['why']}"})
        for r in found:
            reqs.append({**r, "spec_id": s.document_id})
        not_checked.append({"what": f"{name}: {out['clause_count']} clauses read, "
                                    f"{out['requiring_clauses']} with 'shall/provide', "
                                    f"{len(out['requirements'])} requirements recognised",
                            "why": "clauses the reader does not recognise are not checked"})
    if reqs:
        _spec_self(issues, reqs, spec_names)
        if data.device_rules:
            _spec_vs_rules(issues, reqs, spec_names, data.device_rules)
        if dr:
            _spec_vs_drawing(issues, not_checked, reqs, spec_names, dr, device_lines, drawing_name)

    # ---- client BOQ -------------------------------------------------------------
    boq_rows: list[dict] = []
    if data.boq:
        br = read_client_boq(ReadClientBoqInput(document_id=data.boq.document_id,
                                                storage_key=data.boq.storage_key,
                                                sheet=data.boq.sheet), storage)
        boq_name = data.boq.filename or data.boq.storage_key
        for row in br.outputs["rows"]:
            key = vocab.device_of(row["description"])
            boq_rows.append({**row, "system": key[0] if key else None,
                             "device_type": key[1] if key else None,
                             "attributes": vocab.attributes_in(row["description"])})
        _boq_checks(issues, not_checked, boq_rows, boq_name, dr, device_lines, drawing_name,
                    reqs, spec_names)

    # ---- the BOQ the review produces ---------------------------------------------
    spec_qty = _spec_quantities(reqs)
    boq_qty: Counter = Counter()
    for r in boq_rows:
        if r["device_type"] and r["quantity"] is not None:
            boq_qty[(r["system"], r["device_type"])] += r["quantity"]
    keys = {(l["system"], l["device_type"]) for l in device_lines} | set(spec_qty) | set(boq_qty)
    by_key = {(l["system"], l["device_type"]): l for l in device_lines}
    boq_lines = []
    for key in sorted(keys):
        l = by_key.get(key, {})
        boq_lines.append({
            "system": key[0], "device_type": key[1], "description": vocab.label(key[1]).capitalize(),
            "unit": l.get("unit", "no"),
            "drawn": l.get("drawn") if dr else None,
            "recommended": l.get("recommended"),
            "spec": spec_qty.get(key),
            "client_boq": boq_qty.get(key) if data.boq else None,
            "status": l.get("status"),
            "where_drawn": l.get("where_drawn", ""),
            "where_recommended": l.get("where_recommended", ""),
            "why": l.get("why", ""),
        })

    # ---- files ------------------------------------------------------------------
    payload = _workbook(data, boq_lines, room_lines, dr, reqs, spec_names, boq_rows, issues,
                        not_checked, drawing_name)
    key = data.output_key or f"craft/review/{data.output_name}"
    storage.write(key, payload)
    res.files.append(OutputFile(name=data.output_name, mime=XLSX_MIME, storage_key=key,
                                byte_size=len(payload), sha256=sha256(payload)))
    if dr and dr["units"]["metres_per_unit"] and dr["recommended"]:
        dxf = _markup(storage.read(data.drawing.storage_key), data.drawing.storage_key, dr)
        mkey = data.markup_key or f"craft/review/{data.markup_name}"
        storage.write(mkey, dxf)
        res.files.append(OutputFile(name=data.markup_name, mime=DXF_MIME, storage_key=mkey,
                                    byte_size=len(dxf), sha256=sha256(dxf)))

    counts = Counter(i["severity"] for i in issues)
    res.outputs = {
        "summary": {"issues": len(issues), "review": counts["review"], "info": counts["info"],
                    "rooms": len(dr["rooms"]) if dr else 0,
                    "drawn_devices": len(dr["drawn"]) if dr else 0,
                    "recommended_devices": len(dr["recommended"]) if dr else 0,
                    "spec_requirements": len(reqs), "boq_rows": len(boq_rows)},
        "boq": boq_lines,
        "rooms": room_lines,
        "issues": issues,
        "not_checked": not_checked,
        "spec_requirements": reqs,
        "client_boq": boq_rows,
        "recommended_positions": dr["recommended"] if dr else [],
        "symbol_map": dr["symbol_map"] if dr else None,
        "spec_reader": {"rules": True, "ai": ai_runs},
        "markup_layer": RECOMMEND_LAYER,
    }
    # Each contradiction is a finding too, so every screen that lists findings shows it.
    res.findings += [Finding(code=i["code"], severity=i["severity"], subject=i["title"],
                             detail=i["detail"], action=i["action"]) for i in issues]
    if res.missing:
        res.status = "missing_data"
    res.duration_ms = int((time.perf_counter() - started) * 1000)
    return res


def _assumptions(rows: list[dict]):
    from ..core import Assumption
    for a in rows:
        try:
            yield Assumption(**a)
        except Exception:  # noqa: BLE001 — a malformed proposal note is skipped, not fatal
            continue


# ---- drawing vs rules -----------------------------------------------------------

def _drawing_vs_rules(issues: list, room_lines: list, device_lines: list, drawing: str | None) -> None:
    # One issue per device type, listing the rooms: thirteen rooms short of a
    # sounder-strobe is one finding to act on, not thirteen.
    short: dict[tuple, list] = defaultdict(list)
    for l in room_lines:
        if l["recommended"] is None or l["status"] in ("matches", "more than recommended", "no rule"):
            continue
        short[(l["system"], l["device_type"])].append(l)
    for (system, dt), ls in short.items():
        missing = sum(l["recommended"] - l["drawn"] for l in ls)
        rooms = "; ".join(f"{l['room']}: {l['drawn']} of {l['recommended']}"
                          + (f" ({l['note']})" if l["note"] else "") for l in ls)
        rule = next((d["why"] for d in device_lines if d["device_type"] == dt), "")
        _issue(issues, "DRAWING-BELOW-RULE", "review",
               f"{vocab.label(dt).capitalize()}: {missing} short of SPI's rules in {len(ls)} room(s)",
               f"Drawn against recommended, by room — {rooms}.",
               "Add the devices (positions are on the marked-up drawing), or record why these rooms "
               "need fewer: ceiling type, room use, or a different code.",
               [{"doc": "drawing", "name": drawing, "ref": ", ".join(l["room"] for l in ls),
                 "text": rooms[:400]},
                {"doc": "rules", "name": "SPI rules library", "ref": dt, "text": rule[:400]}])
    for d in device_lines:
        if d["device_type"] in ("manual_call_point", "card_reader", "exit_button", "door_contact") \
                and d["recommended"] is not None and d["drawn"] < d["recommended"]:
            _issue(issues, "DRAWING-BELOW-RULE", "review",
                   f"{vocab.label(d['device_type']).capitalize()}: {d['drawn']} drawn, {d['recommended']} recommended",
                   f"The rules put {d['recommended']} at exits and controlled doors "
                   f"({d['where_recommended'] or 'see the marked-up drawing'}); the drawing has {d['drawn']}"
                   f"{' (' + d['where_drawn'] + ')' if d['where_drawn'] else ''}.",
                   "Check each exit and controlled door on the marked-up drawing.",
                   [{"doc": "drawing", "name": drawing, "ref": "whole level", "text": d["where_drawn"]},
                    {"doc": "rules", "name": "SPI rules library", "ref": d["device_type"], "text": d["why"]}])


# ---- spec ---------------------------------------------------------------------

def _spec_quantities(reqs: list[dict]) -> dict:
    out: dict = {}
    for r in reqs:
        if r["kind"] == "quantity":
            out.setdefault((r["system"], r["device_type"]), r["value"])
    return out


def _spec_self(issues: list, reqs: list, names: dict) -> None:
    """The spec against itself: one device, two different values."""
    qty: dict = defaultdict(list)
    attr: dict = defaultdict(list)
    height: dict = defaultdict(list)
    for r in reqs:
        if r["kind"] == "quantity":
            qty[(r["system"], r["device_type"])].append(r)
        elif r["kind"] == "attribute" and r["attribute"] not in ("standard",):
            attr[(r["system"], r["device_type"], r["attribute"])].append(r)
        elif r["kind"] == "height":
            height[(r["system"], r["device_type"])].append(r)
    for (system, dt), rs in qty.items():
        vals = sorted({r["value"] for r in rs})
        if len(vals) > 1:
            _issue(issues, "SPEC-CONTRADICTS-ITSELF", "review",
                   f"Spec gives {vocab.label(dt)} quantity as {' and '.join(map(str, vals))}",
                   "Two clauses state different quantities for the same device.",
                   "Ask the consultant which governs (RFI).", [_spec_src(r, names) for r in rs])
    for (system, dt, a), rs in attr.items():
        vals = sorted({v for r in rs for v in r["values"]})
        if len(vals) > 1 and not (a == "brand" and any(r.get("approved_equal") for r in rs)):
            subject = vocab.label(dt) if dt else (system or "the system").replace("_", " ")
            _issue(issues, "SPEC-CONTRADICTS-ITSELF", "review",
                   f"Spec gives {subject} {a.replace('_', ' ')} as {' and '.join(vals)}",
                   f"Clauses state different {a.replace('_', ' ')} for {subject}.",
                   "Ask the consultant which governs (RFI).", [_spec_src(r, names) for r in rs])
    for (system, dt), rs in height.items():
        vals = sorted({r["value"] for r in rs})
        if len(vals) > 1:
            _issue(issues, "SPEC-CONTRADICTS-ITSELF", "review",
                   f"Spec gives {vocab.label(dt)} height as {' and '.join(f'{v} m' for v in vals)}",
                   "Clauses state different mounting heights for the same device.",
                   "Ask the consultant which governs (RFI).", [_spec_src(r, names) for r in rs])


def _spec_vs_rules(issues: list, reqs: list, names: dict, rules: dict) -> None:
    for r in reqs:
        if r["kind"] != "height":
            continue
        rk = RULE_BAND_KEY.get(r["device_type"])
        rule = rules.get(rk) if rk else None
        if not rule:
            continue
        lo, hi = _band(rule.get("band"))
        if (lo is not None and r["value"] < lo) or (hi is not None and r["value"] > hi):
            _issue(issues, "SPEC-OUTSIDE-CODE-BAND", "review",
                   f"Spec puts {vocab.label(r['device_type'])} at {r['value']} m; the rule band is {rule['band']}",
                   f"{rule['rule']} ({rule['source']}) requires {rule['band']}; the spec says {r['value']} m.",
                   "Confirm with the consultant: a spec cannot relax the code, it can only be stricter.",
                   [_spec_src(r, names), {"doc": "rules", "name": "SPI rules library", "ref": rule["rule"],
                                          "text": f"{rule['band']} — {rule['source']}"}])


def _spec_vs_drawing(issues: list, not_checked: list, reqs: list, names: dict, dr: dict,
                     device_lines: list, drawing: str | None) -> None:
    rooms = {r["id"]: r for r in dr["rooms"]}
    drawn_total: Counter = Counter((x["system"], x["device_type"]) for x in dr["drawn"])
    in_room: dict = defaultdict(Counter)
    for x in dr["drawn"]:
        in_room[x["room_id"]][x["device_type"]] += 1
    drawn_systems = {x["system"] for x in dr["drawn"]}
    spec_systems = {r["system"] for r in reqs if r.get("system")}

    def drawn_in(room_id, dt):
        if dt == "smoke_detector":
            return sum(in_room[room_id][t] for t in DETECTORS)
        return in_room[room_id][dt]

    for r in reqs:
        key = (r["system"], r["device_type"])
        src = _spec_src(r, names)
        if r["kind"] in ("quantity", "quantity_min") and r["device_type"]:
            n = drawn_total[key]
            bad = n != r["value"] if r["kind"] == "quantity" else n < r["value"]
            if bad:
                _issue(issues, "SPEC-VS-DRAWING-QUANTITY", "review",
                       f"{vocab.label(r['device_type']).capitalize()}: spec "
                       f"{'at least ' if r['kind'] == 'quantity_min' else ''}{r['value']}, drawing {n}",
                       f"The spec states {r['value']}; {n} are drawn on {drawing}.",
                       "Resolve which is right before the BOQ is issued.",
                       [src, {"doc": "drawing", "name": drawing, "ref": "count",
                              "text": next((d["where_drawn"] for d in device_lines
                                            if (d["system"], d["device_type"]) == key), "")}])
        elif r["kind"] == "coverage" and r["device_type"]:
            scope = [x for x in rooms.values()
                     if ("all" in r["rooms"] or x["type"] in r["rooms"])
                     and x["type"] not in (r.get("except_rooms") or [])]
            if not scope:
                not_checked.append({"what": f"{src['ref']}: {vocab.label(r['device_type'])} in "
                                            f"{', '.join(r['rooms'])}",
                                    "why": "no room of that type was found on the drawing"})
                continue
            lacking = [x["name"] for x in scope if drawn_in(x["id"], r["device_type"]) == 0]
            if lacking:
                _issue(issues, "SPEC-VS-DRAWING-COVERAGE", "review",
                       f"Spec requires {vocab.label(r['device_type'])} in "
                       f"{'all rooms' if 'all' in r['rooms'] else ', '.join(r['rooms'])}; "
                       f"{len(lacking)} room(s) have none",
                       f"No {vocab.label(r['device_type'])} drawn in: {', '.join(sorted(lacking))}.",
                       "Add them, or confirm the room is excluded.",
                       [src, {"doc": "drawing", "name": drawing, "ref": ", ".join(sorted(lacking)),
                              "text": "none drawn"}])
        elif r["kind"] == "rate" and r["device_type"]:
            m = re.match(r"(\d+(?:\.\d+)?)m²$", r["per"])
            if m:
                per = float(m.group(1))
                cov = next((c for c in reqs if c["kind"] == "coverage" and c["clause"] == r["clause"]
                            and c["device_type"] == r["device_type"]), None)
                types = (None if not cov or "all" in cov["rooms"] else set(cov["rooms"]))
                short = []
                for x in rooms.values():
                    if not x["area_m2"] or (types and x["type"] not in types) or \
                            (not types and x["type"] not in WORK_ROOMS):
                        continue
                    need = math.ceil(x["area_m2"] / per) * r["value"]
                    have = drawn_in(x["id"], r["device_type"])
                    if have < need:
                        short.append(f"{x['name']} ({x['area_m2']:.1f} m²: needs {need}, has {have})")
                if short:
                    _issue(issues, "SPEC-VS-DRAWING-RATE", "review",
                           f"{vocab.label(r['device_type']).capitalize()}: below the spec's "
                           f"{r['value']} per {per:g} m² in {len(short)} room(s)",
                           "; ".join(short) + ".",
                           "Add outlets, or confirm the rate applies only to some rooms.",
                           [src, {"doc": "drawing", "name": drawing, "ref": "room areas from the plan",
                                  "text": "; ".join(short)[:400]}])
            else:
                not_checked.append({"what": f"{src['ref']}: {r['value']} {vocab.label(r['device_type'])} "
                                            f"per {r['per']}",
                                    "why": f"the drawing does not say how many {r['per']}s there are"})
    for system in sorted(spec_systems - drawn_systems):
        r = next(x for x in reqs if x.get("system") == system)
        _issue(issues, "SPEC-SYSTEM-NOT-DRAWN", "review",
               f"Spec requires {system.replace('_', ' ')}; nothing of it is drawn",
               f"The spec has requirements for {system.replace('_', ' ')} but no device of that "
               f"system was counted on {drawing}.",
               "Check the drawing set: it may be on another sheet, on a layer not counted, or missing.",
               [_spec_src(r, names), {"doc": "drawing", "name": drawing, "ref": "count", "text": "0 devices"}])
    for system in sorted(drawn_systems - spec_systems):
        _issue(issues, "DRAWING-SYSTEM-NOT-IN-SPEC", "info",
               f"{system.replace('_', ' ').capitalize()} is drawn but the spec says nothing about it",
               f"Devices of {system.replace('_', ' ')} are on {drawing}, and no specification clause read "
               "mentions that system.",
               "Check the scope: it may be by others, or the spec section was not supplied.",
               [{"doc": "drawing", "name": drawing, "ref": system, "text": "drawn"}])


# ---- client BOQ ------------------------------------------------------------------

def _boq_checks(issues: list, not_checked: list, rows: list, boq: str, dr: dict | None,
                device_lines: list, drawing: str | None, reqs: list, names: dict) -> None:
    qty: Counter = Counter()
    rows_of: dict = defaultdict(list)
    for r in rows:
        if r["device_type"] is None:
            not_checked.append({"what": f"BOQ row {r['source_row']}: {r['description'][:80]}",
                                "why": "names no device the checker knows, or several"})
            continue
        rows_of[(r["system"], r["device_type"])].append(r)
        if r["quantity"] is None:
            not_checked.append({"what": f"BOQ row {r['source_row']}: {r['description'][:80]}",
                                "why": "no quantity in the row"})
        else:
            qty[(r["system"], r["device_type"])] += r["quantity"]

    def boq_src(key):
        rs = rows_of.get(key, [])
        return {"doc": "boq", "name": boq,
                "ref": "rows " + ", ".join(str(r["source_row"]) for r in rs) if rs else "—",
                "text": " | ".join(f"{r['description'][:80]} — {r['quantity']:g} {r['unit'] or ''}"
                                   if r["quantity"] is not None else r["description"][:80] for r in rs)}

    if dr:
        drawn = Counter((x["system"], x["device_type"]) for x in dr["drawn"])
        for key in sorted(set(qty) | set(drawn)):
            if key not in rows_of:
                _issue(issues, "DRAWING-NOT-IN-BOQ", "review",
                       f"{vocab.label(key[1]).capitalize()}: {drawn[key]} drawn, not in the BOQ",
                       f"{drawn[key]} {vocab.label(key[1])}(s) are on {drawing}; no BOQ row names one.",
                       "Add a BOQ line, or confirm the device is by others.",
                       [{"doc": "drawing", "name": drawing, "ref": "count", "text": str(drawn[key])},
                        {"doc": "boq", "name": boq, "ref": "—", "text": "no row"}])
            elif key not in drawn:
                _issue(issues, "BOQ-NOT-ON-DRAWING", "review",
                       f"{vocab.label(key[1]).capitalize()}: {qty[key]:g} in the BOQ, none drawn",
                       f"The BOQ prices {qty[key]:g}; nothing of the kind is counted on {drawing}.",
                       "Check another sheet or layer, or remove the line.",
                       [boq_src(key), {"doc": "drawing", "name": drawing, "ref": "count", "text": "0"}])
            elif abs(qty[key] - drawn[key]) > 1e-9:
                _issue(issues, "BOQ-VS-DRAWING-QUANTITY", "review",
                       f"{vocab.label(key[1]).capitalize()}: BOQ {qty[key]:g}, drawing {drawn[key]}",
                       f"The BOQ quantity differs from the count on {drawing} by {qty[key] - drawn[key]:+g}.",
                       "Recount, or explain the difference (spares, other floors, by others).",
                       [boq_src(key), {"doc": "drawing", "name": drawing, "ref": "count",
                                       "text": next((d["where_drawn"] for d in device_lines
                                                     if (d["system"], d["device_type"]) == key), "")}])
    spec_q = {}
    for r in reqs:
        if r["kind"] == "quantity":
            spec_q.setdefault((r["system"], r["device_type"]), r)
    for key, r in spec_q.items():
        if key in qty and abs(qty[key] - r["value"]) > 1e-9:
            _issue(issues, "BOQ-VS-SPEC-QUANTITY", "review",
                   f"{vocab.label(key[1]).capitalize()}: BOQ {qty[key]:g}, spec {r['value']}",
                   "The BOQ quantity differs from the quantity the spec states.",
                   "Resolve which governs before pricing.", [boq_src(key), _spec_src(r, names)])

    # descriptions against the spec's attributes
    for row in rows:
        if not row["attributes"]:
            continue
        for name, values in row["attributes"].items():
            if name == "standard":
                continue
            stated = [r for r in reqs if r["kind"] == "attribute" and r["attribute"] == name and (
                (r["device_type"] and r["device_type"] == row["device_type"]) or
                (not r["device_type"] and r["system"] and r["system"] == row["system"]))]
            if not stated:
                continue
            spec_vals = {v for r in stated for v in r["values"]}
            off = [v for v in values if v not in spec_vals]
            if not off:
                continue
            equal = name == "brand" and any(r.get("approved_equal") for r in stated)
            _issue(issues, "BOQ-VS-SPEC-ATTRIBUTE", "info" if equal else "review",
                   f"BOQ row {row['source_row']}: {name.replace('_', ' ')} {', '.join(off)}; "
                   f"spec says {', '.join(sorted(spec_vals))}",
                   f"'{row['description'][:120]}' does not match the spec"
                   + (" — the spec allows an approved equal, so this needs approval, not a change."
                      if equal else "."),
                   "Submit for approval as an equal." if equal else "Change the line or raise an RFI.",
                   [{"doc": "boq", "name": boq, "ref": f"row {row['source_row']}", "text": row["description"][:200]},
                    *[_spec_src(r, names) for r in stated[:2]]])


# ---- outputs ------------------------------------------------------------------

def _workbook(data, boq_lines, room_lines, dr, reqs, names, boq_rows, issues, not_checked,
              drawing) -> bytes:
    wb = Workbook()
    bold = Font(bold=True)
    head = PatternFill("solid", fgColor="1F2A24")
    white = Font(bold=True, color="FFFFFF")
    tones = {"review": "FCE8C3", "info": "E8EEF4"}

    def sheet(title, header, rows, widths=None, tone_col=None):
        ws = wb.create_sheet(title)
        ws.append(header)
        for c in ws[1]:
            c.font, c.fill = white, head
            c.alignment = Alignment(vertical="center", wrap_text=True)
        for r in rows:
            ws.append(r)
        for i, w in enumerate(widths or [], 1):
            ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = w
        for row in ws.iter_rows(min_row=2):
            for c in row:
                c.alignment = Alignment(vertical="top", wrap_text=True)
            if tone_col is not None and row[tone_col].value in tones:
                for c in row:
                    c.fill = PatternFill("solid", fgColor=tones[row[tone_col].value])
        ws.freeze_panes = "A2"
        return ws

    ws = wb.active
    ws.title = "Summary"
    ws.append([f"{data.project_name} — drawing, specification and BOQ check"])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append(["PROPOSAL — quantities read off drawings and recommended by rule; for engineer review."])
    ws.append([])
    ws.append(["Drawing", drawing or "—"])
    ws.append(["Specifications", ", ".join(names.values()) or "—"])
    ws.append(["Client BOQ", (data.boq.filename or data.boq.storage_key) if data.boq else "—"])
    ws.append(["Issues needing review", sum(1 for i in issues if i["severity"] == "review")])
    ws.append(["Notes", sum(1 for i in issues if i["severity"] == "info")])
    ws.append(["Not checked", len(not_checked)])
    ws.append(["Engine", ENGINE_VERSION])
    for r in range(4, 11):
        ws.cell(row=r, column=1).font = bold
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 80

    sheet("BOQ", ["System", "Item", "Unit", "Drawn qty", "SPI recommended", "Spec qty", "Client BOQ qty",
                  "Status", "Where drawn", "Where SPI recommends", "Why (rule)"],
          [[l["system"].replace("_", " "), l["description"], l["unit"], l["drawn"], l["recommended"],
            l["spec"], l["client_boq"], l["status"], l["where_drawn"], l["where_recommended"], l["why"]]
           for l in boq_lines], [16, 26, 7, 10, 14, 9, 13, 20, 40, 40, 70])
    sheet("Issues", ["Severity", "Code", "Issue", "Detail", "Action", "Sources"],
          [[i["severity"], i["code"], i["title"], i["detail"], i["action"],
            "\n".join(f"{s['doc']}: {s['name']} — {s['ref']}: {s['text']}" for s in i["sources"])]
           for i in sorted(issues, key=lambda i: (i["severity"] != "review", i["code"]))],
          [9, 26, 50, 60, 40, 80], tone_col=0)
    if room_lines:
        sheet("By room", ["Room", "Type", "Area m²", "System", "Device", "Drawn", "SPI recommended",
                          "Difference", "Status", "Note"],
              [[l["room"], l["room_type"], l["area_m2"], l["system"].replace("_", " "),
                vocab.label(l["device_type"]), l["drawn"], l["recommended"], l["difference"], l["status"],
                l["note"]] for l in room_lines], [22, 12, 9, 14, 20, 8, 14, 11, 22, 40])
    if dr and dr["recommended"]:
        rooms = {r["id"]: r["name"] for r in dr["rooms"]}
        sheet("Recommended positions", ["Device", "Room", "x (m)", "y (m)", "Height (m)", "Rule", "Why"],
              [[vocab.label(x["device_type"]), rooms.get(x["room_id"], "—"), x["x_m"], x["y_m"], x["z_m"],
                x["rule"], x["basis"]] for x in dr["recommended"]], [20, 20, 9, 9, 10, 28, 80])
    if reqs:
        sheet("Spec requirements", ["Spec", "Clause", "Where", "Read by", "Kind", "System", "Device", "Value",
                                    "Clause text"],
              [[names.get(r["spec_id"]), r.get("clause"), r["location"], r.get("read_by", "rules"), r["kind"],
                (r.get("system") or "").replace("_", " "), vocab.label(r["device_type"]) if r.get("device_type") else "",
                _value(r), r["text"]] for r in reqs], [22, 8, 10, 16, 12, 14, 18, 22, 90])
    if boq_rows:
        sheet("Client BOQ", ["Row", "Description", "Unit", "Qty", "Read as", "Attributes"],
              [[r["source_row"], r["description"], r["unit"], r["quantity"],
                vocab.label(r["device_type"]) if r["device_type"] else "— not matched",
                "; ".join(f"{k}: {', '.join(v)}" for k, v in r["attributes"].items())] for r in boq_rows],
              [6, 60, 7, 8, 20, 40])
    sheet("Not checked", ["What", "Why"], [[n["what"], n["why"]] for n in not_checked], [80, 60])
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _value(r: dict) -> str:
    if r["kind"] in ("quantity", "quantity_min"):
        return f"{'≥ ' if r['kind'] == 'quantity_min' else ''}{r['value']}"
    if r["kind"] == "rate":
        return f"{r['value']} per {r['per']}"
    if r["kind"] == "coverage":
        return "in " + ", ".join(r["rooms"]) + (
            f" except {', '.join(r['except_rooms'])}" if r.get("except_rooms") else "")
    if r["kind"] == "height":
        return f"{r['value']} m AFF"
    if r["kind"] == "attribute":
        return f"{r['attribute']}: {', '.join(r['values'])}"
    return ""


ABBR = {"smoke_detector": "SD", "manual_call_point": "MCP", "sounder_strobe": "SS",
        "card_reader": "CR", "exit_button": "EB", "door_contact": "DC", "data_outlet": "DO"}


def _markup(raw: bytes, key: str, dr: dict) -> bytes:
    """A copy of the drawing with SPI's recommended positions on their own layer."""
    from ezdxf.enums import TextEntityAlignment
    doc = open_dxf(raw, key)
    msp = doc.modelspace()
    mpu = dr["units"]["metres_per_unit"]
    if RECOMMEND_LAYER not in doc.layers:
        doc.layers.add(RECOMMEND_LAYER, color=6)
    h = 0.25 / mpu  # 250 mm text and marks, in drawing units
    lt = "DASHED" if "DASHED" in doc.linetypes else "CONTINUOUS"
    for x in dr["recommended"]:
        cx, cy = x["x_m"] / mpu, x["y_m"] / mpu
        msp.add_circle((cx, cy), 0.9 * h, dxfattribs={"layer": RECOMMEND_LAYER, "color": 6, "linetype": lt})
        msp.add_line((cx - 0.6 * h, cy), (cx + 0.6 * h, cy), dxfattribs={"layer": RECOMMEND_LAYER, "color": 6})
        msp.add_line((cx, cy - 0.6 * h), (cx, cy + 0.6 * h), dxfattribs={"layer": RECOMMEND_LAYER, "color": 6})
        msp.add_text("+" + ABBR.get(x["device_type"], x["device_type"][:3].upper()),
                     dxfattribs={"layer": RECOMMEND_LAYER, "color": 6, "height": 0.6 * h}
                     ).set_placement((cx + 1.1 * h, cy - 1.2 * h), align=TextEntityAlignment.TOP_LEFT)
    ext = [(r["footprint_m"]) for r in dr["rooms"]]
    if ext:
        xs = [p[0] for poly in ext for p in poly]
        ys = [p[1] for poly in ext for p in poly]
        msp.add_text("SPI RECOMMENDED POSITIONS (magenta, +code) — proposals from the rules library, "
                     "for engineer review", dxfattribs={"layer": RECOMMEND_LAYER, "color": 6, "height": 1.2 * h}
                     ).set_placement((min(xs) / mpu, (min(ys) / mpu) - 4 * h),
                                     align=TextEntityAlignment.TOP_LEFT)
    out = io.StringIO()
    doc.write(out)
    return out.getvalue().encode("utf-8")
