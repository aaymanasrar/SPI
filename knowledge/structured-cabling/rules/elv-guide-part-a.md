# Part A — Structured cabling (ANSI/TIA-568, NEC Article 800)

**Source:** ELV & Telecom Installation Rule Guide Book, 21 Sep 2026, Part A.
See [the source record](../../standards-references/elv-telecom-installation-rule-guide/README.md)
for provenance, confidence tags and what is still unverified.

**System:** `structured_cabling` · **Rule codes:** `ELV-A-01` … `ELV-A-12`

**Second source, added 24 Sep 2026:** a condensed copy of **ANSI/TIA/EIA-568-B** —
[source record](../../standards-references/tia-eia-568-b/README.md). It confirms A-01, A-02, A-03,
A-09, A-10 and A-12, **corrects** A-02 and A-11, confirms by absence that A-04 and A-08 are not TIA
numbers, and adds A-13…A-21. It is a condensed secondary summary of a **superseded** edition, so
nothing below is verified against the current ANSI/TIA-568.2-D / 568.3-D.

Twenty-one rules covering length, bend, pathway, fire rating, firestop, power separation, bonding
and certification for copper and fibre horizontal and backbone cabling.

| ID | Rule | Tag | Basis and note |
|---|---|---|---|
| A-01 | Horizontal permanent link max **90 m**; channel max **100 m** (90 m plus up to 10 m of patch and equipment cords combined). Work area cord max 5 m. | CODE | **Confirmed in 568-B** p.9-10: permanent link 90 m, channel 100 m, and the *maximum allowable length of patch cords and equipment cords is 10 meters*. The 10 m allowance is no longer an unsourced figure. Measure pulled length including service loops. Confirm against the current 568.2-D. |
| A-02 | Minimum bend radius: **4-pair UTP 4 ×** outside diameter, **4-pair ScTP 8 ×**, **copper backbone 10 ×**. Fibre: horizontal 2/4-fibre **25 mm** no load and **50 mm** under load; intrabuilding backbone **10 ×** no load / **15 ×** under load; interbuilding backbone **10 ×** / **20 ×**. Patch cords 6 mm UTP, 50 mm ScTP, no load. Follow the cable datasheet where stricter, as is common for Cat 6A and shielded cable. | CODE | **Confirmed and corrected by 568-B** p.8, 9, 28, 31. The guide's *fibre 20 × under pulling tension* was wrong as a general figure: **20 × is interbuilding only; intrabuilding backbone under load is 15 ×**, and horizontal 2/4-fibre is an absolute mm figure, not a multiplier. ScTP 8 × and the copper backbone 10 × are new. |
| A-03 | Pair untwist at termination must not exceed **13 mm** for **Category 5e and higher**. For Category 3, twists must be maintained to within **76 mm (3 in)** of the termination. | CODE | **Confirmed in 568-B** p.9: pairs *should not be untwisted more that half an inch* (12.7 mm) for Cat 5e and higher; Cat 3 within 3 in. The category scope and the Cat 3 figure are new — the 13 mm limit does not apply to Cat 3. Excess untwist raises crosstalk and can stop 10GBASE-T from passing. |
| A-04 | Support cable at regular intervals — the guide gives **every 4 to 5 ft**. No resting on ceiling tiles, grid wire, pipes or ductwork. Cable ties cinched loosely so the sheath is not deformed. | SPEC | **SPEC tag confirmed by absence.** 568-B contains no support interval at all; its only placement requirement is qualitative (p.8, minimize stress, cable ties cinched loosely). The 4 to 5 ft figure is contractor and BICSI practice and cannot become scope on its own. |
| A-05 | Match the cable listing to the space: **CMP** (plenum) in air-handling spaces, **CMR** (riser) in vertical shafts, **CM** (general purpose) only in non-plenum, non-riser horizontal runs. A higher-rated cable can replace a lower one, never the reverse. | CODE | NEC Article 800 as summarised by Cables NYC. Cite the clause from the edition the AHJ has adopted. |
| A-06 | Any penetration of a fire-rated wall or floor must be sealed with a **listed firestop system matching the assembly rating**. Intumescent sleeves are one product route, not the rule itself. | CODE | Building code and NEC. The Cables NYC guide does not state firestop requirements; this rule comes from the building and fire codes. |
| A-07 | Do not share a raceway, compartment or box with power or Class 1 conductors unless a permanent barrier separates them. Keep parallel runs apart and cross at **90 degrees**. | CODE | NEC Article 800 (800.52 in older editions). Separation distances come from TIA-569 and BICSI and vary with circuit size and shielding — take the figure from the project spec, not from a blog. |
| A-08 | Use conduit only where the spec, AHJ or a protection need calls for it; otherwise tray, J-hooks or other listed supports are acceptable. Keep conduit fill within the spec (**40 percent** is the common limit for three or more cables). | SPEC | Tailwind Voice & Data confirms conduit is a choice unless local code or spec requires it. The 40 percent figure remains **unconfirmed** — it does not appear in 568-B either. Take the fill limit from the project spec. |
| A-09 | Bond and ground telecom rooms, racks and shielded cabling to the building telecommunications bonding backbone. | CODE | **Confirmed in 568-B** p.5, 8, 9 (grounding and bonding *as per ANSI/TIA/EIA 607*) and addendum B.1-2 p.32 (**J-STD-607-A**). Note p.4 of that document says 606 — a transcription error in the summary; 606 is administration, 607 is bonding. See also A-21. |
| A-10 | Label both ends of every link and record them in an administration schedule. | SPEC | **TIA-606 reference confirmed in 568-B** p.6, 7, 23. The document requires MUTOA work area cables to carry a unique identifier and be *labelled at both ends*, and administers consolidation points and cross-connect circuits per 606. Kept SPEC because the guide's blanket every-link rule is broader than what 568-B states. |
| A-11 | Certify **100 percent** of copper permanent links with a Level-appropriate field certifier and keep the native result files. The 568-B field-test set is **wiremap, length, insertion loss, NEXT, PSNEXT, ELFEXT, PSELFEXT, return loss, propagation delay and delay skew**. | CODE | **Corrected by 568-B** p.10. The guide included **DC resistance** in the field-test set; it is not there — DC resistance is a cable component spec (9.38 ohms/100 m max, p.12/17). ACR-F and PSACR-F are the later names for ELFEXT and PSELFEXT, so the guide's list was the same set under newer names plus one error. Use the tester's current limit set for the installed category. |
| A-12 | Test **100 percent** of fibre links for insertion loss and polarity, and inspect end faces before mating. | CODE | **Loss and polarity confirmed in 568-B** p.9, 11: the A/B polarity scheme is stated and link attenuation is called the most important field test. Limits are in A-20. **End-face inspection is not stated in 568-B** and remains from general knowledge. |

## Rules added from ANSI/TIA/EIA-568-B (A-13 … A-21)

All nine are stated in the supplied 568-B document, and all carry the same caveat: a condensed
secondary summary of a superseded edition, unverified against the current 568.2-D / 568.3-D.

| ID | Rule | Tag | Basis and note |
|---|---|---|---|
| A-13 | Horizontal cabling is a **star topology** to the horizontal cross-connect. At most **one** transition or consolidation point between the horizontal cross-connect and the outlet. **No bridged taps or splices** in the copper horizontal. Baluns and impedance matching devices stay external to the outlet. | CODE | 568-B p.3. Each floor should have its own telecommunications closet, sized per TIA-569. |
| A-14 | Provide a **minimum of two telecommunications outlets per work area**: one 4-pair 100 ohm Category 3 or higher (Cat 5e or 6 recommended), the other either 4-pair Cat 5e/6 or two multimode fibres (62.5/125 or 50/125). | CODE | 568-B p.4 and addendum B.1-4 p.34. **Drives outlet, faceplate, jack and horizontal cable counts directly** — the most BOQ-significant rule added here. |
| A-15 | Backbone is a **hierarchical star**, at most **two** levels of cross-connect, and no more than one cross-connect passed through between the horizontal and main cross-connects. Maximum distances, inclusive of cable, patch cords, jumpers and equipment cable: copper voice **800 / 500 / 300 m**, multimode **2000 / 1700 / 300 m**, singlemode **3000 / 2700 / 300 m** for MC to HC / MC to IC / IC to HC. MC and IC jumpers max **20 m**; equipment jumpers max **30 m**. | CODE | 568-B p.4-5. Between any two horizontal cross-connects the signal passes through 3 or fewer cross-connect facilities. |
| A-16 | Respect **maximum pulling tension**: 4-pair UTP **110 N (25 lbf)**; inside-plant 2/4-fibre **222 N (50 lbf)**; OSP fibre minimum pull strength **2670 N (600 lbf)**; drop cables **1335 N (300 lbf)**. For multipair copper, use the manufacturer specification. | CODE | 568-B p.8, 28. Pairs with A-02: exceeding either tension or bend radius damages the link in ways certification may not catch until later. |
| A-17 | **Consolidation point:** at most one per horizontal run; a CP and a transition point may not share a run; **no cross-connects at a CP**; locate **at least 15 m from the telecommunications room** to limit NEXT and return loss; fully accessible, permanent location; administered per TIA-606. | CODE | 568-B p.7. Addendum B.2-1 p.45 additionally recommends at least 5 m between the CP and the outlet. |
| A-18 | **MUTOA:** at least one per furniture cluster; serves at most **12 work areas**; work area cord max **22 m**; attached to a permanent part of the building; **not** in the ceiling or in furniture unless that furniture is permanently affixed. Horizontal length is derated by C = (102 - H) / (1 + D), where D = **0.2** for 24 AWG UTP/ScTP and **0.5** for 26 AWG ScTP. Labelled at both ends per TIA-606. | CODE | 568-B p.6. The published table runs from 90 m horizontal (5 m work area cord, 10 m combined cords) to 70 m (22 m / 27 m). No 100 m reduction is required for fibre. |
| A-19 | **Propagation delay** max **555 ns** channel and **498 ns** permanent link, at 10 MHz. **Delay skew** max **50 ns** channel and **44 ns** permanent link. Cable delay skew max **45 ns/100 m**. Each mated connection contributes no more than 2.5 ns delay and 1.25 ns skew. | CODE | 568-B p.11, 48. These are the numeric limits behind two of the A-11 test parameters. |
| A-20 | **Fibre link attenuation:** horizontal link below **2.0 dB**, or below **2.75 dB** where an open-office consolidation point is present (2.0 dB with a MUTOA). Test horizontal in one direction at 850 or 1300 nm; backbone at both 850 and 1300 nm multimode, 1310 and 1550 nm singlemode. Link attenuation = cable attenuation + connector insertion loss + splice insertion loss. | CODE | 568-B p.11. Gives A-12 a number. Splice attenuation max 0.3 dB; multimode splice return loss min 20 dB, singlemode 26 dB, and 55 dB for CATV. |
| A-21 | **ScTP screens** shall be bonded to the **TGB** in the telecommunications room, and the horizontal cable screen bonded through a screen termination to the connecting hardware. Screen-to-ground potential must not exceed **1.0 V rms** and **1.0 V dc**. | CODE | 568-B addendum B.1-2 p.32 and p.9. A measurable acceptance criterion, unlike the qualitative A-09. Applies only where screened cable is installed. |

## Inspection checklist (liftable into an ITP)

- [ ] Pulled length of every run is 90 m or less, including service loops
- [ ] Cable jacket rating matches each space (CMP, CMR or CM)
- [ ] Every fire-rated penetration is sealed with a listed system and labelled
- [ ] No cable shares a raceway or box with power without a barrier
- [ ] Bend radius and pulling tension respected at every turn and tray drop
- [ ] Untwist at each termination is 13 mm or less
- [ ] Certifier limit set matches the installed category, and results are saved unedited
- [ ] Labels at both ends agree with the administration schedule
- [ ] Minimum two outlets provided per work area, to the recognized categories
- [ ] Backbone lengths and cross-connect hierarchy within the A-15 limits
- [ ] Pulling tension respected; no run exceeded 110 N (UTP) during installation
- [ ] Consolidation point at least 15 m from the telecommunications room, one per run
- [ ] Propagation delay and delay skew within limits on the certification report
- [ ] Fibre link attenuation below 2.0 dB (2.75 dB where a consolidation point is present)
- [ ] ScTP screen bonded to the TGB; screen-to-ground potential measured at or below 1.0 V
