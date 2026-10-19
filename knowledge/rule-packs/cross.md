# Cross-discipline — rule pack

15 rules. Generated from the database; see
[`../rule-packs/README.md`](README.md) for how to use these and what to output.

---
### X-01 — Confirm adopted code editions with the AHJ and SOW before design
- **Limit:** record on design_basis_page_1; with ["ahj", "sow"]; confirm ["adopted_code_editions", "client_standards"]
- **Does not apply / exception:** In Saudi Arabia check the current SBC 801 text, Civil Defense approval requirements, and whether the project uses TIA-568 or ISO/IEC 11801 for cabling.
- **Basis:** CODE · Authority having jurisdiction
- **Scope:** binds on its own

### X-03 — One cause-and-effect matrix, every line tested
- **Limit:** test every_line_at_acceptance; artefact cause_and_effect_matrix; cardinality exactly_one_per_project; covers ["ahu", "door_locks", "lifts", "voice_alarm", "cctv_call_up"]; implements ["ELV-B-08", "ELV-B-09", "ELV-B-10", "ELV-C-06"]
- **When:** project.has_fire_alarm eq true
- **Does not apply / exception:** A line that is not tested is an output nobody has proven.
- **Basis:** CODE · NFPA 72 control functions
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### X-04 — Maintain a firestop log
- **Limit:** per sealed_penetration; artefact firestop_log; supports ELV-A-06; fields ["location", "assembly_rating", "product", "installer"]
- **When:** project.has_fire_rated_penetrations eq true
- **Does not apply / exception:** Photographs accompany the log in the handover pack.
- **Basis:** CODE · Building and fire code
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### LP-03 — Perimeter fence line - Security lighting
- **Limit:** why Optical cameras need light for colour assessment; lighting must not interfere with intrusion sensors; key numbers Area avg 5 lux; switch-on at 1.6x design lux or 15 lux; lamp replacement <=72 h; what is used Fence-line poles (~5 m at ~20 m spacing) and area lighting on 10-30 m poles; generator-backed; auto on
- **Basis:** LOCAL · SAES-O-204 (2012) 4; HCIS SEC-04
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### LP-08 — Gatehouse interior - Lighting / displays
- **Limit:** why Operators must read screens and see outside at night; key numbers 300 lux at counter; what is used Dimmable interior lighting; bilingual (Arabic/English) status & alarm displays; alarm printer
- **Basis:** LOCAL · SAES-O-204 4.4; HCIS SEC-05 v2.0 (2017) 5.3.7
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity

### LP-09 — Security Control Center / 911 EC - Integrated security + support systems
- **Limit:** why One operator view for time-critical response; SCC is the ERP hub; key numbers 24/7; voice recording 12 months; layout per ISO 11064; displays 1080p or better; what is used Single command & control platform (SACS, ALPRS, IDAS, IDMS, VASS, radio, dispatch); video wall; local ACS on SCC doors; fire detection per SAF-04; dedicated UPS + generator
- **Basis:** LOCAL · SAES-O-205 (22-Mar-2023) 6.8-6.9
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity

### LP-14 — Telecom room - Environmental alarm
- **Limit:** why HVAC failure is the main risk to telecom equipment; what is used High-temperature alarm relayed to Network Operations Control Center
- **Basis:** LOCAL · SAES-B-014 (2004 public copy) 7.7 (verify current edition)
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### LP-17 — Security equipment room - Room design
- **Limit:** why Protect core security servers/NVRs from heat, water and insider access; key numbers HVAC per SAES-K-003 / SAES-T-916; what is used Redundant split/central AC (no window units), cabinet AC where in cabinets; transformers NOT in room (separate room with UPS); locked with entry control; CCTV inside room; no plumbing in walls/ceiling
- **Basis:** LOCAL · SAES-O-205 (22-Mar-2023) 5.13
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity

### LP-23 — Outdoor / coastal installations - All field devices
- **Limit:** why Gulf-region heat, dust and salt destroy under-rated equipment; key numbers Design max: indoor AC 35 C, outdoor sheltered 70 C, unsheltered 80 C (+15 C self-heating rule); dust up to 500 mg/m3; coastal = within 1 km of Gulf / 3 km of Red Sea; what is used Sealed housings (IP66 / NEMA 4X stainless in corrosive); sunshields; rated for extreme heat and sandstorm dust; salt-spray protection near coast
- **Basis:** LOCAL · SAES-T-555 (2012 public copy) App. A (older edition - verify vs SAES-O-201)
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity

### LP-29 — Hospital - patient rooms & wards - Nurse call
- **Limit:** why Staff must locate the calling patient quickly; what is used Integrated nurse call with over-door (corridor) flashers, cancel buttons at door and bed; bed-head unit with nurse call button, telephone and data
- **Basis:** LOCAL · MOH Private Hospitals Design Guide (Scribd copy) 3-3-1-21, 2-6-22; iHFG Part E
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### LP-34 — Hospital - general - Other light current
- **Limit:** why Standard MOH light-current package; what is used Master clock, MATV/satellite, telephone/IP data, intercom (incl. lift guard intercom), gas detection interfaced to FA, mosque audio system
- **Basis:** LOCAL · MOH Private Hospitals Design Guide (Scribd copy) 4-6-7 to 4-6-19, 5-2-37
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### X-02 — Coordinate pathways with other trades before first fix
- **Limit:** avoid surface_trunking_afterwards; before first_fix; route through open_wall_or_ceiling; coordinate with ["electrical", "hvac", "plumbing", "fire"]
- **Basis:** SPEC · SmartPage practice
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced

### X-05 — Named owner and single schedule per shared network element
- **Limit:** elements ["switch", "poe_budget", "vlan", "ip_range"]; requires ["named_owner", "single_schedule"]; supports ["ELV-C-02", "ELV-C-03", "ELV-C-04"]
- **When:** project.has_shared_network eq true
- **Basis:** SPEC · SmartPage practice
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### X-06 — Every rule in a BOQ carries its tag and cites its scope basis
- **Limit:** enforced at boq_transition_to_validated_approved_issued; enforced by forbid_unsupported_scope; requires ["confidence_tag", "drawing_or_sow_citation"]; binding alone ["code"]; not binding alone ["spec", "local"]; accepted citation types ["sow_clause", "drawing", "client_standard"]
- **Does not apply / exception:** This rule is why the other 41 can be stored without becoming quantities by accident.
- **Basis:** SPEC · SmartPage BOQ traceability requirement
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced

### LP-36 — Mosque - Public address / prayer call
- **Limit:** why Adhan coverage outside + intelligible speech inside; key numbers Coverage/SPL per project spec; what is used Separate prayer-call (external horn/column speakers on minaret) and internal prayer-hall PA; zoned; not a listed voice-evac system unless designed as one
- **Basis:** SPEC · Project practice (verify against project SOW)
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.
