# SmartPage Engineering Knowledge

This directory holds **SmartPage's own engineering knowledge and source material** for the
SmartPage Intelligence platform. It is the human-authored input that the platform's engineering
rules, product catalogue and pricing are derived from.

It corresponds to Appendix A of the Master Build Specification, which is deliberately a *data
request* rather than a list of values.

---

## The governing rule

> **Nothing in this directory may be invented.**

No engineering rule, product, price, standard, approval, vendor or specification may be written
here by an AI agent, or inferred, or copied from a plausible-looking external source. Every file
here must originate from SmartPage engineering, a manufacturer, or a named authority document.

This is not a formality. A fabricated spacing rule or an invented price does not announce itself
as wrong — it flows through the rules engine, into a BOQ, into a quotation, and out to a customer
carrying the appearance of engineering authority. The platform is built so that every number can
answer *where did you come from?*; this directory is where that chain begins.

If a value is unknown, it stays unknown. That is a supported state throughout the system.

---

## What goes where

| Directory | Contents |
|---|---|
| `fire-alarm/rules/` | Design rules: detection coverage, spacing, device selection criteria, circuit limits, zoning |
| `fire-alarm/design-methodology/` | How SmartPage engineers approach a fire alarm design, step by step |
| `fire-alarm/equipment/` | Panels, detectors, sounders, interfaces — types used and the criteria for choosing between them |
| `fire-alarm/exceptions/` | Where the standard approach does not apply, and what is done instead |
| `cctv/rules/` | Camera selection, coverage, placement and field-of-view rules |
| `cctv/design-methodology/` | SmartPage's CCTV design approach |
| `cctv/equipment/` | Camera types, mounts, encoders, recorders |
| `cctv/storage/` | Retention requirements and storage calculation methodology |
| `cctv/network/` | Bandwidth, switching, PoE budgets and network design requirements |
| `access-control/rules/` | Reader, controller, lock and credential rules |
| `access-control/door-types/` | Door classifications and the hardware each type requires |
| `access-control/equipment/` | Controllers, readers, locks, exit devices, door contacts |
| `access-control/exceptions/` | Life-safety overrides, free-egress cases, and other departures |
| `structured-cabling/rules/` | Copper and fibre horizontal cabling: length, bend, pathway, fire rating, separation, bonding, certification |
| `outdoor-infrastructure/rules/` | Mast siting, generator setback, noise and RF exposure |
| `network/rules/` | PoE budgets, reach, oversubscription, segmentation, redundancy |
| `ups/rules/` | UPS sizing, battery runtime and ventilation, topology, redundancy |
| `vendors/` | Manufacturer and supplier information, authorization records, contact and commercial terms |
| `products/` | Datasheets, specifications and model information for authorized products |
| `pricing/` | Approved price lists, labour rates, installation rates, testing & commissioning rates |
| `historical-projects/` | Completed SmartPage projects with their approved BOQs and quotations — the ground-truth set |
| `standards-references/` | Applicable Saudi/GCC authority requirements and referenced standards |

---

## How this relates to the database

Source material lives here. The platform does **not** read this directory at runtime.

Knowledge is encoded into the database as structured, versioned, approved records — engineering
rules with test cases, catalogue entries with authorization status, price lists with effective
dates — and each of those records references the source document it came from. That encoding step
is a deliberate, reviewed act performed by an engineer, not an automatic import.

The sequence is:

```
source material (here)  →  reviewed encoding  →  versioned DB record  →  approval  →  usable by the platform
```

---

## Historical projects

`historical-projects/` deserves particular attention. Master Spec §24 makes ground-truth testing
mandatory before commercial release, and §24.3 sets the priority plainly:

> Do not optimize the system for impressive demos. Optimize it against approved historical
> engineering outputs.

Each historical project should include the original drawings and project documents, the approved
BOQ, the product schedule, the issued quotation, and any known engineer corrections. These are
what the platform's accuracy is measured against.

---

## Confidentiality

This material may include client project data, manufacturer agreements and commercial pricing.
Treat the contents as confidential. Consider whether large binaries and sensitive commercial
documents belong in git history at all, or whether this directory should be referenced from
controlled storage instead.

---

## Current status

**Three documents supplied, 57 rules encoded.** The *ELV & Telecom Installation Rule Guide Book*
(SmartPage, 21 Sep 2026) arrived on 24 Sep 2026 with 42 rules; a condensed copy of
**ANSI/TIA/EIA-568-B** and the Saudi **Law of the Use of Security Surveillance Cameras** followed
the same day, adding 15 more and re-verifying nine:

| Part | Scope | Rules | File |
|---|---|---|---|
| A | Structured cabling (ANSI/TIA-568, NEC Art. 800) | 21 | `structured-cabling/rules/elv-guide-part-a.md` |
| B | Fire detection and life safety (NFPA 72, BS 5839) | 11 | `fire-alarm/rules/elv-guide-part-b.md` |
| C | Security, CCTV and access control | 7 | `cctv/rules/elv-guide-part-c.md`, `access-control/rules/elv-guide-part-c.md` |
| D | Outdoor infrastructure and mast siting | 6 | `outdoor-infrastructure/rules/elv-guide-part-d.md` |
| X | Cross-discipline and handover pack | 6 | `standards-references/elv-telecom-installation-rule-guide/` |
| KSA | Saudi security surveillance camera law (CCTV) | 6 | `cctv/rules/ksa-security-camera-law.md` |

Each document has a source record, and **all three should be read before any figure from these
rules is quoted at a client**:

- [ELV & Telecom Installation Rule Guide Book](standards-references/elv-telecom-installation-rule-guide/README.md)
  — confidence tags, source register, and the guide's own critical review of its evidence.
- [ANSI/TIA/EIA-568-B](standards-references/tia-eia-568-b/README.md) — what it confirms, what it
  **corrects**, and why a condensed summary of a superseded edition still does not count as verified.
- [Saudi security surveillance camera law](standards-references/saudi-security-camera-law/README.md)
  — statutory, with per-camera fines, and the one technical figure that is still unconfirmed.

That distinction is carried into the database as `engineering_rules.source_verified` and
`verification_note`: **18 of the 57 rules are confirmed against a source that was actually opened,
and 39 are not.** The 568-B document moved nine Part A rules from *"from general knowledge"* to
*"confirmed against a condensed summary of the superseded edition"* — a real gain in provenance,
and deliberately still not `source_verified`.

The encoding is `supabase/migrations/0015_seed_elv_installation_rules.sql` and
`0016_tia568b_verification_and_ksa_cctv.sql`. Every one of the 57 rule versions is **draft**. None can execute, both because approval is an Engineering Manager act under spec 11.2
and because the rule expression language does not exist yet (ARCHITECTURE.md §9.4) — these are the
first real rules, and they are what that language now has to be designed against.

**The two figures to chase first**, because both set quantities rather than pass/fail checks:

1. **Ministerial Decision 22688/1444** and the MOI technical specification — the CCTV **retention
   period** (reported as 90 days) sizes NVR and storage, and therefore a large part of a Saudi CCTV
   BOQ. It is currently secondary-sourced only.
2. **ANSI/TIA-568.2-D** — rule A-14 (minimum two outlets per work area) is CODE and emits a
   *quantity*, so it can drive outlet, faceplate, jack and cable counts without a SOW clause.

**Still not supplied:** products, prices, vendors, authorizations, labour and installation rates,
BOQ and quotation templates, and historical ground-truth projects. Everything from the design
modules onward still produces an empty shell until those arrive.
