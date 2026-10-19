# Structured Cabling — rule pack

38 rules. Generated from the database; see
[`../rule-packs/README.md`](README.md) for how to use these and what to output.

**4 rule(s) in this pack are marked DO NOT USE.** They are contradicted by another rule and the conflict is unresolved. Skip them.

---
### A-01 — Horizontal permanent link and channel length limit
- **Limit:** channel max 100 m; cord allowance max 10 m; permanent link max 90 m; measure pulled_length_including_service_loops
- **When:** link.media eq "copper_horizontal"
- **Does not apply / exception:** Service loops count toward the 90 m. Measure pulled length, not point-to-point distance.
- **Basis:** CODE · ANSI/TIA/EIA-568-B.1
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### A-02 — Minimum bend radius, copper and fibre
**DO NOT USE — conflicts with SPT-SC-04.** SC-04 states fibre 20x OD under tension as a single figure. ELV-A-02 was corrected on 24 Sep 2026 against the supplied ANSI/TIA/EIA-568-B text, which gives 20x for INTERBUILDING backbone only, 15x for intrabuilding backbone under load, and an absolute 25 mm / 50 mm for horizontal 2- and 4-fibre. SC-04 also omits the copper backbone 10x figure. Do not merge: resolve against a current 568.3-D before either version is approved.

- **Limit:** utp installed 4×; patch cord utp no load 6 mm; sctp installed 8×; copper backbone 10×; patch cord sctp no load 50 mm; fibre horizontal no load 25 mm; fibre horizontal under load 50 mm; fibre interbuilding backbone no load 10×; (+5 more, see the source file)
- **Does not apply / exception:** Cat 6A and shielded cable datasheets are commonly stricter than 4x and then govern.; Corrected 24 Sep 2026: the 20x under-load multiplier is interbuilding backbone only. Intrabuilding backbone is 15x and horizontal 2/4-fibre is an absolute mm figure.
- **Basis:** CODE · ANSI/TIA/EIA-568-B.1
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### A-03 — Maximum pair untwist at termination
- **Limit:** max untwist 0.5 in; max untwist 13 mm; cat3 maintain twist within 3 in; cat3 maintain twist within 76 mm; applies to category 5e_and_higher
- **When:** termination.media eq "twisted_pair"
- **Does not apply / exception:** Excess untwist raises crosstalk and can stop 10GBASE-T from passing certification.; The 13 mm limit does not apply to Category 3, which uses the 76 mm figure.
- **Basis:** CODE · ANSI/TIA/EIA-568-B.1
- **Scope:** binds on its own

### A-05 — Cable listing must match the space (CMP, CMR, CM)
- **Limit:** substitution higher_rating_may_replace_lower_never_the_reverse; map {"riser": "CMR", "plenum": "CMP", "general": "CM"}
- **When:** space.type in ["plenum", "riser", "general"]
- **Does not apply / exception:** Air-handling space takes CMP, vertical shaft takes CMR, and CM is only for non-plenum non-riser horizontal runs.
- **Basis:** CODE · NEC Article 800
- **Scope:** binds on its own

### A-06 — Fire-rated penetrations sealed with a listed firestop system
- **Limit:** note intumescent_sleeve_is_one_product_route_not_the_rule; requires listed_firestop_system_matching_assembly_rating
- **When:** penetration.assembly_fire_rated eq true
- **Does not apply / exception:** Every sealed penetration must also appear in the firestop log, rule X-04.
- **Basis:** CODE · Building code and NEC
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### A-07 — Separation from power and Class 1 conductors
- **Limit:** crossing angle 90 °; shared raceway forbidden_without_permanent_barrier; parallel separation distance from_project_spec; applies to ["raceway", "compartment", "box"]
- **Does not apply / exception:** Separation distance is deliberately not a number here. It is a project-spec value, not a rule constant.
- **Basis:** CODE · NEC Article 800
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### A-09 — Bonding and grounding to the telecommunications bonding backbone
- **Limit:** bond to telecommunications_bonding_backbone; scope ["telecom_rooms", "racks", "shielded_cabling"]
- **Basis:** CODE · ANSI/TIA/EIA-607 (J-STD-607-A)
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### A-11 — Certify 100 percent of copper permanent links
- **Limit:** coverage 100 %; retain native_result_files_unedited; not a field test {"dc_resistance": "cable component spec, 9.38 ohms per 100 m max"}; field test set 568b ["wiremap", "length", "insertion_loss", "next", "psnext", "elfext", "pselfext", "return_loss", "propagation_delay", "delay_skew"]; case study parameters ["wiremap", "insertion_loss", "next", "return_loss"]; renamed in later editions {"elfext": "acr_f", "pselfext": "psacr_f"}
- **When:** link.media eq "copper_horizontal"
- **Does not apply / exception:** Native tester files, not only the PDF summary. Both go in the handover pack.; Corrected 24 Sep 2026: DC resistance was wrongly listed as a field-test parameter.
- **Basis:** CODE · ANSI/TIA/EIA-568-B.1
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### A-12 — Test 100 percent of fibre links
- **Limit:** coverage 100 %; before mating end_face_inspection; parameters ["insertion_loss", "polarity"]
- **When:** link.media eq "fibre"
- **Basis:** CODE · ANSI/TIA/EIA-568-B.3
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### A-13 — Horizontal topology and transition points
- **Limit:** max transition or consolidation points 1; topology star_to_horizontal_cross_connect; closet sized per TIA-569; forbidden ["bridged_tap", "splice_in_copper_horizontal"]; closet per floor yes; keep external to outlet ["balun", "impedance_matching_device"]
- **When:** link.media eq "copper_horizontal"
- **Does not apply / exception:** A consolidation point and a transition point may not share a run. See A-17.
- **Basis:** CODE · ANSI/TIA/EIA-568-B.1
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### A-14 — Minimum two telecommunications outlets per work area
- **Limit:** min outlets per work area 2; outlet 1 {"media": "4_pair_100_ohm", "recommended": ["cat5e", "cat6"], "min_category": "cat3"}; outlet 2 {"one_of": [{"media": "4_pair_100_ohm", "category": ["cat5e", "cat6"]}, {"media": "multimode_fibre", "types": ["62.5/125", "50/125"], "fibre_count": 2}]}; not recognized ["1", "2", "4", "5"]; recognized categories ["3", "5e", "6"]
- **Does not apply / exception:** The only rule in the set that emits a quantity rather than a validation result. It is CODE, so under X-06 it can bind without a SOW clause -- which is exactly why its unverified status matters.
- **Basis:** CODE · ANSI/TIA/EIA-568-B.1 (and B.1-4)
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### A-15 — Backbone hierarchy and maximum distances
- **Limit:** max cross connect levels 2; max cross connects passed through 1; topology hierarchical_star; distances m {"copper_voice": {"ic_to_hc": 300, "mc_to_hc": 800, "mc_to_ic": 500}, "multimode_fibre": {"ic_to_hc": 300, "mc_to_hc": 2000, "mc_to_ic": 1700}, "singlemode_fibre": {"ic_to_hc": 300, "mc_to_hc": 3000, "mc_to_ic": 2700}}; jumper max m {"equipment": 30, "main_cross_connect": 20, "intermediate_cross_connect": 20}; distances inclusive of ["cable", "patch_cords", "jumpers", "equipment_cable"]
- **When:** link.segment eq "backbone"
- **Does not apply / exception:** Between any two horizontal cross-connects the signal passes through 3 or fewer cross-connect facilities.
- **Basis:** CODE · ANSI/TIA/EIA-568-B.1
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### A-16 — Maximum pulling tension
- **Limit:** cable ties cinch_loosely_do_not_deform_sheath; multipair copper manufacturer_specification; max tension n {"utp_4_pair": 110, "fibre_inside_plant_2_or_4": 222}; min pull strength n {"fibre_osp": 2670, "fibre_drop": 1335}
- **Does not apply / exception:** Pairs with A-02. Exceeding tension or bend radius damages a link in ways certification may not reveal until later.
- **Basis:** CODE · ANSI/TIA/EIA-568-B.1 and B.3
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### A-17 — Consolidation point placement and limits
- **Limit:** max per horizontal run 1; min distance to telecom room 15 m; recommended min distance to outlet 5 m; location fully_accessible_and_permanent; administered per TIA-606; cross connects permitted at cp no; may share run with transition point no
- **When:** run.has_consolidation_point eq true
- **Does not apply / exception:** The 15 m minimum exists to limit NEXT and return loss, so it is a performance rule, not a convenience.
- **Basis:** CODE · ANSI/TIA/EIA-568-B.1
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### A-18 — MUTOA limits and horizontal length derating
- **Limit:** max work area cord 22 m; max work areas served 12; min per furniture cluster 1; mounting permanent_part_of_building; administered per TIA-606; derating formula C = (102 - H) / (1 + D); derating factor D {"sctp_26awg": 0.5, "utp_sctp_24awg": 0.2}; published table m [{"horizontal": 90, "combined_cords": 10, "work_area_cord": 5}, {"horizontal": 85, "combined_cords": 14, "work_area_cord": 9}, {"horizontal": 80, "combined_cords": 18, "work_area_cord": 13}, {"horizontal": 75, "combined_cords": 22, "work_area_cord": 17}, {"horizontal": 70, "combined_cords": 27, "work_area_cord": 22}]; (+2 more, see the source file)
- **When:** work_area.has_mutoa eq true
- **Does not apply / exception:** Work area cables are labelled at both ends: the outlet end identifies the work area, the work area end identifies the MUTOA and port.
- **Basis:** CODE · ANSI/TIA/EIA-568-B.1
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### A-19 — Propagation delay and delay skew limits
- **Limit:** max cable delay skew ns per 100m 45; measured at mhz 10; max delay skew ns {"channel": 50, "permanent_link": 44}; per mated connection {"skew_ns": 1.25, "delay_ns": 2.5}; max propagation delay ns {"channel": 555, "permanent_link": 498}
- **When:** link.media eq "copper_horizontal"
- **Does not apply / exception:** These are the numeric limits behind two of the A-11 field-test parameters.
- **Basis:** CODE · ANSI/TIA/EIA-568-B.1
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### A-20 — Fibre link attenuation limits and test wavelengths
**DO NOT USE — conflicts with SPT-SC-12.** ELV-A-20 carries a flat 2.0 dB horizontal link limit from 568-B. SC-12 uses a calculated loss budget (length x attenuation + 0.75 dB per connector + 0.3 dB per splice). These are two different acceptance methods and can disagree on the same link; pick one per project.

- **Limit:** max with mutoa 2.0 dB; max splice attenuation 0.3 dB; max with consolidation point 2.75 dB; max horizontal link attenuation 2.0 dB; link attenuation equation cable_attenuation + connector_insertion_loss + splice_insertion_loss; backbone test {"multimode_nm": [850, 1300], "singlemode_nm": [1310, 1550]}; horizontal test {"directions": 1, "wavelengths_nm": [850, 1300]}; min splice return loss db {"multimode": 20, "singlemode": 26, "singlemode_catv": 55}
- **When:** link.media eq "fibre"
- **Does not apply / exception:** Gives A-12 a number. A-12 still carries the end-face inspection requirement, which 568-B does not state.
- **Basis:** CODE · ANSI/TIA/EIA-568-B.1 and B.3
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### A-21 — ScTP screen bonding and screen-to-ground potential
- **Limit:** max screen to ground v dc 1.0; max screen to ground v rms 1.0; bond screen to tgb_in_telecommunications_room; drain wire bonded per TIA-607; bond horizontal screen via screen_termination_to_connecting_hardware
- **When:** cable.screened eq true
- **Does not apply / exception:** A measurable acceptance criterion, unlike the qualitative A-09.; Applies only where screened cable is actually installed.
- **Basis:** CODE · ANSI/TIA/EIA-568-B.1-2 (J-STD-607-A)
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### SC-01 — Horizontal length
- **Limit:** Permanent link <= 90 m; channel <= 100 m; cords <= 10 m total
- **When:** Balanced twisted-pair
- **Does not apply / exception:** MUTOA/consolidation point rules
- **Basis:** CODE · ANSI/TIA-568.0 / .1 · KSA/client: SAES-T-916 - verify; ISO/IEC 11801
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### SC-03 — Slack / service loops
- **Limit:** 3 m in TR; 0.3 m at outlet (copper); fibre 1 m outlet, 3 m TR
- **When:** Horizontal
- **Calculation:** Add to each run length
- **In plain English:** Add the slack lengths (3 m in the telecom room, 0.3 m at the outlet for copper) to every cable run.
- **Basis:** CODE · ANSI/TIA-568.0
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### SC-04 — Bend radius
**DO NOT USE — conflicts with ELV-A-02.** SC-04 states fibre 20x OD under tension as a single figure. ELV-A-02 was corrected on 24 Sep 2026 against the supplied ANSI/TIA/EIA-568-B text, which gives 20x for INTERBUILDING backbone only, 15x for intrabuilding backbone under load, and an absolute 25 mm / 50 mm for horizontal 2- and 4-fibre. SC-04 also omits the copper backbone 10x figure. Do not merge: resolve against a current 568.3-D before either version is approved.

- **Limit:** UTP 4x OD; F/UTP 8x OD; fibre 10x OD unloaded, 20x under tension
- **When:** Installed
- **Calculation:** R_min = k x OD
- **In plain English:** Minimum bend radius = a multiplier x the cable's outer diameter. The multiplier is 4 for UTP, 8 for shielded, and 10 or 20 for fibre.
- **Does not apply / exception:** Bend-insensitive fibre per manufacturer
- **Basis:** CODE · ANSI/TIA-568.0 / .3
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### SC-05 — Pulling tension
- **Limit:** 4-pair UTP <= 110 N (25 lbf)
- **When:** Installation
- **Basis:** CODE · ANSI/TIA-568.0
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### SC-06 — Conduit fill
- **Limit:** <= 40% for 3+ cables (53% one, 31% two)
- **When:** Conduit
- **Calculation:** Fill = sum(pi OD^2/4) / A_conduit
- **In plain English:** Conduit fill = the total cross-section area of all cables / the inside area of the conduit. Must be 40% or less for 3+ cables (53% for one cable, 31% for two).
- **Does not apply / exception:** Short nipples <= 600 mm may reach 60%
- **Basis:** CODE · TIA-569 / NEC Ch.9 Table 1 · KSA/client: SBC 401; SAES-T-911 conduit - verify
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### SC-07 — Conduit runs
- **Limit:** <= 30 m between pull points; <= 2 x 90 deg bends between pull boxes
- **When:** Conduit
- **Does not apply / exception:** Increase size if extra bend unavoidable
- **Basis:** CODE · ANSI/TIA-569 · KSA/client: SAES-T-911 - verify
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### SC-08 — Tray fill
- **Limit:** <= 50% fill; cable depth <= 150 mm
- **When:** Cable tray
- **Calculation:** Fill = sum cable area / tray area
- **In plain English:** Tray fill = total area of all cables / tray area. Must be 50% or less.
- **Basis:** CODE · ANSI/TIA-569 · KSA/client: Project spec
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### SC-09 — Telecom room
- **Limit:** >= 1 TR per floor; extra if floor > 1,000 m2 or any run > 90 m
- **When:** Buildings
- **Calculation:** N_TR >= max(1, ceil(A/1000))
- **In plain English:** Number of telecom rooms = floor area / 1,000 m2, rounded up, with at least one per floor.
- **Basis:** CODE · ANSI/TIA-569 · KSA/client: Project spec
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### SC-10 — Work-area outlets
- **Limit:** >= 2 outlets per work area (~10 m2)
- **When:** Office space
- **Calculation:** N = ceil(A_office/10) x 2
- **In plain English:** Number of outlets = office area / 10 m2 (rounded up) x 2, i.e. two outlets per work area.
- **Does not apply / exception:** Non-office spaces per design
- **Basis:** CODE · ANSI/TIA-568.0 / 569 · KSA/client: Project drawings govern BOQ
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### SC-11 — Power separation
- **Limit:** Maintain separation per standard table (typ. >= 300 mm from unshielded power in open trays)
- **When:** Parallel runs with power
- **Does not apply / exception:** Metal barriers/shielded cable reduce distance
- **Basis:** CODE · ANSI/TIA-569 Annex / EN 50174-2 · KSA/client: SBC 401
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### SC-12 — Fibre loss budget
**DO NOT USE — conflicts with ELV-A-20.** ELV-A-20 carries a flat 2.0 dB horizontal link limit from 568-B. SC-12 uses a calculated loss budget (length x attenuation + 0.75 dB per connector + 0.3 dB per splice). These are two different acceptance methods and can disagree on the same link; pick one per project.

- **Limit:** Loss_calc <= link budget
- **When:** Fibre links
- **Calculation:** Loss = L_km x alpha + n_conn x 0.75 + n_splice x 0.3 dB (alpha: MM 3.5 dB/km @850; SM 1.0 ISP / 0.5 OSP)
- **In plain English:** Total fibre loss = (length in km x loss per km) + (number of connector pairs x 0.75 dB) + (number of splices x 0.3 dB). Compare this against what the equipment can tolerate.
- **Does not apply / exception:** Test results govern acceptance
- **Basis:** CODE · ANSI/TIA-568.3
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### SC-13 — Bonding & grounding
- **Limit:** TMGB/TGB; bonding conductors >= 6 AWG (16 mm2), TBB sized by length
- **When:** All TRs/racks
- **Calculation:** Size per TIA-607 length table
- **In plain English:** Size the bonding backbone conductor from the TIA-607 table based on its length.
- **Basis:** CODE · ANSI/TIA-607 · KSA/client: SBC 401; SAES-T-916 - verify
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### SC-14 — Labelling & admin
- **Limit:** Unique IDs for cables, panels, outlets, pathways
- **When:** All installations
- **Basis:** CODE · ANSI/TIA-606 · KSA/client: Client labelling scheme
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### LP-25 — Building telecom rooms - Structured cabling
- **Limit:** why Standardised, maintainable cabling plant; key numbers Horizontal <=90 m; TC <=500 m2 area 3.0x2.2 m; 800-1,000 m2 3.0x3.4 m; ER 18-24 C; what is used RCDD-qualified design; star topology; TC per 1,000 m2; no false ceiling; 1-h rated walls; testing per SAES-T-634
- **Basis:** LOCAL · SAES-T-916 (2003 public copy - verify current)
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### LP-26 — Outside plant fibre - Fibre OSP
- **Limit:** why Long inter-building runs; key numbers <=0.5 dB/km @1310, <=0.3 @1550; fusion splice avg 0.05 / max 0.1 dB; bend 10x/20x OD; what is used SM fibre in duct (4 in with subducts) or direct-buried; fusion splicing
- **Basis:** LOCAL · SAES-T-624 (2009)
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### A-04 — Cable support interval and prohibited supports
- **Limit:** support interval max 5 ft; support interval min 4 ft; permitted supports ["j_hook", "tray", "conduit"]; prohibited supports ["ceiling_tile", "grid_wire", "pipe", "ductwork"]
- **Does not apply / exception:** Use the support type shown on the drawings.
- **Basis:** SPEC · BICSI practice
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced

### A-08 — Conduit use and fill limit
- **Limit:** max fill 40 %; fill applies from cable count 3; alternatives ["tray", "j_hook", "other_listed_support"]; conduit required when ["spec", "ahj", "protection_need"]
- **When:** pathway.type eq "conduit"
- **Does not apply / exception:** Conduit that is neither on the drawings nor in the SOW is not scope. See X-06.
- **Basis:** SPEC · Project specification
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### A-10 — Label both ends and maintain an administration schedule
- **Limit:** label both_ends; record administration_schedule in; must match as_built_drawings
- **Basis:** SPEC · ANSI/TIA/EIA-606
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced

### SC-02 — Cable quantity estimate
- **Limit:** Boxes of 305 m
- **When:** Per floor/TR
- **Calculation:** Avg = (L_min + L_max)/2 x 1.1 + slack; runs/box = floor(305/Avg); boxes = ceil(runs/runs_per_box)
- **In plain English:** Average cable run = (shortest + longest) / 2, plus 10%, plus slack. Then see how many whole runs fit in one 305 m box, and divide the total number of runs by that to get how many boxes to order (rounded up).
- **Does not apply / exception:** Measured takeoff overrides estimate
- **Basis:** SPEC · BICSI TDMM method (practice) · KSA/client: BOQ trace to drawings (no assumed routing)
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### SC-15 — Cable sheath
- **Limit:** LSZH in enclosed/occupied spaces
- **When:** Indoor
- **Does not apply / exception:** Outdoor/duct: gel-filled/armoured
- **Basis:** SPEC · IEC 60332-3 / 61034 / 60754 · KSA/client: Aramco / KSA project specs typically mandate LSZH
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.
