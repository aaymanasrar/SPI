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

**Empty.** No engineering rules, products, prices, standards, approvals or vendor information have
been supplied yet.

Phases 0–2 of the build (foundation, project workspace, schema, and the catalogue and rules
*frameworks*) proceed without this material. Everything from the design modules onward produces an
empty shell until it arrives — so collecting it is the real critical path, and it moves slower
than the software does.
