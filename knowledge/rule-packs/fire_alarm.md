# Fire Alarm — rule pack

47 rules. Generated from the database; see
[`../rule-packs/README.md`](README.md) for how to use these and what to output.

**2 rule(s) in this pack are marked DO NOT USE.** They are contradicted by another rule and the conflict is unresolved. Skip them.

---
### B-01 — Smoke detector spacing on a smooth flat ceiling
- **Limit:** max spacing 9.1 m; max spacing 30 ft; max wall distance 4.6 m; max wall distance 15 ft; override detector_listed_spacing_if_smaller; wall distance basis half_of_listed_spacing
- **When:** detector.type eq "smoke"; ceiling.profile eq "smooth_flat"
- **Does not apply / exception:** Beams, joists, partitions and airflow change this layout. See B-04.
- **Basis:** CODE · NFPA 72
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### B-02 — Heat detector listed spacing and height derating
**DO NOT USE — supersedes with SPT-FA-04.** ELV-B-02 carried a single recalled multiplier (roughly 0.7x at a 20 ft ceiling). FA-04 gives the full NFPA 72 Table 17.6.3.5.1 height-factor ladder from 0.91 down to 0.34. FA-04 is the better rule; ELV-B-02 should be superseded rather than kept alongside it.

- **Limit:** listed spacing 15 m; listed spacing 50 ft; derate at 20ft 0.7×; valid to ceiling height 10 ft; derate reduce_as_ceiling_height_rises; derate applies to fixed_temperature
- **When:** detector.type eq "heat"
- **Does not apply / exception:** Use the listed spacing on the device, not the generic figure, wherever the listing is smaller.
- **Basis:** CODE · NFPA 72
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### B-03 — Minimum detector clearance from an air supply diffuser
- **Limit:** min distance 0.9 m; min distance 3 ft; from air_supply_diffuser
- **Does not apply / exception:** Smoke dilution at the diffuser delays detection, which is why this is a hard clearance and not a preference.
- **Basis:** CODE · NFPA 72
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### B-04 — Recompute spacing for ceiling geometry and airflow
- **Limit:** before fixing_detector_positions; drawings ["reflected_ceiling_plan", "hvac"]; recompute on ["ceiling_height", "beam", "joist", "partition", "airflow", "diffuser"]
- **Does not apply / exception:** This rule is why B-01 and B-02 cannot be applied from a floor plan alone.
- **Basis:** CODE · NFPA 72 Chapter 17
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### B-06 — Fix the BS 5839-1 system category before counting detectors
- **Limit:** L1 all_areas; L2 defined_risk_areas; must precede detector_count; categories ["L1", "L2", "L3", "L4", "L5", "P1", "P2", "M"]
- **When:** project.standard eq "BS 5839-1"
- **Does not apply / exception:** A detector quantity produced before the category is fixed has no basis. This rule gates the Part B count.
- **Basis:** CODE · BS 5839-1
- **Scope:** binds on its own

### B-07 — BS 5839-1 detector coverage radius
- **Limit:** heat radius 5.3 m; smoke radius 7.5 m; ceiling normal
- **When:** project.standard eq "BS 5839-1"; ceiling.profile eq "normal"
- **Does not apply / exception:** Flagged unconfirmed by the source author. Approving this version without reading BS 5839-1 would put an unchecked number into a detector count.
- **Basis:** CODE · BS 5839-1
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### B-08 — Automatic air handling unit shutdown on fire alarm
- **Limit:** action shutdown_or_control_on_alarm; target air_handling_unit; arrangement per_mechanical_design; appears as ["facp_output", "relay_or_module_in_point_list"]
- **When:** project.has_ahu eq true
- **Does not apply / exception:** Every line must appear in the single cause-and-effect matrix, rule X-03.
- **Basis:** CODE · NFPA 90A, NFPA 72
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### B-09 — Electromagnetic locks release on alarm and on power loss
- **Limit:** scope egress_doors; target electromagnetic_lock; failure mode fail_safe; release on ["fire_alarm_signal", "loss_of_power"]
- **When:** door.has_electromagnetic_lock eq true; door.on_egress_route eq true
- **Does not apply / exception:** Same physical requirement as C-06, approached from the fire alarm side. Both are encoded; a design satisfying one but not the other is a conflict to surface, not to resolve silently.
- **Basis:** CODE · NFPA 101 and local building code
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### B-10 — Emergency voice evacuation where the fire strategy requires it
- **Limit:** test speech_intelligibility_on_completion; provide when building_class_or_fire_strategy_requires
- **When:** fire_strategy.requires_voice_evacuation eq true
- **Does not apply / exception:** Do not price voice evacuation from this rule alone. The fire strategy is what makes it scope.
- **Basis:** CODE · NFPA 72 Chapter 24
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### FA-01 — Smoke detector - max spacing
- **Limit:** 9.1 m (30 ft) nominal
- **When:** Smooth, flat ceiling
- **Calculation:** Coverage approx 84 m2 per detector (S squared)
- **In plain English:** Each smoke detector covers a square about 9.1 m on each side. 9.1 x 9.1 = about 84 m2, so one detector protects roughly 84 m2 of flat ceiling.
- **Does not apply / exception:** Beams/joists, sloped ceilings, high air movement, performance-based design, manufacturer listing lower
- **Basis:** CODE · NFPA 72 Ch.17 (§17.7.3.2.3) · KSA/client: SBC 801 §907 (adopts NFPA 72 for installation)
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### FA-02 — Smoke detector - 0.7S rule
- **Limit:** Every point on ceiling <= 0.7 x S from a detector
- **When:** Irregular room shapes
- **Calculation:** R = 0.7 x 9.1 = 6.37 m radius
- **In plain English:** Draw a circle around each detector with a radius of 0.7 times the spacing. With 9.1 m spacing that is 6.37 m. Every spot on the ceiling must fall inside one of these circles.
- **Does not apply / exception:** Corridors: spacing along centreline, max S/2 from end wall
- **Basis:** CODE · NFPA 72 Ch.17 (§17.7.3.2.3) · KSA/client: SBC 801 §907 (adopts NFPA 72 for installation)
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### FA-03 — Smoke detector - wall distance
- **Limit:** <= S/2 (4.55 m) from walls; sidewall mount within 300 mm of ceiling
- **When:** Smooth ceiling
- **Calculation:** S/2 = 9.1 / 2
- **In plain English:** No detector may be further from a wall than half the spacing. Half of 9.1 m is 4.55 m.
- **Does not apply / exception:** Dead-air-space rules differ for heat detectors
- **Basis:** CODE · NFPA 72 Ch.17 · KSA/client: SBC 801 §907 (adopts NFPA 72 for installation)
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### FA-04 — Heat detector - spacing
**DO NOT USE — supersedes with ELV-B-02.** ELV-B-02 carried a single recalled multiplier (roughly 0.7x at a 20 ft ceiling). FA-04 gives the full NFPA 72 Table 17.6.3.5.1 height-factor ladder from 0.91 down to 0.34. FA-04 is the better rule; ELV-B-02 should be superseded rather than kept alongside it.

- **Limit:** Listed spacing (typ. 7.6-15.2 m) x height factor
- **When:** Ceiling > 3.0 m (10 ft)
- **Calculation:** S_adj = S_listed x factor (3-3.7 m:0.91, 3.7-4.3:0.84, 4.3-4.9:0.77, 4.9-5.5:0.71, 5.5-6.1:0.64, 6.1-6.7:0.58, 6.7-7.3:0.52, 7.3-7.9:0.46, 7.9-8.5:0.40, 8.5-9.1:0.34)
- **In plain English:** Take the heat detector's listed spacing and multiply it by a reduction factor based on ceiling height. The higher the ceiling, the smaller the factor, so detectors must be closer together. Example: at 5 m ceiling height the factor is 0.71.
- **Does not apply / exception:** Listing may give its own height reduction; beams/joists apply further reduction
- **Basis:** CODE · NFPA 72 Table 17.6.3.5.1 · KSA/client: SBC 801 §907 (adopts NFPA 72 for installation)
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### FA-05 — Heat detector - sidewall mounting
- **Limit:** 100-300 mm below ceiling
- **When:** Sidewall install
- **Does not apply / exception:** Not in dead-air space at ceiling/wall junction
- **Basis:** CODE · NFPA 72 Ch.17 · KSA/client: SBC 801 §907 (adopts NFPA 72 for installation)
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### FA-06 — Smoke detector - beamed ceiling
- **Limit:** Beam depth < 0.1H -> smooth-ceiling spacing; >=0.1H and beam spacing >=0.4H -> detector in each pocket; >=0.1H and spacing <0.4H -> reduce spacing perpendicular to beams by 50%
- **When:** Solid beams, level ceiling
- **Calculation:** Check d_beam / H and W_pocket / H
- **In plain English:** Compare the beam depth and the gap between beams against the ceiling height (H). Shallow beams (under 10% of H) are ignored. Deep beams far apart need a detector in each pocket. Deep beams close together mean you halve the spacing across the beams.
- **Does not apply / exception:** Sloped beamed ceilings, beam pockets used as smoke reservoirs
- **Basis:** CODE · NFPA 72 §17.7.3.2.4 · KSA/client: SBC 801 §907 (adopts NFPA 72 for installation)
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### FA-07 — Heat detector - beamed/joisted ceiling
- **Limit:** Beams > 100 mm deep: spacing perpendicular to beams <= 2/3 listed; beams > 450 mm deep and > 2.4 m o.c.: each bay treated as separate area
- **When:** Solid beams/joists
- **Calculation:** S_perp = 0.667 x S_listed
- **In plain English:** Across the direction of the beams, the heat detector spacing is cut to two-thirds of its listed value.
- **Does not apply / exception:** Open-web joists treated as smooth if <= 100 mm solid chord
- **Basis:** CODE · NFPA 72 §17.6.3 · KSA/client: SBC 801 §907 (adopts NFPA 72 for installation)
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### FA-08 — Sloped/peaked ceiling detector
- **Limit:** One row within 0.9 m (3 ft) of peak, measured horizontally
- **When:** Slope > 1:8
- **Calculation:** Additional rows per horizontal-projection spacing
- **In plain English:** On sloped ceilings, measure spacing on a flat plan view (as if looking down from above) and add extra rows of detectors as needed. One row must be within 0.9 m of the peak.
- **Does not apply / exception:** Shed ceilings follow high-side rule
- **Basis:** CODE · NFPA 72 Ch.17 · KSA/client: SBC 801 §907 (adopts NFPA 72 for installation)
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### FA-09 — Detector distance from HVAC diffuser
- **Limit:** >= 0.9 m (3 ft) from supply diffuser / return grille
- **When:** Any forced-air space
- **Does not apply / exception:** Air-sampling / listed high-velocity applications
- **Basis:** CODE · NFPA 72 Ch.17 · KSA/client: SBC 801 §907 (adopts NFPA 72 for installation)
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### FA-10 — Duct smoke detector
- **Limit:** Required on supply side
- **When:** AHU > 944 L/s (2,000 cfm)
- **Calculation:** Q_AHU vs 944 L/s
- **In plain English:** Check the air handler's airflow. If it moves more than 944 litres per second (2,000 cfm), a duct smoke detector is needed on the supply side.
- **Does not apply / exception:** Units serving single space with area detection per code alternative
- **Basis:** CODE · IMC §606 / NFPA 90A · KSA/client: SBC 501 (Mechanical) §606 mirrors IMC
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### FA-11 — Manual call point - location
- **Limit:** Within 1.5 m (5 ft) of each exit door; travel distance <= 61 m (200 ft) on same floor
- **When:** Every exit on every floor where required
- **Calculation:** Count = exits + extra so no point > 61 m
- **In plain English:** Put one call point at every exit, then add more until nobody on the floor has to walk more than 61 m to reach one.
- **Does not apply / exception:** Group widths > 12 m: MCP on each side of opening
- **Basis:** CODE · NFPA 72 §17.15.9 (formerly 17.14) · KSA/client: SBC 801 §907.4.2
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### FA-12 — Manual call point - mounting height
- **Limit:** Operable part 1.07-1.22 m (42-48 in) AFF
- **When:** Wall mounted
- **Does not apply / exception:** Client spec may fix single height (e.g., 1.2 m)
- **Basis:** CODE · NFPA 72 §17.15.9 · KSA/client: SBC 801 §907.4.2.2
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### FA-13 — Audible - public mode
- **Limit:** >= 15 dB above avg ambient OR >= 5 dB above max ambient lasting >= 60 s (greater); max 110 dBA
- **When:** Measured 1.5 m AFF, occupiable areas
- **Calculation:** SPL_req = max(L_avg+15, L_max+5)
- **In plain English:** Alarm sounders must be loud enough to hear over the background noise. Take whichever is higher: normal noise plus 15 dB, or the loudest sustained noise (lasting 60 seconds or more) plus 5 dB.
- **Does not apply / exception:** Private mode: 10 dB above avg ambient; voice intelligibility per §18.4.10
- **Basis:** CODE · NFPA 72 §18.4.3 · KSA/client: SBC 801 §907.5.2.1.1 / .1.2
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### FA-14 — Audible - sleeping areas
- **Limit:** Greater of 15 dB > ambient, 5 dB > max 60 s, or 75 dBA at pillow; 520 Hz low-frequency tone
- **When:** Sleeping rooms
- **Does not apply / exception:** Existing systems per retroactive provisions
- **Basis:** CODE · NFPA 72 §18.4.6 · KSA/client: SBC 801 §907.5.2.1
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### FA-15 — Visual - wall strobe height
- **Limit:** Entire lens 2.03-2.44 m (80-96 in) AFF
- **When:** Wall mounted
- **Does not apply / exception:** Ceiling > 3 m or low-ceiling alternatives per §18.5.5
- **Basis:** CODE · NFPA 72 §18.5.5 · KSA/client: SBC 801 §907.5.2.3
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### FA-16 — Visual - room candela (1 strobe, wall)
- **Limit:** 6.1x6.1 m:15 cd; 8.5x8.5:30; 12.2x12.2:60; 13.7x13.7:75; 16.5x16.5:95; 16.8x16.8:115; 19.2x19.2:135; 20.7x20.7:185
- **When:** Square room, 1 strobe centred on wall
- **Calculation:** Select next larger room size
- **In plain English:** Look up the room size in the table and pick the strobe brightness (candela) for it. If the room falls between two sizes, use the bigger size's rating.
- **Does not apply / exception:** Multiple strobes / ceiling mount use Table (b); synchronise >2 in field of view
- **Basis:** CODE · NFPA 72 Table 18.5.5.4.1(a) · KSA/client: SBC 801 §907.5.2.3
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### FA-17 — Visual - corridors
- **Limit:** 15 cd min; <= 4.6 m from end; <= 30.5 m apart
- **When:** Corridor <= 6.1 m wide
- **Calculation:** N = ceil((L - 9.2)/30.5) + 1
- **In plain English:** Take the corridor length, subtract the 9.2 m covered by the two end strobes, divide the rest by 30.5 m, round up, and add 1. That gives the number of strobes.
- **Does not apply / exception:** Wider corridors treated as rooms
- **Basis:** CODE · NFPA 72 §18.5.5.5 · KSA/client: SBC 801 §907.5.2.3
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### FA-18 — Secondary power - batteries
- **Limit:** 24 h standby + 5 min alarm (15 min for EVACS)
- **When:** All FACP/NAC panels
- **Calculation:** Ah = (I_sb x 24 + I_al x t_al) x 1.2 (20% margin = practice)
- **Calculator:** `calc_engine.fire_alarm_battery()` — do not do this arithmetic yourself; call the module and quote its CalcResult.
- **In plain English:** Battery size = (standby current x 24 hours) + (alarm current x alarm time), then add 20% extra as a safety margin.
- **Does not apply / exception:** Generator-backed systems: 4 h standby permitted where allowed
- **Basis:** CODE · NFPA 72 §10.6.7 · KSA/client: SBC 801 §907; Aramco/Civil Defense may require longer
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### FA-21 — Circuit survivability
- **Limit:** Level 2 or 3 pathways for EVACS in partial-evac/high-rise
- **When:** Relocation/partial evacuation
- **Does not apply / exception:** Fully sprinklered + AHJ acceptance
- **Basis:** CODE · NFPA 72 §24.3.14 / Ch.12 · KSA/client: SBC 801 §907
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### FA-22 — Elevator recall detection
- **Limit:** Smoke detectors in lift lobbies, machine room, hoistway top (if sprinklered)
- **When:** Elevators with Phase I recall
- **Does not apply / exception:** Heat detectors where smoke unsuitable
- **Basis:** CODE · NFPA 72 §21.3; ASME A17.1 · KSA/client: SBC 801 §607
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### LP-35 — Mosque (Group A-3) - Fire alarm
- **Limit:** why Assembly occupancy thresholds; key numbers Threshold 300 occupants; what is used Manual fire alarm system when occupant load >=300 (or >100 above/below exit discharge); automatic detection per specific rooms (electrical, AHU)
- **Basis:** CODE · SBC 801 907.2.1 (IFC 2018 basis - verify Saudi amendment)
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### LP-37 — Office building (Group B) - Fire alarm
- **Limit:** why Business occupancy thresholds; key numbers 500 / 100 occupants; what is used Manual fire alarm when total occupant load >=500 or >100 above/below exit discharge; automatic sprinklers usually provide detection/notification
- **Basis:** CODE · SBC 801 907.2.2 (IFC 2018 basis - verify)
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### LP-38 — School (Group E) - Fire alarm / voice
- **Limit:** why Child occupants need controlled, intelligible evacuation; key numbers 50 / 100 occupants; what is used Manual fire alarm for occupant load >=50; emergency voice/alarm communication when >100
- **Basis:** CODE · SBC 801 907.2.3 (IFC 2018 basis - verify)
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### LP-39 — Mall / retail (Group M) - Fire alarm / voice
- **Limit:** why Large transient public; key numbers 500 / 100 occupants; what is used Manual fire alarm for occupant load >=500 or >100 above/below exit discharge; EVACS in covered malls above size threshold
- **Basis:** CODE · SBC 801 907.2.7, 907.2.20 (IFC 2018 basis - verify)
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### LP-40 — Hotel (Group R-1) - Fire alarm
- **Limit:** why Sleeping occupants; key numbers 75 dBA at pillow or 15 dB > ambient; what is used Manual FA + automatic smoke detection in interior corridors; smoke alarms in guest rooms; low-frequency 520 Hz sounders in sleeping rooms
- **Basis:** CODE · SBC 801 907.2.8; NFPA 72 18.4.6
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### LP-41 — Apartments (Group R-2) - Fire alarm
- **Limit:** why Sleeping occupants in multi-unit buildings; key numbers 3 stories / 16 units; what is used Manual FA where 3 or more stories or >16 dwelling units; smoke alarms in units
- **Basis:** CODE · SBC 801 907.2.9 (IFC 2018 basis - verify)
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### LP-42 — High-rise building - Fire alarm / voice
- **Limit:** why Phased evacuation of tall buildings; key numbers Occupied floor >23 m (75 ft) above fire-department access; what is used Automatic smoke detection + emergency voice/alarm communication; fire command centre; firefighter phones
- **Basis:** CODE · SBC 801 907.2.13 (IFC 2018 basis - verify)
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### LP-44 — Kitchens, generator & mechanical rooms - Fire alarm
- **Limit:** why Nuisance-alarm avoidance; key numbers Spacing per listing x height factor; what is used Heat detectors (rate-of-rise or fixed) where smoke detectors would false-alarm; flame detectors at high-hazard points
- **Basis:** CODE · NFPA 72 Ch.17; MOH Private Hospitals Design Guide (Scribd copy) 5-2-38 to 5-2-40
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### LP-11 — Control room / PIB / SIH / comms building - Fire alarm
- **Limit:** why Electronics-dense, continuously critical buildings; early smoke detection before damage; key numbers Designer: registered engineer with 5 yrs FA experience; what is used Mandatory addressable FA; spot smoke detectors in room, under raised floor and above suspended ceiling; local panel at building entrance; common alarm to plant control room via DCS or hardwired annunciator
- **Basis:** LOCAL · SAES-B-014 (2004 public copy) 7.1-7.5 (verify current edition)
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### LP-12 — Floor-standing I/O, ESD, UPS cabinets - Fire alarm
- **Limit:** why Very early warning inside cabinets where fires start small; what is used Air-sampling (high-sensitivity) or point smoke detection with adjustable set points
- **Basis:** LOCAL · SAES-B-014 (2004 public copy) 7.6 (verify current edition)
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### LP-13 — Electrical substation - Fire alarm
- **Limit:** why Large open volumes with high ceilings; beams cover long spans cheaply; key numbers Applies to substations >100 m2; what is used Projected-beam smoke detection, addressable
- **Basis:** LOCAL · SAES-B-014 (2004 public copy) 7.8 (verify current edition)
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### LP-15 — Battery room - Fire alarm
- **Limit:** why Battery thermal events; what is used Addressable spot smoke detection
- **Basis:** LOCAL · SAES-B-014 (2004 public copy) 5.14 (verify current edition)
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### LP-27 — Electrical/electronic rooms & cable areas - Fire alarm
- **Limit:** why Cable/electronics fires are the dominant building hazard; what is used Smoke detection & alarm in buildings/rooms/enclosures with electrical-electronic equipment and cabling; manual pull boxes in occupied buildings per Saudi Building Code
- **Basis:** LOCAL · HCIS SAF (Light & Non-Industrial, 2017)
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### LP-28 — Hospital - whole building - Fire alarm + interfaces
- **Limit:** why Defend-in-place occupancy - compartmentation and controlled evacuation; what is used NFPA 72 system; duct smoke detectors tied to FACP; FACP interfaces to lifts, AC, BMS, PA and magnetic door holders; external fire exits release on alarm; PA used for voice evacuation
- **Basis:** LOCAL · MOH Private Hospitals Design Guide (Scribd copy) 4-6-11 to 4-6-14, 8-1-13
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### B-05 — Aspirating smoke detection selection and pipe network sizing
- **Limit:** driver design_brief; sizing manufacturer_calculation_software; boq term aspirating_smoke_detection; constraint within_maximum_smoke_transport_time; use when ["high_airflow", "tall_ceiling", "hidden_space", "very_early_warning"]
- **When:** space.condition in ["high_airflow", "tall_ceiling", "hidden_space", "very_early_warning_required"]
- **Does not apply / exception:** VESDA is one manufacturer brand. Write aspirating smoke detection in the BOQ unless the SOW names a brand.
- **Basis:** SPEC · NFPA 72, EN 54-20
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### B-11 — Test 100 percent of devices at acceptance and arrange monitoring
- **Limit:** device test coverage 100 %; retain test_record; monitoring per_fire_strategy
- **Calculator:** `calc_engine.fire_alarm_battery()` — do not do this arithmetic yourself; call the module and quote its CalcResult.
- **Does not apply / exception:** Monitoring to a receiving point is scope only where the fire strategy or SOW requires it.
- **Basis:** SPEC · NFPA 72 Chapter 14
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### FA-19 — NAC voltage drop
- **Limit:** End-of-line V >= appliance listed min (typ. 16 V)
- **When:** 24 V NAC
- **Calculation:** V_EOL = 20.4 V - I x R/m x 2L  (20.4 V = battery end voltage)
- **Calculator:** `calc_engine.nac_end_of_line()` — do not do this arithmetic yourself; call the module and quote its CalcResult.
- **In plain English:** The voltage at the last device = battery end voltage (20.4 V) minus the voltage lost in the wire. Wire loss = current x wire resistance x the total wire length there and back (2 x one-way length).
- **Does not apply / exception:** Regulated/boosted NAC PSUs per listing
- **Basis:** SPEC · Manufacturer + NFPA 72 Ch.10 · KSA/client: Aramco: SAES-B-014 / project SOW governs where stricter
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### FA-20 — Loop loading spare
- **Limit:** Design <= 80% of loop device & current capacity
- **When:** SLC / NAC circuits
- **Calculation:** Spare = 1 - used/max >= 20%
- **In plain English:** Spare capacity = 1 minus (what is used / the maximum allowed). It must be at least 20%, meaning the loop is loaded no more than 80%.
- **Does not apply / exception:** Client spec may require 25%
- **Basis:** SPEC · Project spec / practice · KSA/client: Aramco: SAES-B-014 / project SOW governs where stricter
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.
