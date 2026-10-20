# 0001 — Craft engines as a separate Python process

Status: accepted · Date: 2026-10-20 · Supersedes: nothing

## Context

The platform can reason about rules and compute numbers, but it cannot read or
write the files engineers work in. A BOQ exists only as `boq_items` rows; a floor
plan is an opaque blob behind `documents.storage_key`.

The libraries that read those formats — `openpyxl`, `python-docx`, `ezdxf`,
`pdfplumber` — are Python, mature, and have no credible JavaScript equivalent for
DXF in particular. The app is Next.js/TypeScript.

## Decision

**Headless engines in a separate Python process, called over HTTP from server
code only.** Four engines (grid, word, cad, pdf) behind one FastAPI service in
`engines/`, with `TOOL_REGISTRY` as the only surface the AI orchestrator sees.

Three consequences we accept deliberately:

1. **A second runtime to deploy.** The alternative — reimplementing DXF parsing
   in TypeScript — is strictly worse. `ezdxf` is a decade of edge cases.
2. **A network hop.** Mitigated by making the HTTP call *outside* the database
   transaction: `transaction()` holds one of ten pooled connections, and a CAD
   parse takes seconds.
3. **The service trusts its caller.** It has no session and no RBAC. It must
   never be reachable from the browser, which is why `CRAFT_SERVICE_URL` is not a
   `NEXT_PUBLIC_` variable, and why permission checks live in the server action.

### CAD output goes to `drawing_objects`, not `extraction_proposals`

`extraction_proposals.extraction_run_id` is NOT NULL, and `extraction_runs`
requires `provider`, `model` and `prompt_version` — all NOT NULL, all describing
an LLM inference. A deterministic `ezdxf` parse is not an inference, and filling
those three columns with `'craft'` would be a lie told in a provenance table.

`drawing_objects` already carries `source source_type` and `review_status`. A
deterministic parse writes `source='imported'`, `review_status='pending'`, and
promotion to `rooms` / `design_devices` uses the existing `building_model.review`
flow. `extraction_proposals` stays reserved for genuinely inferred values.

### Licence policy

Allowed: MIT, BSD, Apache-2.0, ISC, PSF, MPL-2.0 (MPL only as a separate process,
i.e. LibreOffice). Forbidden: AGPL, GPL shipped to the browser, HyperFormula,
ODA SDK.

**LGPL is on neither list, so `scripts/check-licenses` treats it as forbidden.**
That rules out `docxtpl` (LGPL-2.1), the obvious choice for .docx templating.
WordCraft will do placeholder substitution with `python-docx` (MIT) instead —
more work, but it keeps a licence nobody approved out of the tree. Reversible:
if LGPL-as-separate-library is acceptable, add it to the allowed set and switch.

**An unreadable licence is not a cleared licence.** The gate fails on `UNKNOWN`.
This was not theoretical: testing the gate with PyMuPDF left `pymupdf4llm` and
`pymupdf_layout` behind after uninstall, both reporting `UNKNOWN`, and the first
version of the gate passed them.

### Excel formulas without a formula engine

GridCraft computes every value in Python **and** writes the Excel formula into
the cell. Excel recalculates for the human; the Python value is the one carrying
provenance. We never evaluate a spreadsheet formula ourselves — that is why
HyperFormula is forbidden rather than merely unused. The test suite asserts both
the value and the formula string, so they cannot silently diverge.

## Alternatives rejected

| Option | Why not |
|---|---|
| TypeScript libraries throughout (`exceljs`, `docx`) | No credible DXF reader. Splitting CAD into Python anyway would mean two runtimes *and* two codebases. |
| Python as a subprocess per call | Interpreter start-up per call, no warm caches, and harder to reason about concurrency than one service. |
| Put the engines inside `calc_engine/` | `calc_engine` makes a promise — no network, no I/O, pure maths — that file writers cannot keep. Keeping them separate preserves it. |
