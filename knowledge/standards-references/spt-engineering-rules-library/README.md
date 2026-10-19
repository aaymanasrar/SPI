# SPT Engineering Rules Library - source record

| Field | Value |
|---|---|
| Document | Engineering Rules Library - ELV / ICT / Fire |
| Author | SPT Pre-Sales |
| Compiled | 29 September 2026 |
| Source file | `Engineering_Rules_Library.xlsx` |
| Rules | 80 across 6 systems |
| Received | 29 September 2026 |
| Encoded by migration | `supabase/migrations/0017_spt_engineering_rules_library.sql` |

This is the fourth Appendix A document and the first that is **structured as a library**
rather than prose: every rule already carries a requirement, a value, a condition, a
calculation, a source, a Saudi overlay, an exception and a basis tag. It is also the first
to state a **precedence order** and to supply **worked calculators**.

---

## 1. Basis legend, as supplied

| Basis | Meaning | Encoded as |
|---|---|---|
| Code | requirement stated in the cited standard (confirm edition adopted by the project). | `confidence = code`, severity `error` |
| Code - verify | drawn from the cited standard but clause number/edition or value must be checked before use in a submittal. | `confidence = code`, severity `critical_review` |
| Practice | industry design practice, not a code mandate. Never present to client as a code requirement. | `confidence = spec`, severity `warning` |

**Basis is a verification state, not a confidence class.** The library's `Code` and
`Code - verify` are both genuine code requirements; the difference is whether the clause,
edition or value has been checked. This schema already separates those two ideas, so both
map to `confidence = code` and the distinction is carried in `source_verified` (false for
all 80) and `verification_note`. Collapsing `Code - verify` into `spec` would have been
wrong: it would let a real code requirement be dismissed as practice.

Tally: **Code 41**, **Code - verify 17**, **Practice 22**.

| System | Rules |
|---|---|
| Fire Alarm | 22 |
| Structured Cabling | 15 |
| CCTV | 12 |
| Access Control | 11 |
| UPS | 11 |
| Network | 9 |

---

## 2. Precedence order, as supplied

The library states an explicit precedence order, highest first:

1. Project SOW / specification / approved drawings
2. Client standards (Aramco SAES, HCIS directives)
3. Saudi Building Code (SBC 201/401/501/801) & NCA
4. International standards (NFPA, TIA, IEC, IEEE)
5. Practice

**This is the first precedence policy the platform has been given, and it matters.**
ARCHITECTURE.md §9.3 says the engine never resolves a conflict silently, and applies a
precedence policy *only where that precedence has been explicitly configured and
approved*. Until now no such policy existed, so every conflict had to halt. This list is
stored in `rule_precedence_policy` as a named, **unapproved** policy: recording it does not
activate it. An Engineering Manager approves it, or it stays inert.

Note what the order implies: a project SOW beats a client standard, which beats the Saudi
Building Code and NCA, which beats NFPA/TIA/IEC/IEEE, which beats practice. That is a
commercial-document-first order. It is defensible for scope, but it cannot override a
statutory obligation — a SOW cannot authorise a camera in a restroom (KSA-CCTV-03) or a
locked egress door (AC-01). Approving this policy should carry that carve-out.

---

## 3. Limitations, as stated by the library

- Clause numbers are referenced to NFPA 72-2022, TIA-568-E / 569-E family, SBC 2018/2024 structure; numbering shifts between editions.
- Aramco SAES and HCIS directive numbers flagged 'verify' were not checked against the current controlled copies.
- Not a substitute for a licensed designer's review or AHJ / Civil Defense approval.

All 80 rules are therefore encoded with `source_verified = false`. The library is a
compilation, not a standard: none of its clause numbers were read from a controlled copy
during this encoding.

---

## 4. How this library relates to the 57 rules already encoded

This is the important section. The library overlaps heavily with the ELV guide, TIA-568-B
and Saudi camera rules already in the database. Loading it blind would have produced
duplicate and in two cases **contradictory** rules, both live, with nothing to flag them.
Every relationship below is recorded in the `rule_relationships` table so the engine can
surface it instead of picking silently (§9.3).

### 4.1 Conflicts and supersessions (4) — resolve before approving either side

| Library rule | Existing rule | Kind | What the disagreement is |
|---|---|---|---|
| SC-04 | ELV-A-02 | **conflicts** | SC-04 states fibre 20x OD under tension as a single figure. ELV-A-02 was corrected on 24 Sep 2026 against the supplied ANSI/TIA/EIA-568-B text, which gives 20x for INTERBUILDING backbone only, 15x for intrabuilding backbone under load, and an absolute 25 mm / 50 mm for horizontal 2- and 4-fibre. SC-04 also omits the copper backbone 10x figure. Do not merge: resolve against a current 568.3-D before either version is approved. |
| FA-04 | ELV-B-02 | **supersedes** | ELV-B-02 carried a single recalled multiplier (roughly 0.7x at a 20 ft ceiling). FA-04 gives the full NFPA 72 Table 17.6.3.5.1 height-factor ladder from 0.91 down to 0.34. FA-04 is the better rule; ELV-B-02 should be superseded rather than kept alongside it. |
| CC-04 | KSA-CCTV-04 | **conflicts** | CC-04 records retention as commonly 30-90 days per HCIS or project spec, tagged Practice. KSA-CCTV-04 records 90 days as a statutory minimum under the Law of the Use of Security Surveillance Cameras. For a Saudi site the statutory floor governs and 30 days is not available. Both remain unconfirmed against their primary sources. |
| SC-12 | ELV-A-20 | **conflicts** | ELV-A-20 carries a flat 2.0 dB horizontal link limit from 568-B. SC-12 uses a calculated loss budget (length x attenuation + 0.75 dB per connector + 0.3 dB per splice). These are two different acceptance methods and can disagree on the same link; pick one per project. |

**SC-04 is the one to look at first.** It repeats exactly the error that the supplied
TIA/EIA-568-B text corrected five days ago: fibre bend radius is not a flat 20× under
tension. If both rules were approved, a designer could pull an intrabuilding backbone to
15× per ELV-A-02 and fail SC-04, or bend to 20× per SC-04 and over-specify. Neither rule
should be approved until one is retired.

### 4.2 Gaps this library closes (4)

| Library rule | Existing rule | What it supplies |
|---|---|---|
| SC-06 | ELV-A-08 | ELV-A-08 carried the 40 percent conduit fill as an unconfirmed figure from general knowledge. SC-06 sources it to TIA-569 / NEC Ch.9 Table 1 and adds the one-cable (53%) and two-cable (31%) values plus the short-nipple exception. SC-06 is itself tagged Code - verify. |
| SC-11 | ELV-A-07 | ELV-A-07 deliberately encoded no separation distance, recording only that the figure comes from the project spec. SC-11 supplies approximately 300 mm from unshielded power in open trays, sourced to TIA-569 Annex / EN 50174-2, with the barrier and shielding exception. |
| CC-01 | ELV-C-07 | ELV-C-07 named the DORI tiers but carried no numbers. CC-01 supplies 25 / 62.5 / 125 / 250 px/m and CC-02 and CC-03 give the scene-width and max-distance formulae. |
| NW-07 | ELV-C-04 | ELV-C-04 was SPEC, deferring to any client IT policy. NW-07 and CC-12 name NCA ECC-2:2024 and OTCC-1:2022, which is a national authority for Saudi sites rather than a preference. |

These are the clearest wins. ELV-A-07 and ELV-C-07 were deliberately encoded **without**
numbers because the earlier sources had none, and ELV-A-08's 40 percent was flagged as
unsourced. This library supplies all three, with citations.

### 4.3 Refinements (6) and agreements (9)

| Library rule | Existing rule | Kind | Note |
|---|---|---|---|
| FA-02 | ELV-B-01 | refines | Adds the 0.7S coverage-radius rule (6.37 m at S = 9.1 m) that governs irregular rooms, which flat spacing alone does not cover. |
| FA-06 | ELV-B-04 | refines | ELV-B-04 said only to redo spacing where beams and joists change coverage. FA-06 and FA-07 give the actual beam-depth and pocket-width tests. |
| AC-02 | ELV-B-09 | refines | ELV-B-09 required maglock release on alarm and on power loss. AC-02 adds the sensor-release arrangement: REX plus a manual push button within 1.5 m at 1.0-1.2 m AFF, PUSH TO EXIT signage, and a minimum 30 s unlock. |
| AC-03 | ELV-C-06 | refines | Adds the implementation constraint that the fire alarm to lock interface is hard-wired through the lock PSU, not a software link. |
| SC-03 | ELV-A-01 | refines | Gives the service-loop allowances (3 m TR, 0.3 m outlet copper; 3 m / 1 m fibre) that ELV-A-01 requires be counted inside the 90 m. |
| UP-11 | ELV-B-11 | refines | Adds that a FACP keeps its own batteries and a central UPS only qualifies if it meets NFPA 72 Ch.10 secondary-supply rules. |
| SC-01 | ELV-A-01 | agrees | Same 90 m / 100 m / 10 m figures. |
| SC-05 | ELV-A-16 | agrees | Same 110 N (25 lbf) pulling tension for 4-pair UTP. |
| SC-10 | ELV-A-14 | agrees | Both require a minimum of two outlets per work area. SC-10 adds the ~10 m2 work area and the count formula, and both are tagged for verification. |
| SC-13 | ELV-A-09 | agrees | Both require bonding to the telecommunications bonding backbone per TIA-607. SC-13 adds conductor sizing (6 AWG / 16 mm2 minimum). |
| SC-14 | ELV-A-10 | agrees | Both require unique IDs and administration per TIA-606. |
| CC-07 | ELV-C-02 | agrees | Both size PoE from the switch budget with a 20 percent margin. CC-07 and NW-01 add the class wattages at the PSE and the power available at the PD. |
| CC-08 | ELV-A-01 | agrees | Both cap the copper channel at 100 m. |
| NW-05 | ELV-A-01 | agrees | Same 100 m channel, with the added note that 10GBASE-T on Cat 6 is limited to about 55 m. |
| AC-07 | ELV-C-05 | agrees | Both prefer OSDP over Wiegand. AC-07 adds the cable-length limits (Wiegand ~150 m, OSDP/RS-485 ~1200 m) and cites NCA ECC. |

---

## 5. Calculators and the plain-English layer

### 5.1 Calculators — 13 exist, none received in full

The library ships **13** worked calculators with real spreadsheet formulae. The first
supplying message carried only five and was cut off partway through the fifth (`FA-19`,
NAC voltage drop); the second described all 13, plus `all_sheets_raw` and
`rules_by_system_sheet`, but was truncated before reaching them. **No calculator content
has been received in full.**

Received complete: `FA-02` (0.7S coverage), `FA-04` (heat detector height factor),
`FA-13` (audible level, public mode), `FA-18` (FACP battery). Received partially: `FA-19`.
Described but not received: the remaining eight, and both raw-sheet sections.

They are **not encoded**, deliberately. They are the most concrete input the expression
language has had — a nested-IF lookup table (FA-04), a `MAX` of two expressions
(FA-13), a multi-term arithmetic formula (FA-18) and a voltage-drop calculation (FA-19).
Designing that language against a third of the set would bake in the wrong shape. Send the
calculators sheet on its own and they can be encoded as `rule_tests` with real expected
values, which is what spec 11.1 asks for.

### 5.2 Plain-English explanations — authored, not source

Each rule with a calculation also carries a plain-English explanation. The supplier states
it plainly: **the plain-English wording is theirs, not from the workbook.** That
distinction is load-bearing here, so it is carried into the database rather than flattened
away.

Stored as `calculation.plain_english`, always beside
`calculation.plain_english_provenance`. The `value_limit` and `calculation` fields remain
the source of record. **The wording may be edited freely; the values may not.**

Received for **43** rules (FA-01 to UP-01). Not received, because the
supplying message was truncated: UP-02, UP-03, UP-05, UP-06 and UP-09.

**Two examples are invented, and are flagged in the data.** The supplier identified them
as illustrative numbers made up to show the idea, not workbook example values:

- **NW-04** — *48 x 1 Gbps ports on a 10 Gbps uplink = 4.8:1*. Received, and stored
  with `plain_english_example_invented: true`.
- **UP-03** — a 10-year battery lasting about 5 years at 35 C. **Its text was not
  received**, so nothing is stored; only this note records that it exists and is invented.

Both are sound arithmetic and fine as teaching examples. The reason for flagging them is
narrower: this library is headed for a client-facing tool, and once rendered an invented
example is indistinguishable from forty-odd workbook-derived ones. Flagging makes removal a
query rather than a re-read:
`update rule_versions ... where calculation ? 'plain_english_example_invented'`.

---

## 6. New systems

`Network` and `UPS` had no row in `systems`. Both are added by migration 0017, which is
what the comment in 0012 anticipated: `systems` is a table rather than an enum precisely
so a new system is a row, not a schema change. The platform now covers six.