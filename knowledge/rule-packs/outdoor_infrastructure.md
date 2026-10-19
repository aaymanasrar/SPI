# Outdoor Infrastructure and Mast — rule pack

6 rules. Generated from the database; see
[`../rule-packs/README.md`](README.md) for how to use these and what to output.

---
### D-01 — Obtain mast setback distances in writing before design
- **Limit:** before design; obtain setback_distance_in_writing; distance not_supplied; from ["local_regulator", "municipality"]; subjects ["homes", "schools", "high_voltage_lines"]
- **When:** project.includes_mast eq true
- **Does not apply / exception:** Encoding a setback number here would be an invention. The deliverable is the written confirmation, not a distance.
- **Basis:** LOCAL · Local regulator and municipality
- **Scope:** applies only in a single jurisdiction; cite the instrument before it becomes a quantity

### D-02 — Generator setback from the neighbouring property line
- **Limit:** min distance 5 m; from neighbouring_property_line; excludes fences; jurisdiction NG
- **When:** site.country eq "NG"; site.has_generator eq true
- **Does not apply / exception:** Measured to the property line, not to the fence.
- **Basis:** LOCAL · NCC Guidelines on Technical Specifications for Masts and Towers (2009), s.3(5)
- **Scope:** applies only in NG; cite the instrument before it becomes a quantity

### D-03 — Generator sound-proofing and anti-vibration mounting
- **Limit:** objective minimise_vibration; jurisdiction NG; measures ["sound_proofing", "shock_absorber_mounts"]
- **When:** site.country eq "NG"; site.has_generator eq true
- **Basis:** LOCAL · NCC Guidelines on Technical Specifications for Masts and Towers (2009)
- **Scope:** applies only in NG; cite the instrument before it becomes a quantity

### D-04 — Keep noise within the residential limit
- **Limit:** residential day 50 dB; residential night 35 dB; jurisdiction NG; limit source environmental_regulator
- **When:** site.adjacent_use eq "residential"
- **Does not apply / exception:** The dB figures are jurisdiction-bound. Replace them, do not reuse them.
- **Basis:** LOCAL · Nigerian environmental regulator, via Helios case
- **Scope:** applies only in NG; cite the instrument before it becomes a quantity

### D-05 — Demonstrate RF exposure within the national limit
- **Limit:** at accessible_locations; demonstrate rf_exposure_within_national_limit; limit value not_supplied; limit source national_regulator; then ["mark", "fence"]
- **When:** project.includes_rf_transmitter eq true
- **Does not apply / exception:** Part D is probably outside a typical Saudi ICT and ELV bid. Confirm scope before pricing any of it.
- **Basis:** LOCAL · National regulator, ICNIRP-derived
- **Scope:** applies only in a single jurisdiction; cite the instrument before it becomes a quantity
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### D-06 — Keep an as-built distance survey and noise record
- **Limit:** per ["generator", "mast"]; records ["as_built_distance_survey", "noise_measurement"]
- **When:** project.includes_mast_or_generator eq true
- **Does not apply / exception:** Your own records are the defence. This is the rule the case actually establishes.
- **Basis:** SPEC · SmartPage practice, from the Helios case
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced
