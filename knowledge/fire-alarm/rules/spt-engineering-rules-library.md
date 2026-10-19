# Fire Alarm - SPT Engineering Rules Library

**Source:** Engineering Rules Library - ELV / ICT / Fire (SPT Pre-Sales, compiled
29 Sep 2026), `Engineering_Rules_Library.xlsx`. See
[the source record](../../standards-references/spt-engineering-rules-library/README.md) for the basis legend, the precedence
order, the library's stated limitations, and how these rules relate to the 57 already
encoded from the earlier documents.

**System:** `fire_alarm` · **Rules:** 22 (Code 16, Code - verify 4, Practice 2)

> **Basis is not confidence.** `Code` and `Code - verify` are both encoded with
> `confidence = code`; the difference is that `Code - verify` needs its clause, edition
> or value checked before it reaches a submittal, which is recorded in
> `verification_note` and raised as `critical_review` rather than `error`. `Practice`
> is encoded as `confidence = spec` and cannot become scope on its own (ELV-X-06).

| ID | Requirement | Value / limit | Condition | Calculation | Source | Saudi / client overlay | Exception | Basis |
|---|---|---|---|---|---|---|---|---|
| FA-01 | Smoke detector - max spacing | 9.1 m (30 ft) nominal | Smooth, flat ceiling | Coverage approx 84 m2 per detector (S squared) | NFPA 72 Ch.17 (§17.7.3.2.3) | SBC 801 §907 (adopts NFPA 72 for installation) | Beams/joists, sloped ceilings, high air movement, performance-based design, manufacturer listing lower | Code |
| FA-02 | Smoke detector - 0.7S rule | Every point on ceiling <= 0.7 x S from a detector | Irregular room shapes | R = 0.7 x 9.1 = 6.37 m radius | NFPA 72 Ch.17 (§17.7.3.2.3) | SBC 801 §907 (adopts NFPA 72 for installation) | Corridors: spacing along centreline, max S/2 from end wall | Code |
| FA-03 | Smoke detector - wall distance | <= S/2 (4.55 m) from walls; sidewall mount within 300 mm of ceiling | Smooth ceiling | S/2 = 9.1 / 2 | NFPA 72 Ch.17 | SBC 801 §907 (adopts NFPA 72 for installation) | Dead-air-space rules differ for heat detectors | Code |
| FA-04 | Heat detector - spacing | Listed spacing (typ. 7.6-15.2 m) x height factor | Ceiling > 3.0 m (10 ft) | S_adj = S_listed x factor (3-3.7 m:0.91, 3.7-4.3:0.84, 4.3-4.9:0.77, 4.9-5.5:0.71, 5.5-6.1:0.64, 6.1-6.7:0.58, 6.7-7.3:0.52, 7.3-7.9:0.46, 7.9-8.5:0.40, 8.5-9.1:0.34) | NFPA 72 Table 17.6.3.5.1 | SBC 801 §907 (adopts NFPA 72 for installation) | Listing may give its own height reduction; beams/joists apply further reduction | Code |
| FA-05 | Heat detector - sidewall mounting | 100-300 mm below ceiling | Sidewall install | — | NFPA 72 Ch.17 | SBC 801 §907 (adopts NFPA 72 for installation) | Not in dead-air space at ceiling/wall junction | Code |
| FA-06 | Smoke detector - beamed ceiling | Beam depth < 0.1H -> smooth-ceiling spacing; >=0.1H and beam spacing >=0.4H -> detector in each pocket; >=0.1H and spacing <0.4H -> reduce spacing perpendicular to beams by 50% | Solid beams, level ceiling | Check d_beam / H and W_pocket / H | NFPA 72 §17.7.3.2.4 | SBC 801 §907 (adopts NFPA 72 for installation) | Sloped beamed ceilings, beam pockets used as smoke reservoirs | Code - verify |
| FA-07 | Heat detector - beamed/joisted ceiling | Beams > 100 mm deep: spacing perpendicular to beams <= 2/3 listed; beams > 450 mm deep and > 2.4 m o.c.: each bay treated as separate area | Solid beams/joists | S_perp = 0.667 x S_listed | NFPA 72 §17.6.3 | SBC 801 §907 (adopts NFPA 72 for installation) | Open-web joists treated as smooth if <= 100 mm solid chord | Code - verify |
| FA-08 | Sloped/peaked ceiling detector | One row within 0.9 m (3 ft) of peak, measured horizontally | Slope > 1:8 | Additional rows per horizontal-projection spacing | NFPA 72 Ch.17 | SBC 801 §907 (adopts NFPA 72 for installation) | Shed ceilings follow high-side rule | Code |
| FA-09 | Detector distance from HVAC diffuser | >= 0.9 m (3 ft) from supply diffuser / return grille | Any forced-air space | — | NFPA 72 Ch.17 | SBC 801 §907 (adopts NFPA 72 for installation) | Air-sampling / listed high-velocity applications | Code |
| FA-10 | Duct smoke detector | Required on supply side | AHU > 944 L/s (2,000 cfm) | Q_AHU vs 944 L/s | IMC §606 / NFPA 90A | SBC 501 (Mechanical) §606 mirrors IMC | Units serving single space with area detection per code alternative | Code - verify |
| FA-11 | Manual call point - location | Within 1.5 m (5 ft) of each exit door; travel distance <= 61 m (200 ft) on same floor | Every exit on every floor where required | Count = exits + extra so no point > 61 m | NFPA 72 §17.15.9 (formerly 17.14) | SBC 801 §907.4.2 | Group widths > 12 m: MCP on each side of opening | Code |
| FA-12 | Manual call point - mounting height | Operable part 1.07-1.22 m (42-48 in) AFF | Wall mounted | — | NFPA 72 §17.15.9 | SBC 801 §907.4.2.2 | Client spec may fix single height (e.g., 1.2 m) | Code |
| FA-13 | Audible - public mode | >= 15 dB above avg ambient OR >= 5 dB above max ambient lasting >= 60 s (greater); max 110 dBA | Measured 1.5 m AFF, occupiable areas | SPL_req = max(L_avg+15, L_max+5) | NFPA 72 §18.4.3 | SBC 801 §907.5.2.1.1 / .1.2 | Private mode: 10 dB above avg ambient; voice intelligibility per §18.4.10 | Code |
| FA-14 | Audible - sleeping areas | Greater of 15 dB > ambient, 5 dB > max 60 s, or 75 dBA at pillow; 520 Hz low-frequency tone | Sleeping rooms | — | NFPA 72 §18.4.6 | SBC 801 §907.5.2.1 | Existing systems per retroactive provisions | Code |
| FA-15 | Visual - wall strobe height | Entire lens 2.03-2.44 m (80-96 in) AFF | Wall mounted | — | NFPA 72 §18.5.5 | SBC 801 §907.5.2.3 | Ceiling > 3 m or low-ceiling alternatives per §18.5.5 | Code |
| FA-16 | Visual - room candela (1 strobe, wall) | 6.1x6.1 m:15 cd; 8.5x8.5:30; 12.2x12.2:60; 13.7x13.7:75; 16.5x16.5:95; 16.8x16.8:115; 19.2x19.2:135; 20.7x20.7:185 | Square room, 1 strobe centred on wall | Select next larger room size | NFPA 72 Table 18.5.5.4.1(a) | SBC 801 §907.5.2.3 | Multiple strobes / ceiling mount use Table (b); synchronise >2 in field of view | Code |
| FA-17 | Visual - corridors | 15 cd min; <= 4.6 m from end; <= 30.5 m apart | Corridor <= 6.1 m wide | N = ceil((L - 9.2)/30.5) + 1 | NFPA 72 §18.5.5.5 | SBC 801 §907.5.2.3 | Wider corridors treated as rooms | Code |
| FA-18 | Secondary power - batteries | 24 h standby + 5 min alarm (15 min for EVACS) | All FACP/NAC panels | Ah = (I_sb x 24 + I_al x t_al) x 1.2 (20% margin = practice) | NFPA 72 §10.6.7 | SBC 801 §907; Aramco/Civil Defense may require longer | Generator-backed systems: 4 h standby permitted where allowed | Code |
| FA-19 | NAC voltage drop | End-of-line V >= appliance listed min (typ. 16 V) | 24 V NAC | V_EOL = 20.4 V - I x R/m x 2L  (20.4 V = battery end voltage) | Manufacturer + NFPA 72 Ch.10 | Aramco: SAES-B-014 / project SOW governs where stricter | Regulated/boosted NAC PSUs per listing | Practice |
| FA-20 | Loop loading spare | Design <= 80% of loop device & current capacity | SLC / NAC circuits | Spare = 1 - used/max >= 20% | Project spec / practice | Aramco: SAES-B-014 / project SOW governs where stricter | Client spec may require 25% | Practice |
| FA-21 | Circuit survivability | Level 2 or 3 pathways for EVACS in partial-evac/high-rise | Relocation/partial evacuation | — | NFPA 72 §24.3.14 / Ch.12 | SBC 801 §907 | Fully sprinklered + AHJ acceptance | Code - verify |
| FA-22 | Elevator recall detection | Smoke detectors in lift lobbies, machine room, hoistway top (if sprinklered) | Elevators with Phase I recall | — | NFPA 72 §21.3; ASME A17.1 | SBC 801 §607 | Heat detectors where smoke unsuitable | Code |

## Plain-English explanations of the calculations

> **Authored by the supplier, not present in the workbook.** Explanatory
> only. Stored as `calculation.plain_english` with a provenance marker, and
> never the basis of a calculation or a quoted value — the `value_limit`
> and `calculation` fields above are the source of record. The wording may be
> edited freely; the values above may not.

| ID | In plain English |
|---|---|
| FA-01 | Each smoke detector covers a square about 9.1 m on each side. 9.1 x 9.1 = about 84 m2, so one detector protects roughly 84 m2 of flat ceiling. |
| FA-02 | Draw a circle around each detector with a radius of 0.7 times the spacing. With 9.1 m spacing that is 6.37 m. Every spot on the ceiling must fall inside one of these circles. |
| FA-03 | No detector may be further from a wall than half the spacing. Half of 9.1 m is 4.55 m. |
| FA-04 | Take the heat detector's listed spacing and multiply it by a reduction factor based on ceiling height. The higher the ceiling, the smaller the factor, so detectors must be closer together. Example: at 5 m ceiling height the factor is 0.71. |
| FA-06 | Compare the beam depth and the gap between beams against the ceiling height (H). Shallow beams (under 10% of H) are ignored. Deep beams far apart need a detector in each pocket. Deep beams close together mean you halve the spacing across the beams. |
| FA-07 | Across the direction of the beams, the heat detector spacing is cut to two-thirds of its listed value. |
| FA-08 | On sloped ceilings, measure spacing on a flat plan view (as if looking down from above) and add extra rows of detectors as needed. One row must be within 0.9 m of the peak. |
| FA-10 | Check the air handler's airflow. If it moves more than 944 litres per second (2,000 cfm), a duct smoke detector is needed on the supply side. |
| FA-11 | Put one call point at every exit, then add more until nobody on the floor has to walk more than 61 m to reach one. |
| FA-13 | Alarm sounders must be loud enough to hear over the background noise. Take whichever is higher: normal noise plus 15 dB, or the loudest sustained noise (lasting 60 seconds or more) plus 5 dB. |
| FA-16 | Look up the room size in the table and pick the strobe brightness (candela) for it. If the room falls between two sizes, use the bigger size's rating. |
| FA-17 | Take the corridor length, subtract the 9.2 m covered by the two end strobes, divide the rest by 30.5 m, round up, and add 1. That gives the number of strobes. |
| FA-18 | Battery size = (standby current x 24 hours) + (alarm current x alarm time), then add 20% extra as a safety margin. |
| FA-19 | The voltage at the last device = battery end voltage (20.4 V) minus the voltage lost in the wire. Wire loss = current x wire resistance x the total wire length there and back (2 x one-way length). |
| FA-20 | Spare capacity = 1 minus (what is used / the maximum allowed). It must be at least 20%, meaning the loop is loaded no more than 80%. |

## Relationship to rules already encoded

| This rule | Existing rule | Relationship | Note |
|---|---|---|---|
| FA-04 | ELV-B-02 | **supersedes** | ELV-B-02 carried a single recalled multiplier (roughly 0.7x at a 20 ft ceiling). FA-04 gives the full NFPA 72 Table 17.6.3.5.1 height-factor ladder from 0.91 down to 0.34. FA-04 is the better rule; ELV-B-02 should be superseded rather than kept alongside it. |
| FA-02 | ELV-B-01 | **refines** | Adds the 0.7S coverage-radius rule (6.37 m at S = 9.1 m) that governs irregular rooms, which flat spacing alone does not cover. |
| FA-06 | ELV-B-04 | **refines** | ELV-B-04 said only to redo spacing where beams and joists change coverage. FA-06 and FA-07 give the actual beam-depth and pocket-width tests. |
