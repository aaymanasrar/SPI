# ELV & Telecom Installation Rule Guide Book — source record

| Field | Value |
|---|---|
| Document | ELV & Telecom Installation Rule Guide Book |
| Author | @aayman (SmartPage) |
| Document date | 21 September 2026 |
| Pages | 13 |
| Received | 24 September 2026 |
| Rules carried | 42 (A-01…A-12, B-01…B-11, C-01…C-07, D-01…D-06, X-01…X-06) |
| Encoded by migration | `supabase/migrations/0015_seed_elv_installation_rules.sql` |

This is the first Appendix A material supplied to the platform. It is a SmartPage-authored
document, which is why it may live here at all: `knowledge/README.md` forbids rules invented or
inferred by an agent, and permits rules that originate from SmartPage engineering or a named
authority document.

---

## 1. The confidence tag is load-bearing

The guide tags every rule by how far it can be relied on. The tag is not commentary — Section 6,
rule X-06 makes it a control:

> Every rule used in a BOQ, TBE or method statement must carry its tag and cite the drawing or
> SOW clause that makes it a scope item. SPEC and LOCAL rules are not scope by themselves.

| Tag | Meaning | Platform effect |
|---|---|---|
| `CODE` | Stated in a published standard (TIA-568, NEC, NFPA 72, BS 5839) | May bind on its own; cite the clause from the edition the AHJ adopted |
| `SPEC` | Project-specification or client practice, not a universal code rule | Applies only where the SOW, drawing or client standard calls it out |
| `LOCAL` | One jurisdiction, court case or regulator | Never carried to another jurisdiction without checking the local authority |

Encoded as `engineering_rules.confidence` (`code` / `spec` / `local`) in migration 0014, and
enforced at BOQ validation by `forbid_unsupported_scope()`: a quantity produced by a `spec` or
`local` rule cannot pass into a validated or approved BOQ unless that BOQ item carries a
`boq_item_sources` row of type `sow_clause`, `drawing` or `client_standard`.

Of the 42 rules: **24 CODE, 13 SPEC, 5 LOCAL.** About four in ten need a project document or a
local authority behind them before they bind anyone.

---

## 2. What the guide says about its own evidence

Section 7 of the guide is a critical review of its own sources, and it is unusually blunt. The
short version, carried through to `engineering_rules.source_verified` and `verification_note`:

- The linked case studies are mostly marketing pages and one Nigerian court case. Most of the
  specific numbers come from the standards themselves, **not** from the pages cited.
- The Cables NYC page does **not** state the 90 m limit, the 4× bend radius, or the firestop rule
  that the source text attributed to it. Those rules are kept, re-sourced to TIA-568 and the
  building codes.
- The Scope Fire case studies confirm the projects exist (BS 5839-1 takeover, an L1 new build,
  aspirating detection in a factory) but state **none** of the Part B numbers.
- The Eureka PatSnap article and the NFPA case-studies page yielded nothing usable.
- The TIA reference in the source list is the superseded TIA/EIA-568-B PDF, not 568.2-D.

**One of these findings has since been overtaken.** A copy of 568-B was supplied on 24 Sep 2026 and
read. It confirms the 90 m link, the 10 m cord allowance, the 4× UTP bend radius, the 13 mm untwist
limit (for Cat 5e and higher only), and the TIA-606/607 references — and it **corrects** two rules
this guide got wrong. It also confirms, by containing no such figure, that A-04's support interval
and A-08's 40 percent fill are not TIA numbers. It remains a condensed summary of a superseded
edition, so it raises provenance without reaching `source_verified`. Details in the
[568-B source record](../tia-eia-568-b/README.md).

The guide's own "where this guide can still be wrong" list, reproduced because it decides which
rules are safe to quote at a client:

> Figures for B-07, the 40 percent conduit fill in A-08, the 10 m cord allowance in A-01 and the
> standard and chapter references (TIA-569, TIA-606, TSB-184-A, IEC 62676-4, NFPA 90A, NFPA 101,
> NFPA 72 chapters) come from general knowledge, not from a document I opened, and I have not seen
> the current editions of TIA-568.2-D, NFPA 72 or BS 5839-1.

**Consequence for the encoding.** Every seeded rule version is `draft`. None is `approved` or
`active`, so none can execute. `source_verified` is `true` only where the cited source was opened
and confirms the rule's content; everywhere else it is `false` and `verification_note` names what
must be confirmed against a licensed copy of the current edition first.

---

## 3. Source register

Eleven of the twelve supplied links were tried on 21 September 2026.

| Source | Status | Used for |
|---|---|---|
| Cables NYC: TIA compliance guide | Opened | A-03, A-04, A-05, A-11 |
| Eureka PatSnap: TIA-568 compliance | Opened, general overview only | Nothing |
| Scope Fire and Security case studies | Opened | B-06, B-11, Part C context |
| Voltiq office network cabling | Opened, no standards cited | A-10, X-02 |
| Tailwind Voice and Data | Opened | A-08, A-10, X-01 |
| Harlem Solicitors: Isiaka Bello v Helios Towers | Opened | D-02, D-03, D-04, D-06 |
| Mediterranean Publications: mast spatial analysis | Opened; covers Mubi, Nigeria | D-01 |
| Judy Legal: Helios Tower v Bello | Judgment behind login | Context only |
| NFPA case studies | Opened, no case-study content | Nothing |
| Taylor and Francis: mast siting compliance | Not readable (HTTP 403) | Nothing |
| TIA/EIA 568-B PDF | **Superseded by events — a copy was supplied and opened on 24 Sep 2026.** See the [568-B source record](../tia-eia-568-b/README.md). | A-01…A-04, A-08…A-12 re-verified; A-02 and A-11 corrected; A-13…A-21 added |
| Scribd: TIA-568-C | Not readable (script challenge) | Nothing |

Sources the guide added itself: Elliott Electric (bend radius, A-02); EngineersUniverse (fire alarm
spacing, B-01 to B-03); SIA on OSDP (C-05); Industrial Monitor Direct on NEC 800 separation (A-07,
secondary — cite NEC directly); Initial Safety on SBC 801 and the CST EMF complaints page (Saudi
lens).

Two cautions the guide records: the Taylor & Francis abstract is unchecked, and the Judy Legal
record shows only that the trial court first found for the claimant — the Court of Appeal outcome
comes from the Harlem Solicitors article, not from the court record.

---

## 4. Saudi / GCC lens — confirm per project, never assume

1. **Which code editions the SOW names.** Aramco and client SOWs usually name NFPA and their own
   standards directly. The SBC 801 summary consulted praises NFPA alignment and cites NFPA 13, 101
   and 220, but does **not** confirm NFPA 72 by name. Check the current SBC 801 text.
2. **TIA-568 or ISO/IEC 11801 for cabling.** Some limits differ — bend-radius figures among them.
3. **Civil Defense approval** requirements for fire alarm, voice alarm and door release.
4. **CST Regulation on Exposure to EMF** and municipal siting rules, if any tower or rooftop RF
   work is in scope. Part D is probably outside a typical ICT and ELV bid.

NSI Gold (UK installer inspectorate approval) and UL 294 (US access-control listing) are **not**
installation rules. Both are LOCAL: evidence that a vendor or installer is approved in that
country, not a requirement on a Saudi or GCC site unless the SOW names them.

---

## 5. Where the rules live

| Part | Scope | File | System |
|---|---|---|---|
| A | Structured cabling (ANSI/TIA-568, NEC Art. 800) | [`structured-cabling/rules/elv-guide-part-a.md`](../../structured-cabling/rules/elv-guide-part-a.md) | `structured_cabling` |
| B | Fire detection and life safety (NFPA 72, BS 5839) | [`fire-alarm/rules/elv-guide-part-b.md`](../../fire-alarm/rules/elv-guide-part-b.md) | `fire_alarm` |
| C | Security, CCTV and access control | [`cctv/rules/elv-guide-part-c.md`](../../cctv/rules/elv-guide-part-c.md) | `cctv`, `acs` |
| D | Outdoor infrastructure and mast siting | [`outdoor-infrastructure/rules/elv-guide-part-d.md`](../../outdoor-infrastructure/rules/elv-guide-part-d.md) | `outdoor_infrastructure` |
| X | Cross-discipline and handover pack | [`elv-guide-part-x-cross-discipline.md`](./elv-guide-part-x-cross-discipline.md) | none (applies to all) |

Each part file carries the rule text, the tag, the basis note and the inspection checklist that can
be lifted into an ITP.
