# Structured Cabling - SPT Engineering Rules Library

**Source:** Engineering Rules Library - ELV / ICT / Fire (SPT Pre-Sales, compiled
29 Sep 2026), `Engineering_Rules_Library.xlsx`. See
[the source record](../../standards-references/spt-engineering-rules-library/README.md) for the basis legend, the precedence
order, the library's stated limitations, and how these rules relate to the 57 already
encoded from the earlier documents.

**System:** `structured_cabling` · **Rules:** 15 (Code 10, Code - verify 3, Practice 2)

> **Basis is not confidence.** `Code` and `Code - verify` are both encoded with
> `confidence = code`; the difference is that `Code - verify` needs its clause, edition
> or value checked before it reaches a submittal, which is recorded in
> `verification_note` and raised as `critical_review` rather than `error`. `Practice`
> is encoded as `confidence = spec` and cannot become scope on its own (ELV-X-06).

| ID | Requirement | Value / limit | Condition | Calculation | Source | Saudi / client overlay | Exception | Basis |
|---|---|---|---|---|---|---|---|---|
| SC-01 | Horizontal length | Permanent link <= 90 m; channel <= 100 m; cords <= 10 m total | Balanced twisted-pair | — | ANSI/TIA-568.0 / .1 | SAES-T-916 - verify; ISO/IEC 11801 | MUTOA/consolidation point rules | Code |
| SC-02 | Cable quantity estimate | Boxes of 305 m | Per floor/TR | Avg = (L_min + L_max)/2 x 1.1 + slack; runs/box = floor(305/Avg); boxes = ceil(runs/runs_per_box) | BICSI TDMM method (practice) | BOQ trace to drawings (no assumed routing) | Measured takeoff overrides estimate | Practice |
| SC-03 | Slack / service loops | 3 m in TR; 0.3 m at outlet (copper); fibre 1 m outlet, 3 m TR | Horizontal | Add to each run length | ANSI/TIA-568.0 | — | — | Code |
| SC-04 | Bend radius | UTP 4x OD; F/UTP 8x OD; fibre 10x OD unloaded, 20x under tension | Installed | R_min = k x OD | ANSI/TIA-568.0 / .3 | — | Bend-insensitive fibre per manufacturer | Code |
| SC-05 | Pulling tension | 4-pair UTP <= 110 N (25 lbf) | Installation | — | ANSI/TIA-568.0 | — | — | Code |
| SC-06 | Conduit fill | <= 40% for 3+ cables (53% one, 31% two) | Conduit | Fill = sum(pi OD^2/4) / A_conduit | TIA-569 / NEC Ch.9 Table 1 | SBC 401; SAES-T-911 conduit - verify | Short nipples <= 600 mm may reach 60% | Code - verify |
| SC-07 | Conduit runs | <= 30 m between pull points; <= 2 x 90 deg bends between pull boxes | Conduit | — | ANSI/TIA-569 | SAES-T-911 - verify | Increase size if extra bend unavoidable | Code |
| SC-08 | Tray fill | <= 50% fill; cable depth <= 150 mm | Cable tray | Fill = sum cable area / tray area | ANSI/TIA-569 | Project spec | — | Code |
| SC-09 | Telecom room | >= 1 TR per floor; extra if floor > 1,000 m2 or any run > 90 m | Buildings | N_TR >= max(1, ceil(A/1000)) | ANSI/TIA-569 | Project spec | — | Code |
| SC-10 | Work-area outlets | >= 2 outlets per work area (~10 m2) | Office space | N = ceil(A_office/10) x 2 | ANSI/TIA-568.0 / 569 | Project drawings govern BOQ | Non-office spaces per design | Code - verify |
| SC-11 | Power separation | Maintain separation per standard table (typ. >= 300 mm from unshielded power in open trays) | Parallel runs with power | — | ANSI/TIA-569 Annex / EN 50174-2 | SBC 401 | Metal barriers/shielded cable reduce distance | Code - verify |
| SC-12 | Fibre loss budget | Loss_calc <= link budget | Fibre links | Loss = L_km x alpha + n_conn x 0.75 + n_splice x 0.3 dB (alpha: MM 3.5 dB/km @850; SM 1.0 ISP / 0.5 OSP) | ANSI/TIA-568.3 | — | Test results govern acceptance | Code |
| SC-13 | Bonding & grounding | TMGB/TGB; bonding conductors >= 6 AWG (16 mm2), TBB sized by length | All TRs/racks | Size per TIA-607 length table | ANSI/TIA-607 | SBC 401; SAES-T-916 - verify | — | Code |
| SC-14 | Labelling & admin | Unique IDs for cables, panels, outlets, pathways | All installations | — | ANSI/TIA-606 | Client labelling scheme | — | Code |
| SC-15 | Cable sheath | LSZH in enclosed/occupied spaces | Indoor | — | IEC 60332-3 / 61034 / 60754 | Aramco / KSA project specs typically mandate LSZH | Outdoor/duct: gel-filled/armoured | Practice |

## Plain-English explanations of the calculations

> **Authored by the supplier, not present in the workbook.** Explanatory
> only. Stored as `calculation.plain_english` with a provenance marker, and
> never the basis of a calculation or a quoted value — the `value_limit`
> and `calculation` fields above are the source of record. The wording may be
> edited freely; the values above may not.

| ID | In plain English |
|---|---|
| SC-02 | Average cable run = (shortest + longest) / 2, plus 10%, plus slack. Then see how many whole runs fit in one 305 m box, and divide the total number of runs by that to get how many boxes to order (rounded up). |
| SC-03 | Add the slack lengths (3 m in the telecom room, 0.3 m at the outlet for copper) to every cable run. |
| SC-04 | Minimum bend radius = a multiplier x the cable's outer diameter. The multiplier is 4 for UTP, 8 for shielded, and 10 or 20 for fibre. |
| SC-06 | Conduit fill = the total cross-section area of all cables / the inside area of the conduit. Must be 40% or less for 3+ cables (53% for one cable, 31% for two). |
| SC-08 | Tray fill = total area of all cables / tray area. Must be 50% or less. |
| SC-09 | Number of telecom rooms = floor area / 1,000 m2, rounded up, with at least one per floor. |
| SC-10 | Number of outlets = office area / 10 m2 (rounded up) x 2, i.e. two outlets per work area. |
| SC-12 | Total fibre loss = (length in km x loss per km) + (number of connector pairs x 0.75 dB) + (number of splices x 0.3 dB). Compare this against what the equipment can tolerate. |
| SC-13 | Size the bonding backbone conductor from the TIA-607 table based on its length. |

## Relationship to rules already encoded

| This rule | Existing rule | Relationship | Note |
|---|---|---|---|
| SC-04 | ELV-A-02 | **conflicts** | SC-04 states fibre 20x OD under tension as a single figure. ELV-A-02 was corrected on 24 Sep 2026 against the supplied ANSI/TIA/EIA-568-B text, which gives 20x for INTERBUILDING backbone only, 15x for intrabuilding backbone under load, and an absolute 25 mm / 50 mm for horizontal 2- and 4-fibre. SC-04 also omits the copper backbone 10x figure. Do not merge: resolve against a current 568.3-D before either version is approved. |
| SC-06 | ELV-A-08 | **resolves** | ELV-A-08 carried the 40 percent conduit fill as an unconfirmed figure from general knowledge. SC-06 sources it to TIA-569 / NEC Ch.9 Table 1 and adds the one-cable (53%) and two-cable (31%) values plus the short-nipple exception. SC-06 is itself tagged Code - verify. |
| SC-11 | ELV-A-07 | **resolves** | ELV-A-07 deliberately encoded no separation distance, recording only that the figure comes from the project spec. SC-11 supplies approximately 300 mm from unshielded power in open trays, sourced to TIA-569 Annex / EN 50174-2, with the barrier and shielding exception. |
| SC-01 | ELV-A-01 | **agrees** | Same 90 m / 100 m / 10 m figures. |
| SC-05 | ELV-A-16 | **agrees** | Same 110 N (25 lbf) pulling tension for 4-pair UTP. |
| SC-10 | ELV-A-14 | **agrees** | Both require a minimum of two outlets per work area. SC-10 adds the ~10 m2 work area and the count formula, and both are tagged for verification. |
| SC-13 | ELV-A-09 | **agrees** | Both require bonding to the telecommunications bonding backbone per TIA-607. SC-13 adds conductor sizing (6 AWG / 16 mm2 minimum). |
| SC-14 | ELV-A-10 | **agrees** | Both require unique IDs and administration per TIA-606. |
| SC-03 | ELV-A-01 | **refines** | Gives the service-loop allowances (3 m TR, 0.3 m outlet copper; 3 m / 1 m fibre) that ELV-A-01 requires be counted inside the 90 m. |
| SC-12 | ELV-A-20 | **conflicts** | ELV-A-20 carries a flat 2.0 dB horizontal link limit from 568-B. SC-12 uses a calculated loss budget (length x attenuation + 0.75 dB per connector + 0.3 dB per splice). These are two different acceptance methods and can disagree on the same link; pick one per project. |
