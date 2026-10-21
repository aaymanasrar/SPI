# Data requests — craft engines

Tracks what the craft engines need from SmartPage and do not have. Until an item
arrives, the corresponding tool returns `missing_data` rather than inventing a
substitute.

**Items 1-3 are closed by decision, not by delivery.** You said there are no
templates to send and to make a clean default for everything, so
`craft/word/templates.py` now holds three real default templates — transmittal,
submittal cover, compliance statement — all built on one shared style
(`craft/word/style.py`), which `word.compliance_sheet` also uses, so every Word
output looks the same.

They carry no logo, no letterhead and no company name. That is deliberate: that
artwork is yours, and a made-up one would go out on a document sent to a client.
A test asserts no identity is invented. To override any of them later, put your
own .docx in storage with `{{placeholders}}` typed into it and point
`word.fill_template` at it — nothing else is needed.

| # | Item | Blocks | Status |
|---|---|---|---|
| 1 | SmartPage **compliance sheet** .docx template | `word.compliance_sheet` | Closed - clean default built |
| 2 | SmartPage **submittal cover** .docx template | `word.fill_template` | Closed - clean default built |
| 3 | SmartPage **transmittal** .docx template | `word.fill_template` | Closed - clean default built |
| 4 | **Symbol / block mapping** per client drawing standard | `cad.count_devices` | Not supplied |
| 5 | A representative client **BOQ workbook** | `grid.read_client_boq` header synonyms | Not supplied |
| 6 | A representative **DXF floor plan** | every `cad.*` tool | Not supplied |
| 7 | A **licence decision** on two LGPL packages | nothing | Closed - signed off by delegation |
| 8 | **LibreOffice** wherever the engines run | `word.to_pdf` | Installed locally; still needed in the deploy image |

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

## 7 A licence decision only you can make

The npm half of `scripts/check-licenses` was not running. It probed
`license-checker --version`, which prints the version and still exits 1, so the
gate read "not installed", printed `SKIP`, and reported **Licence check
passed**. The Python half was genuinely clean, which is why the green looked
believable. Both halves now fail rather than skip, and the npm half judges each
package (`scripts/npm-licence-policy.mjs`, tested by
`scripts/tests/licence-policy.test.sh`).

With it running, two packages in the existing tree are outside the allowed set.
Neither came from the craft engines:

| Package | Licence | Why it is here |
|---|---|---|
| `@img/sharp-libvips-darwin-arm64` | LGPL-3.0-or-later | `next` → `sharp`, image optimisation |
| `@img/sharp-wasm32` | Apache-2.0 AND LGPL-3.0-or-later AND MIT | unconstrained optional dep of `sharp` |

Both are libvips — the same image-processing library, once as a native binary and
once compiled to WebAssembly. Your policy forbids "GPL shipped to the browser";
these run in the Node server runtime, and Next does not bundle `sharp` into
client JS, so on my reading they do not breach it. LGPL is on neither your
allowed nor your forbidden list, which is why this is your call and not mine.

They are recorded as exceptions in `npm-licence-policy.mjs` and marked
`signedOff: false`, so the gate passes but prints them with **"not yet signed off
by the licence owner"** on every run. Three ways out:

1. **Accept** — I set `signedOff: true` and the warning stops.
2. **Add LGPL for separate-process / server-side use** to the allowed list, as
   MPL-2.0 already is. Then neither needs an exception.
3. **Remove them** — means giving up Next's image optimisation (`images.unoptimized`,
   or a different loader). `@img/sharp-wasm32` could be dropped on its own via an
   npm `overrides` entry without losing anything on macOS or Linux.

Until you say, option 1's warning stays on screen. I have not changed your policy.

## 8 LibreOffice

Installed locally on 2026-10-21 (`brew install --cask libreoffice`), version:

```
LibreOffice 26.8.0.3 bce0998afefdbc355585ca324285661a2170ba77
```

`word.to_pdf` has now actually run: the full suite is **105 passed, 0 skipped**,
and the test that performs a real conversion is among them. A cover and a
compliance statement convert in about 1.1 s each.

`find_soffice()` resolves `/opt/homebrew/bin/soffice`, and checks `SOFFICE_PATH`
first so a deploy image can point somewhere else.

**Still outstanding:** whatever image the engines are deployed into needs it too
(`apt-get install libreoffice-writer`, or set `SOFFICE_PATH`). A machine without
it gets a clear refusal naming the program, not a crash and not a silent
fallback to a renderer that would drop the template styles.
