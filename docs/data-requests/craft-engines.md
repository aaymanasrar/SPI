# Data requests — craft engines

Tracks what the craft engines need from SmartPage and do not have. Until an item
arrives, the tests use fixtures named `PLACEHOLDER_*` and the corresponding tool
returns `missing_data` rather than inventing a substitute.

| # | Item | Blocks | Status |
|---|---|---|---|
| 1 | SmartPage **compliance sheet** .docx template | `word.compliance_sheet` | Not supplied |
| 2 | SmartPage **submittal cover** .docx template | `word.fill_template` | Not supplied |
| 3 | SmartPage **transmittal** .docx template | `word.fill_template` | Not supplied |
| 4 | **Symbol / block mapping** per client drawing standard | `cad.count_symbols` | Not supplied |
| 5 | A representative client **BOQ workbook** | `grid.read_client_boq` header synonyms | Not supplied |
| 6 | A representative **DXF floor plan** | every `cad.*` tool | Not supplied |

## Notes on each

**1–3 Templates.** Place in `knowledge/templates/`. WordCraft substitutes
placeholders of the form `{{ field }}` using `python-docx`; it does not need a
templating language. What it does need is the real document, because a compliance
sheet's column order and the consultant's expected wording are SmartPage's
convention, not something to invent.

**4 Symbol mapping.** Stored as data (JSON or a table), never as code — a mapping
hard-coded in `symbols.py` would be an invented engineering rule. Shape:
`{ block_name | layer_pattern → device_type, system }`. One mapping per client
drawing standard, because a block called `FD` means a smoke detector on one job
and a fire damper on another.

**5 Client BOQ.** `grid/reader.py` recognises header synonyms from a list that is
currently a reasonable guess (`qty`, `qnty`, `uom`, `mlfb`, …). One real client
workbook would replace guesswork with evidence. The reader fails loudly when no
header is recognised rather than mapping columns by position.

**6 DXF.** Needed for golden-file tests with real geometry. The current fixtures
will be synthesised with `ezdxf` and are explicitly not representative of how a
consultant draws.

## Related, outside this document

Two gaps in already-encoded data block calculations the engines will want:

- **15 fire devices have no `alarm_current_ma`** (Siemens capture, 0020–0021), so
  rule FA-18 cannot be computed from the catalogue. `engine_readiness` lists them.
- **`SEC-07` / `SAES-O-207` were never retrieved**, so security UPS autonomy is an
  open assumption in rule `SPT-LP-19`.
