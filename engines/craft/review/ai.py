"""A language model reading spec clauses, behind one small adapter.

Which model reads is configuration, not code (ARCHITECTURE.md §8.3):

    SPI_AI_PROVIDER = ollama          # 'none' (default) turns this off
    SPI_AI_URL      = http://127.0.0.1:11434
    SPI_AI_MODEL    = qwen3:8b        # on a server: e.g. qwen3.8:27b

The instructions the model works from are the skill file next to this module
(skill/spec_reader.md); its hash is recorded with every run, so a result can be
traced to the exact instructions that produced it.

Nothing the model says is taken on trust. A requirement is kept only if its
clause id exists, its quote is in that clause word for word, its names are from
the fixed lists, and any number it gives appears in its quote. Everything
dropped is returned with the reason, so a person sees what was refused.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import vocab
from .spec import REQUIRE, WORDS

SKILL_PATH = Path(__file__).parent / "skill" / "spec_reader.md"
BATCH = 10

SYSTEMS = sorted(vocab.SYSTEM_PHRASES)
DEVICES = sorted({d for (_, d) in vocab.DEVICE_PHRASES})
SYSTEM_OF = {d: s for (s, d) in vocab.DEVICE_PHRASES}
ROOMS = ["all", "office", "open_office", "meeting", "corridor", "toilet", "stair", "reception", "store",
         "kitchen", "server", "plant", "classroom", "bedroom", "prayer"]
ATTRIBUTES = sorted(vocab.ATTRIBUTE_PATTERNS)
KINDS = ["quantity", "quantity_min", "rate", "coverage", "height", "attribute", "system"]

#: The answer's shape. Passed to the model as a JSON schema, so the reply
#: parses; validated again here, because a schema says nothing about truth.
SCHEMA = {
    "type": "object",
    "properties": {"requirements": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "clause_id": {"type": "string"},
            "kind": {"type": "string", "enum": KINDS},
            "system": {"type": ["string", "null"], "enum": SYSTEMS + [None]},
            "device_type": {"type": ["string", "null"], "enum": DEVICES + [None]},
            "value": {"type": ["number", "null"]},
            "per": {"type": ["string", "null"]},
            "rooms": {"type": ["array", "null"], "items": {"type": "string", "enum": ROOMS}},
            "except_rooms": {"type": ["array", "null"], "items": {"type": "string", "enum": ROOMS}},
            "attribute": {"type": ["string", "null"], "enum": ATTRIBUTES + [None]},
            "values": {"type": ["array", "null"], "items": {"type": "string"}},
            "approved_equal": {"type": ["boolean", "null"]},
            "quote": {"type": "string"},
            "note": {"type": ["string", "null"]},
        },
        "required": ["clause_id", "kind", "quote"],
    }}},
    "required": ["requirements"],
}


def config() -> dict | None:
    provider = os.environ.get("SPI_AI_PROVIDER", "none").strip().lower()
    if provider in ("", "none"):
        return None
    return {"provider": provider,
            "url": os.environ.get("SPI_AI_URL", "http://127.0.0.1:11434").rstrip("/"),
            "model": os.environ.get("SPI_AI_MODEL", "").strip()}


def skill() -> tuple[str, str]:
    text = SKILL_PATH.read_text(encoding="utf-8")
    return text, hashlib.sha256(text.encode()).hexdigest()[:12]


def _ollama(cfg: dict, system: str, user: str, timeout: float) -> str:
    body = json.dumps({
        "model": cfg["model"], "stream": False, "think": False, "format": SCHEMA,
        "options": {"temperature": 0, "num_ctx": 16384},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }).encode()
    req = urllib.request.Request(f"{cfg['url']}/api/chat", data=body,
                                 headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())["message"]["content"]


def _call(cfg: dict, system: str, user: str, timeout: float) -> str:
    if cfg["provider"] == "ollama":
        return _ollama(cfg, system, user, timeout)
    raise RuntimeError(f"SPI_AI_PROVIDER={cfg['provider']!r} is not supported yet (supported: ollama)")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


def _number_in(value: float, text: str) -> bool:
    low = text.lower()
    as_text = f"{value:g}"
    if re.search(r"(?<![\d.])" + re.escape(as_text) + r"(?![\d])", low):
        return True
    return any(n == value and re.search(rf"\b{re.escape(w)}\b", low) for w, n in WORDS.items())


def _check(r: dict, clauses: dict) -> str | None:
    """None if the requirement may be kept, else why not."""
    c = clauses.get(r.get("clause_id"))
    if c is None:
        return "names a clause that was not sent"
    quote = r.get("quote") or ""
    if not quote.strip() or _norm(quote) not in _norm(c["text"]):
        return "its quote is not in the clause"
    dt, kind = r.get("device_type"), r.get("kind")
    if kind in ("quantity", "quantity_min", "rate", "coverage", "height") and not dt:
        return f"a {kind} with no device"
    if kind in ("quantity", "quantity_min", "rate", "height"):
        if r.get("value") is None or not _number_in(float(r["value"]), quote):
            return "its number is not in its quote"
    if kind == "rate" and not r.get("per"):
        return "a rate with no 'per'"
    if kind == "coverage" and not r.get("rooms"):
        return "a coverage with no rooms"
    if kind == "attribute" and not (r.get("attribute") and r.get("values")):
        return "an attribute with no name or value"
    if kind == "system" and not r.get("system"):
        return "a system requirement with no system"
    return None


def _shape(r: dict, c: dict, model: str) -> dict:
    """The rule reader's requirement shape, so every check reads both alike."""
    dt = r.get("device_type")
    out = {"clause": c["ref"], "location": c["location"], "text": c["text"], "kind": r["kind"],
           "system": r.get("system") or (SYSTEM_OF.get(dt) if dt else None), "device_type": dt,
           "read_by": f"ai:{model}", "quote": r["quote"]}
    if r["kind"] in ("quantity", "quantity_min", "rate"):
        v = float(r["value"])
        out["value"] = int(v) if v.is_integer() else v
    if r["kind"] == "rate":
        out["per"] = re.sub(r"\s+", "", r["per"]).replace("m2", "m²").replace("sqm", "m²")
    if r["kind"] == "height":
        out["value"], out["unit"] = float(r["value"]), "m AFF"
    if r["kind"] == "coverage":
        out["rooms"] = r["rooms"]
        if r.get("except_rooms"):
            out["except_rooms"] = r["except_rooms"]
    if r["kind"] == "attribute":
        out["attribute"] = r["attribute"]
        out["values"] = list(dict.fromkeys(r["values"]))
        if r["attribute"] == "brand":
            out["approved_equal"] = bool(r.get("approved_equal"))
    if r.get("note"):
        out["note"] = r["note"]
    return out


def read_clauses(clauses: list[dict], timeout: float = 300) -> dict:
    """Requirements the model reads from these clauses, checked. Returns
    {'requirements', 'rejected', 'run'}; 'run' is None when no model is set up."""
    cfg = config()
    if not cfg:
        return {"requirements": [], "rejected": [], "run": None}
    system, version = skill()
    wanted = [c for c in clauses if REQUIRE.search(c["text"])]
    by_id = {f"c{i}": c for i, c in enumerate(wanted, 1)}
    kept, rejected, errors = [], [], []
    started = time.perf_counter()
    ids = list(by_id)
    for i in range(0, len(ids), BATCH):
        chunk = ids[i:i + BATCH]
        user = "Clauses:\n" + json.dumps([{"id": k, "text": by_id[k]["text"]} for k in chunk],
                                         ensure_ascii=False, indent=1)
        try:
            raw = _call(cfg, system, user, timeout)
            reqs = json.loads(raw).get("requirements", [])
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, KeyError,
                RuntimeError) as e:
            errors.append(f"clauses {chunk[0]}–{chunk[-1]}: {type(e).__name__}: {e}")
            continue
        for r in reqs:
            if not isinstance(r, dict):
                continue
            why = _check(r, by_id)
            if why:
                rejected.append({"clause": r.get("clause_id"), "quote": r.get("quote"), "why": why,
                                 "kind": r.get("kind"), "device_type": r.get("device_type")})
            else:
                kept.append(_shape(r, by_id[r["clause_id"]], cfg["model"]))
    return {"requirements": kept, "rejected": rejected,
            "run": {"provider": cfg["provider"], "model": cfg["model"], "skill_version": version,
                    "clauses_sent": len(wanted), "accepted": len(kept), "rejected": len(rejected),
                    "errors": errors, "seconds": round(time.perf_counter() - started, 1)}}


def _key(r: dict) -> tuple:
    return (r["clause"], r["location"], r["kind"], r.get("system"), r.get("device_type"),
            r.get("attribute"))


def merge(pattern: list[dict], ai: list[dict]) -> list[dict]:
    """Both readers' requirements, each marked with who read it. Where both read
    the same thing, the rule reader's value stands and the model's note (an
    exception such as 'except toilets') is kept; a disagreement is kept as two
    requirements, so the checks see both."""
    out: list[dict] = []
    ai_by = {}
    for r in ai:
        ai_by.setdefault(_key(r), []).append(r)
    for p in pattern:
        twins = ai_by.pop(_key(p), [])
        same = next((a for a in twins if _same(p, a)), None)
        if same:
            out.append({**p, "read_by": "both", **{k: same[k] for k in ("except_rooms", "note") if k in same}})
            twins.remove(same)
        else:
            out.append({**p, "read_by": "rules"})
        out += twins
    for rest in ai_by.values():
        out += rest
    return out


def _same(a: dict, b: dict) -> bool:
    for k in ("value", "per", "rooms"):
        if a.get(k) != b.get(k):
            return False
    return set(a.get("values") or []) == set(b.get("values") or [])
