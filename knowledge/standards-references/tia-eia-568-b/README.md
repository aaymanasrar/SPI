# ANSI/TIA/EIA-568-B — source record

| Field | Value |
|---|---|
| Document supplied | *ANSI/TIA/EIA 568-B Commercial Building Telecommunications Cabling Standard* |
| Publisher of this copy | Quang Dung Technology (QD-Tek), compiled from Cablingdb.com |
| Pages | 62 |
| Received | 24 September 2026 |
| Parts covered | 568-B.1 (general), 568-B.2 (twisted pair), 568-B.3 (optical fibre), addenda B.1-1…B.1-4, B.2-1…B.2-5, B.3-1 |
| Rules affected | A-01…A-04, A-09…A-12 re-verified; A-02 and A-11 corrected; A-13…A-21 added |
| Encoded by migration | `supabase/migrations/0016_tia568b_verification_and_ksa_cctv.sql` |

---

## 1. Read this before citing anything below

This document is **not the standard**. Three things limit it, and all three are carried into
`engineering_rules.verification_note` rather than being quietly dropped:

1. **It is a condensed secondary summary.** Its own disclaimer says so: *"The purpose of this
   document is to provide an easy to understand, condensed version of the original document…
   This document is not meant to replace the original standards developed by the various
   standards bodies and we urge you to purchase the original documents through
   www.tiaonline.com."* Most limits are stated; most equations, annexes and test methods are
   referred to but not reproduced.
2. **It is a superseded edition.** 568-B dates from the early 2000s. The current cabling standards
   are **ANSI/TIA-568.2-D** (balanced twisted pair) and **ANSI/TIA-568.3-D** (optical fibre).
   Figures that survive unchanged into the current edition are common, but that has not been
   checked — it cannot be, without a licensed copy.
3. **It contains at least one internal inconsistency.** Page 4 says the system *"must be bonded and
   grounded as per ANSI/TIA/EIA 606"*; pages 5, 8 and 9 and addendum B.1-2 all say **607**.
   606 is administration and labelling, 607 is bonding and grounding, so page 4 is a transcription
   error in the summary. Rule A-09 follows 607, and A-10 follows 606.

**Net effect on the rule set.** This document moves eight Part A rules from *"believed correct,
standard not opened"* to *"confirmed against a condensed summary of the superseded edition"*. That
is a real improvement in provenance and it is **not** the same as verified. Every rule touched here
keeps `source_verified = false`, with a note naming what is still outstanding: confirmation against
the current 568.2-D / 568.3-D.

---

## 2. What it confirms, and what it changes

### Confirmed — figures the ELV guide carried from general knowledge

| Rule | Was flagged as | This document says | Page |
|---|---|---|---|
| A-01 | *"The 10 m cord allowance comes from general knowledge"* | *"The maximum allowable length of patch cords and equipment cords is 10 meters."* Permanent link 90 m, channel 100 m. | 9, 10 |
| A-02 | 4× confirmed only by a reseller reference | Bend radius table: 4-pair UTP **4 × diameter**, 4-pair ScTP **8 ×**, backbone **10 ×** | 8 |
| A-03 | Sourced to a marketing page | *"pairs should not be untwisted more that ½""* for Cat 5e and higher — ½ in = 12.7 mm, the 13 mm figure | 9 |
| A-09 | *"The TIA-607 reference is from general knowledge"* | *"Grounding and bonding practices as per ANSI/TIA/EIA 607"*; addendum B.1-2 names **J-STD-607-A** | 5, 8, 32 |
| A-10 | *"The TIA-606 reference is from general knowledge"* | Administration per **ANSI/TIA/EIA-606**; MUTOA work area cables *"labelled at both ends"* | 6, 7, 23 |
| A-12 | Polarity and loss recalled, not read | Polarity A/B scheme stated; horizontal link attenuation **< 2.0 dB** | 9, 11 |

### Confirmed by absence — the SPEC tags were right

**A-04 (4 to 5 ft support interval)** does not appear anywhere in this document. The only placement
requirement is qualitative: *"Cable should be placed in such a manner as to minimize stress… If
cable ties are used, they should be cinched loosely to prevent deforming the cable sheath"* (p.8).
This positively confirms that the support interval is contractor/BICSI practice and **not** a TIA
number — the SPEC tag stands, and A-04 still cannot become scope on its own.

**A-08 (40 percent conduit fill)** likewise does not appear. Still unconfirmed, still SPEC.
**A-05, A-06, A-07** are NEC and building-code matters and are outside this document entirely.

### Corrected — two rules were wrong

| Rule | The ELV guide said | This document says | Page |
|---|---|---|---|
| **A-02** | *"Fibre: 10 × diameter installed, 20 × under pulling tension"* | 20 × applies to **interbuilding** backbone only. **Intrabuilding** backbone under load is **15 ×**. Horizontal 2/4-fibre is an absolute **25 mm** no load / **50 mm** under load, not a multiplier at all. | 9, 28 |
| **A-11** | Full field-test set includes **DC resistance** | The primary field test list is wiremap, length, insertion loss, NEXT, PSNEXT, ELFEXT, PSELFEXT, return loss, propagation delay, delay skew. **DC resistance is a cable component spec (≤ 9.38 Ω/100 m), not a field test.** ACR-F and PSACR-F are the later names for ELFEXT and PSELFEXT. | 10, 12, 17 |

Both corrections were applied to version 1 of each rule in place. That is permitted precisely
because both versions are still `draft` — migration 0010 freezes a rule version only once it
reaches approved, active or superseded, and nothing here has been approved.

### Added — nine new Part A rules

A-13 topology and transition points · A-14 two outlets per work area · A-15 backbone distances and
hierarchy · A-16 pulling tension · A-17 consolidation point · A-18 MUTOA · A-19 propagation delay
and delay skew · A-20 fibre link attenuation · A-21 ScTP screen bonding.

**A-14 and A-15 are the commercially significant ones.** A-14 sets a *minimum two outlets per work
area*, which drives outlet, faceplate, jack and horizontal cable counts directly. A-15 caps
backbone lengths. Both are CODE, so both can bind without a SOW clause — which is exactly why
their unverified status matters, and why they are seeded as drafts.

---

## 3. Key figures, as stated in this document

**Lengths.** Horizontal permanent link 90 m · channel 100 m · patch and equipment cords 10 m
combined · work area cord 5 m · MUTOA work area cord 22 m max · consolidation point ≥ 15 m from
the telecommunications room · MC and IC jumpers ≤ 20 m · equipment jumpers ≤ 30 m.

**Backbone (inclusive of cable, patch cords, jumpers and equipment cable).**

| Media | MC→HC | MC→IC | IC→HC |
|---|---|---|---|
| Copper (voice) | 800 m | 500 m | 300 m |
| Multimode fibre | 2000 m | 1700 m | 300 m |
| Singlemode fibre | 3000 m | 2700 m | 300 m |

**Bend radius.** UTP 4× OD · ScTP 8× OD · copper backbone 10× OD · patch cords (addendum B.1-1)
6 mm UTP / 50 mm ScTP no load · fibre 2/4 intrabuilding 25 mm no load, 50 mm under load ·
intrabuilding backbone 10×/15× · interbuilding backbone 10×/20×.

**Pulling tension.** 4-pair UTP **110 N (25 lbf)** · inside-plant 2/4 fibre **222 N (50 lbf)** ·
OSP fibre min pull strength **2670 N (600 lbf)** · drop cables **1335 N (300 lbf)**.

**Delay.** Propagation delay ≤ 555 ns channel, ≤ 498 ns permanent link, at 10 MHz · delay skew
≤ 50 ns channel, ≤ 44 ns permanent link · cable delay skew ≤ 45 ns/100 m.

**Fibre loss.** Horizontal link < 2.0 dB; < 2.75 dB where an open-office consolidation point is
present; 2.0 dB with a MUTOA. Link attenuation = cable + connector insertion + splice insertion.

**Bonding.** ScTP screen to the TGB in the telecommunications room; screen-to-ground potential
≤ 1.0 V rms and ≤ 1.0 V dc.

**Recognized categories.** 3, 5e and 6 only. Categories 1, 2, 4 and 5 are not recognized.
Cat 6 horizontal is limited to 90 m assuming a 5 m patch cord at each end.
