"""Read a specification into requirement statements, each citing its clause.

Reads PDF (text layer), DOCX and plain text. The document is split into clauses
by their numbering ("2.3.1", "A.", "(b)"); in each clause the reader looks for
what can be checked against a drawing or a BOQ:

* **quantity** — "provide 12 IP cameras", "two card readers";
* **rate** — "2 data outlets per workstation", "one detector per 10 m²";
* **coverage** — "smoke detectors in all rooms", "every office shall have…";
* **attribute** — addressable, 4 MP, Cat6A, IP66, a brand, a standard;
* **height** — "1.4 m AFF" next to a device.

This is pattern reading, not understanding. Every requirement carries the full
clause text and its page or paragraph, so a person can see exactly what was read
and from where; a clause the patterns miss is simply not a requirement here, and
the output says how many clauses were read so the gap is visible. Nothing is
inferred that the clause does not state.
"""
from __future__ import annotations

import io
import re
import time
from pathlib import PurePosixPath

from pydantic import BaseModel, Field

from ..core import ENGINE_VERSION, Finding, InvalidInput, MissingItem, Storage, ToolResult, register
from . import vocab

WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
         "eight": 8, "nine": 9, "ten": 10, "twelve": 12, "a single": 1, "single": 1}
NUM = r"(\d{1,4}|" + "|".join(sorted(WORDS, key=len, reverse=True)) + r")"

#: Room words in a spec -> the room types bim.prototype gives a room.
ROOM_WORDS: list[tuple[str, str]] = [
    (r"open[- ]?(?:plan )?offices?", "open_office"), (r"offices?", "office"),
    (r"meeting rooms?|conference rooms?|boardrooms?", "meeting"),
    (r"corridors?|passages?|hallways?", "corridor"), (r"toilets?|washrooms?|restrooms?|wcs?", "toilet"),
    (r"stair(?:case|well)?s?", "stair"), (r"lift lobb(?:y|ies)|lobb(?:y|ies)|receptions?|foyers?", "reception"),
    (r"store ?rooms?|stores|storage rooms?", "store"), (r"kitchens?|pantr(?:y|ies)", "kitchen"),
    (r"server rooms?|comms rooms?|it rooms?|idf rooms?|mdf rooms?", "server"),
    (r"plant rooms?|electrical rooms?|mechanical rooms?", "plant"),
    (r"classrooms?", "classroom"), (r"bedrooms?", "bedroom"), (r"prayer rooms?", "prayer"),
]
ALL_ROOMS = r"(?:all|every|each)\s+(?:the\s+)?(?:rooms?|areas?|spaces?|occupied (?:rooms?|areas?|spaces?)|floors?)"
REQUIRE = re.compile(r"\b(shall|must|is required|are required|to be provided|provide[sd]?|required)\b", re.I)
CLAUSE_START = re.compile(
    r"^\s*((?:\d{1,3}\.){1,5}\d{0,3}\.?|\d{1,3}\)|[A-Z]\.|\([a-z]\)|[a-z]\)|PART\s+\d+|SECTION\s+\d+)\s+")


class ReadSpecInput(BaseModel):
    document_id: str
    storage_key: str
    filename: str | None = Field(None, description="used to tell PDF, DOCX and text apart")
    max_pages: int = Field(200, ge=1, le=1000)


def _lines(raw: bytes, name: str, max_pages: int) -> tuple[list[tuple[str, str]], list[int], int]:
    """(location, line) pairs, pages without a text layer, and pages read."""
    suffix = PurePosixPath(name).suffix.lower()
    out: list[tuple[str, str]] = []
    no_text: list[int] = []
    if raw[:4] == b"%PDF" or suffix == ".pdf":
        import pdfplumber
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            pages = pdf.pages[:max_pages]
            for i, page in enumerate(pages, 1):
                text = page.extract_text() or ""
                if not text.strip():
                    no_text.append(i)
                out += [(f"p.{i}", ln) for ln in text.splitlines()]
            return out, no_text, len(pages)
    if raw[:2] == b"PK" or suffix == ".docx":
        import docx
        d = docx.Document(io.BytesIO(raw))
        for i, p in enumerate(d.paragraphs, 1):
            if p.text.strip():
                out.append((f"¶{i}", p.text))
        for ti, t in enumerate(d.tables, 1):
            for ri, row in enumerate(t.rows, 1):
                cells = list(dict.fromkeys(c.text.strip() for c in row.cells if c.text.strip()))
                if cells:
                    out.append((f"table {ti} row {ri}", " — ".join(cells)))
        return out, [], 1
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    return [("line", ln) for ln in text.splitlines()], [], 1


def _clauses(lines: list[tuple[str, str]]) -> list[dict]:
    clauses: list[dict] = []
    cur: dict | None = None
    for loc, ln in lines:
        if not ln.strip():
            continue
        m = CLAUSE_START.match(ln)
        if m or cur is None or loc.startswith(("¶", "table")):
            cur = {"ref": m.group(1).rstrip(".") if m else None, "location": loc,
                   "text": ln.strip()}
            clauses.append(cur)
        else:
            cur["text"] += " " + ln.strip()
    for c in clauses:
        c["text"] = re.sub(r"\s+", " ", c["text"]).strip()
    return clauses


def _num(s: str) -> int:
    s = s.lower().strip()
    return WORDS[s] if s in WORDS else int(s)


def _room_types(text: str) -> list[str]:
    found = []
    for pat, t in ROOM_WORDS:
        if re.search(r"\b(?:" + pat + r")\b", text, re.I):
            found.append(t)
    return list(dict.fromkeys(found))


def requirements_of(clause: dict) -> list[dict]:
    """Requirements stated in one clause. Only clauses that require something
    ('shall', 'provide', …) are read; a description is not a requirement."""
    text = clause["text"]
    if not REQUIRE.search(text):
        return []
    # The clause number is not part of what it says: "2.3 Provide …" is not 3 of anything.
    body = CLAUSE_START.sub("", text, count=1)
    low = body.lower()
    found = vocab.devices_in(body)
    systems = vocab.systems_in(body)
    base = {"clause": clause["ref"], "location": clause["location"], "text": text}
    out: list[dict] = []

    for (system, device), s, e in found:
        before = low[max(0, s - 40):s]
        after = low[e:e + 80]
        # rate: "<n> <device> per <thing>" / "one <device> per 10 m²"
        rate = re.search(r"^\s*(?:shall be provided\s+)?(?:at\s+)?per\s+(?:each\s+)?"
                         r"(\d+(?:\.\d+)?\s?(?:m2|m²|sq\.?\s?m)|workstation|desk|room|office|door|exit|floor|bed)",
                         after)
        # The count is the number closest before the device, with at most three
        # plain words between ("4 IP dome cameras"); never a number inside another.
        qty = re.search(r"(?<![\d.])" + NUM + r"(?![\d.])\s*(?:no\.?\s*|nos\.?\s*|number of\s*)?"
                        r"(?:\(\d+\)\s*)?(?:(?!" + NUM + r"\b)[a-z/-]+\s){0,3}$", before)
        if qty:
            n = _num(qty.group(1))
            if rate:
                per = rate.group(1).replace("sq m", "m²").replace("sq. m", "m²").replace("m2", "m²").replace(" ", "")
                out.append({**base, "kind": "rate", "system": system, "device_type": device,
                            "value": n, "per": per})
            elif not re.search(r"\b(?:minimum|at least|min\.)\s*$", before[: qty.start()] or ""):
                out.append({**base, "kind": "quantity", "system": system, "device_type": device,
                            "value": n})
            else:
                out.append({**base, "kind": "quantity_min", "system": system, "device_type": device,
                            "value": n})
        # coverage: "in all rooms", "every office", "each meeting room"
        window = low[max(0, s - 120):e + 120]
        if re.search(ALL_ROOMS, window):
            out.append({**base, "kind": "coverage", "system": system, "device_type": device,
                        "rooms": ["all"]})
        else:
            m = re.search(r"\b(?:all|every|each|in(?:\s+the)?)\s+((?:[a-z-]+\s){0,2}[a-z-]+)", window)
            rooms = _room_types(window) if m else []
            if rooms and re.search(r"\b(all|every|each)\b", window):
                out.append({**base, "kind": "coverage", "system": system, "device_type": device,
                            "rooms": rooms})
        # height next to the device
        h = re.search(r"(\d(?:\.\d{1,2})?)\s?m\s*(?:aff|a\.f\.f\.?|above (?:the )?(?:finished )?floor)",
                      low[max(0, s - 60):e + 100])
        if h:
            out.append({**base, "kind": "height", "system": system, "device_type": device,
                        "value": float(h.group(1)), "unit": "m AFF"})

    # attributes belong to the clause's device, else its system
    attrs = vocab.attributes_in(body)
    if attrs:
        devices = list(dict.fromkeys(k for k, _, _ in found))
        targets: list[tuple[str | None, str | None]] = devices or [(s, None) for s in systems] or [(None, None)]
        equal = bool(vocab.APPROVED_EQUAL.search(body))
        for name, values in attrs.items():
            for system, device in targets:
                out.append({**base, "kind": "attribute", "system": system, "device_type": device,
                            "attribute": name, "values": values,
                            **({"approved_equal": equal} if name == "brand" else {})})
    # a system the clause requires, even with no device named
    for system in systems:
        out.append({**base, "kind": "system", "system": system, "device_type": None})
    return out


def read_spec_bytes(raw: bytes, name: str, max_pages: int = 200) -> dict:
    lines, no_text, pages = _lines(raw, name, max_pages)
    clauses = _clauses(lines)
    reqs: list[dict] = []
    for c in clauses:
        reqs += requirements_of(c)
    return {"pages_read": pages, "pages_without_text_layer": no_text,
            "clause_count": len(clauses),
            "requiring_clauses": sum(1 for c in clauses if REQUIRE.search(c["text"])),
            "requirements": reqs}


@register("review.read_spec", "review", ReadSpecInput,
          "Read a specification (PDF, DOCX or text) into requirement statements — quantities, "
          "per-area rates, room coverage, attributes, heights — each citing its clause",
          modes=("preview",))
def read_spec(data: ReadSpecInput, storage: Storage | None = None) -> ToolResult:
    started = time.perf_counter()
    res = ToolResult(tool="review.read_spec", engine_version=ENGINE_VERSION)
    if storage is None:
        raise InvalidInput("review.read_spec needs storage to fetch the document")
    out = read_spec_bytes(storage.read(data.storage_key), data.filename or data.storage_key,
                          data.max_pages)
    res.outputs = out
    if out["pages_without_text_layer"] and len(out["pages_without_text_layer"]) == out["pages_read"]:
        res.status = "missing_data"
        res.missing = [MissingItem(field="text_layer", record=f"document:{data.document_id}",
                                   note="No page has a text layer: this is a scan. Run OCR, or "
                                        "supply the specification as DOCX or a text PDF.")]
    elif out["pages_without_text_layer"]:
        res.findings.append(Finding(
            code="SPEC-PAGES-WITHOUT-TEXT", severity="review", subject=f"document:{data.document_id}",
            detail=f"Pages {out['pages_without_text_layer']} have no text layer and were not read.",
            action="OCR those pages or supply them as text, then read again."))
    if not out["requirements"] and res.status == "ok":
        res.findings.append(Finding(
            code="SPEC-NOTHING-READ", severity="review", subject=f"document:{data.document_id}",
            detail=f"{out['clause_count']} clauses read, none stating an ELV requirement the "
                   "reader recognises.",
            action="Check the document is the ELV specification; clauses it misses are not checked."))
    res.duration_ms = int((time.perf_counter() - started) * 1000)
    return res
