# CCTV - SPT Engineering Rules Library

**Source:** Engineering Rules Library - ELV / ICT / Fire (SPT Pre-Sales, compiled
29 Sep 2026), `Engineering_Rules_Library.xlsx`. See
[the source record](../../standards-references/spt-engineering-rules-library/README.md) for the basis legend, the precedence
order, the library's stated limitations, and how these rules relate to the 57 already
encoded from the earlier documents.

**System:** `cctv` · **Rules:** 12 (Code 5, Code - verify 2, Practice 5)

> **Basis is not confidence.** `Code` and `Code - verify` are both encoded with
> `confidence = code`; the difference is that `Code - verify` needs its clause, edition
> or value checked before it reaches a submittal, which is recorded in
> `verification_note` and raised as `critical_review` rather than `error`. `Practice`
> is encoded as `confidence = spec` and cannot become scope on its own (ELV-X-06).

| ID | Requirement | Value / limit | Condition | Calculation | Source | Saudi / client overlay | Exception | Basis |
|---|---|---|---|---|---|---|---|---|
| CC-01 | Pixel density - DORI | Detect 25 px/m; Observe 62.5; Recognise 125; Identify 250 | Target at max design distance | Scene width W = 2 d tan(HFOV/2); PPM = H_res / W | IEC 62676-4 | HCIS SEC directives / Aramco security SAES - verify required class per zone | Thermal/analytics cameras use vendor detection criteria | Code |
| CC-02 | Required horizontal resolution | H_res >= PPM_req x W | Per camera view | H_res = PPM x 2 d tan(HFOV/2) | IEC 62676-4 | Project SOW | Wide dynamic range/night reduces effective PPM - add margin | Code |
| CC-03 | Max distance for target PPM | d_max = H_res / (PPM x 2 tan(HFOV/2)) | Fixed lens | e.g., 2688 px, 90 deg HFOV, 250 px/m -> 5.4 m | IEC 62676-4 (derived) | — | Varifocal: compute at chosen focal length | Code |
| CC-04 | Storage | Recording retention per spec | Continuous/motion recording | TB = sum(Mbps) x 3600 x h/day x days / 8 / 10^6 x (1+overhead) | Practice (vendor calculators) | HCIS / project spec retention (commonly 30-90 days) - verify | Event-only recording: apply duty-cycle factor | Practice |
| CC-05 | Storage redundancy | RAID 5/6 + >= 1 hot spare; + 20% free space | NVR/VMS storage | Usable = raw x (n-k)/n | Practice | Client spec | Edge (SD) recording as failover | Practice |
| CC-06 | Network bandwidth | Link utilisation <= 70% | Camera uplinks / NVR NICs | BW = sum stream Mbps (main + sub + live view) | Practice | — | Multicast live view reduces load | Practice |
| CC-07 | PoE power per camera | Match camera class (af 15.4 W / at 30 W / bt 60-90 W) | PTZ with heater/IR usually >= at/bt | Switch budget >= sum P_class x 1.2 | IEEE 802.3af/at/bt | — | External PSU for >90 W (heaters, wipers) | Code |
| CC-08 | Copper link length | <= 100 m channel | Cat6/6A to camera | Beyond -> fibre + media converter / extender | ANSI/TIA-568 | SAES-T-916 (Aramco) - verify | Listed PoE extenders | Code |
| CC-09 | Face ID camera geometry | Vertical angle to face <= 15 deg; horizontal <= 30 deg off-axis | Identification views (entries) | theta = atan((h_cam - 1.6)/d) | IEC 62676-4 guidance / practice | HCIS / project SOW | Stereo/overhead analytics | Practice |
| CC-10 | Outdoor enclosure | IP66/IP67, IK10; rated to site ambient + solar gain | Outdoor, KSA climate | — | IEC 60529 / IEC 62262 | Aramco: design ambient per SAES/SOW (hazardous areas: Ex certified) | Indoor conditioned spaces | Code - verify |
| CC-11 | Coverage overlap | Adjacent perimeter views overlap; no blind zones at fence line | Perimeter security | Overlap = FOV_n intersect FOV_n+1 > 0 at detection distance | Practice | HCIS perimeter directives - verify | Radar/PIDS-cued PTZ designs | Practice |
| CC-12 | Time sync & cyber hygiene | NTP sync; unique credentials; security VLAN; firmware management | All IP cameras/NVRs | — | IEC 62676-1 / vendor hardening | NCA ECC-2:2024 (and OTCC-1 for OT sites) | Air-gapped systems still require local NTP | Code - verify |

## Plain-English explanations of the calculations

> **Authored by the supplier, not present in the workbook.** Explanatory
> only. Stored as `calculation.plain_english` with a provenance marker, and
> never the basis of a calculation or a quoted value — the `value_limit`
> and `calculation` fields above are the source of record. The wording may be
> edited freely; the values above may not.

| ID | In plain English |
|---|---|
| CC-01 | Work out how wide the camera's view is at the target distance, then divide the camera's horizontal pixels by that width. The result (pixels per metre) tells you whether you can detect, observe, recognise or identify a person. |
| CC-02 | To find the camera resolution you need: multiply the required pixels per metre by the width of the scene at the target distance. |
| CC-03 | Rearranges the formula to find the furthest distance at which a camera still gives enough detail. Example: a 2688-pixel camera with a 90 degree view needs the person within 5.4 m to identify them (250 px/m). |
| CC-04 | Add up all camera bitrates (Mbps), convert to data per second, multiply by the seconds recorded each day and the number of days kept. Divide by 8 to turn bits into bytes and by 1,000,000 to get terabytes, then add extra for RAID and free space. |
| CC-05 | Some disks in a RAID array hold backup (parity) data, not recordings. Usable storage = raw storage x (total disks - parity disks) / total disks. |
| CC-06 | Network bandwidth needed = the sum of every video stream: main recording stream, secondary stream and any live viewing. |
| CC-07 | The switch must supply enough power for all cameras. Add up each camera's PoE class power and add 20% extra. |
| CC-08 | If a copper cable run would go beyond 100 m, switch to fibre with a media converter, or use an extender. |
| CC-09 | Work out the camera's downward angle to a face: the height difference between the camera and a face (1.6 m) divided by the distance, then take the angle. It must be 15 degrees or less to identify faces. |
| CC-11 | Check that each camera's field of view overlaps the next one at the detection distance, so there are no gaps along the perimeter. |

## Relationship to rules already encoded

| This rule | Existing rule | Relationship | Note |
|---|---|---|---|
| CC-01 | ELV-C-07 | **resolves** | ELV-C-07 named the DORI tiers but carried no numbers. CC-01 supplies 25 / 62.5 / 125 / 250 px/m and CC-02 and CC-03 give the scene-width and max-distance formulae. |
| CC-04 | KSA-CCTV-04 | **conflicts** | CC-04 records retention as commonly 30-90 days per HCIS or project spec, tagged Practice. KSA-CCTV-04 records 90 days as a statutory minimum under the Law of the Use of Security Surveillance Cameras. For a Saudi site the statutory floor governs and 30 days is not available. Both remain unconfirmed against their primary sources. |
| CC-07 | ELV-C-02 | **agrees** | Both size PoE from the switch budget with a 20 percent margin. CC-07 and NW-01 add the class wattages at the PSE and the power available at the PD. |
| CC-08 | ELV-A-01 | **agrees** | Both cap the copper channel at 100 m. |
