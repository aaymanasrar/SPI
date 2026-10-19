# By location — what goes where (Saudi projects)

44 rules, indexed by **where you are**, not by system. Use this when the
question is *"we are designing a hospital ward / a perimeter fence / a gatehouse —
what goes in it?"* For a limit on a specific system, use the system packs instead.

Everything here is a **Saudi client or authority standard** (Aramco SAES, HCIS SEC/SAF,
MOH) or an SBC threshold. It applies on a Saudi project and nowhere else. Confirm the
standard is called out by the project SOW before pricing from it.

See [`README.md`](README.md) for the output format.

---

## Any

### Kitchens, generator & mechanical rooms — Fire alarm
`LP-44`
- **Install:** Heat detectors (rate-of-rise or fixed) where smoke detectors would false-alarm; flame detectors at high-hazard points
- **Key numbers:** Spacing per listing x height factor
- **Why:** Nuisance-alarm avoidance
- **Basis:** CODE · NFPA 72 Ch.17; MOH Private Hospitals Design Guide (Scribd copy) 5-2-38 to 5-2-40
- **Scope:** binds on its own
- **Unverified:** summary, keyword extract, or an old public edition. Verify against the current controlled copy before citing.

## Any (lead-acid)

### Battery room — Ventilation / UPS
`LP-16`
- **Install:** Mechanical ventilation sized for hydrogen dilution; conditioned room
- **Key numbers:** Q = 0.05 x n x Igas x Crt x 10^-3 m3/h
- **Why:** H2 off-gassing; KSA ambient shortens VRLA life
- **Basis:** CODE · IEC 62485-2 (see rule UP-05)
- **Scope:** binds on its own
- **Unverified:** summary, keyword extract, or an old public edition. Verify against the current controlled copy before citing.

## Aramco

### Battery room — Fire alarm
`LP-15`
- **Install:** Addressable spot smoke detection
- **Why:** Battery thermal events
- **Basis:** LOCAL · SAES-B-014 (2004 public copy) 5.14 (verify current edition)
- **Scope:** applies only in SA; cite the standard before it becomes a quantity
- **Unverified:** summary, keyword extract, or an old public edition. Verify against the current controlled copy before citing.

### Outside plant fibre — Fibre OSP
`LP-26`
- **Install:** SM fibre in duct (4 in with subducts) or direct-buried; fusion splicing
- **Key numbers:** <=0.5 dB/km @1310, <=0.3 @1550; fusion splice avg 0.05 / max 0.1 dB; bend 10x/20x OD
- **Why:** Long inter-building runs
- **Basis:** LOCAL · SAES-T-624 (2009)
- **Scope:** applies only in SA; cite the standard before it becomes a quantity
- **Unverified:** summary, keyword extract, or an old public edition. Verify against the current controlled copy before citing.

### Remote sites (wells, bulk plants, AFOs) — CCTV / network
`LP-24`
- **Install:** Camera access switch at camera site; leased IP-VPN link
- **Key numbers:** Camera traffic <=10% of leased link, with >=20% free before adding cameras
- **Calculator:** `calc_engine.network_bandwidth()`
- **Why:** No local building; bandwidth is scarce
- **Basis:** LOCAL · SAES-T-555 (2012 public copy) 6.1.8, 6.1.10
- **Scope:** applies only in SA; cite the standard before it becomes a quantity

### Telecom room — Environmental alarm
`LP-14`
- **Install:** High-temperature alarm relayed to Network Operations Control Center
- **Why:** HVAC failure is the main risk to telecom equipment
- **Basis:** LOCAL · SAES-B-014 (2004 public copy) 7.7 (verify current edition)
- **Scope:** applies only in SA; cite the standard before it becomes a quantity
- **Unverified:** summary, keyword extract, or an old public edition. Verify against the current controlled copy before citing.

## Aramco buildings

### Building telecom rooms — Structured cabling
`LP-25`
- **Install:** RCDD-qualified design; star topology; TC per 1,000 m2; no false ceiling; 1-h rated walls; testing per SAES-T-634
- **Key numbers:** Horizontal <=90 m; TC <=500 m2 area 3.0x2.2 m; 800-1,000 m2 3.0x3.4 m; ER 18-24 C
- **Why:** Standardised, maintainable cabling plant
- **Basis:** LOCAL · SAES-T-916 (2003 public copy - verify current)
- **Scope:** applies only in SA; cite the standard before it becomes a quantity
- **Unverified:** summary, keyword extract, or an old public edition. Verify against the current controlled copy before citing.

## Aramco community (e.g. clinic parking)

### Parking / outdoor lots — CCTV
`LP-43`
- **Install:** Pole-mounted outdoor IP cameras (IP66, sunshield), PoE where <=100 m else fibre; lighting check >=5 lux or IR/day-night
- **Key numbers:** >=5 lux for colour image
- **Why:** Vehicle crime, incident evidence
- **Basis:** LOCAL · SAES-T-555 (2012 public copy) 5.3.5, 10.5
- **Scope:** applies only in SA; cite the standard before it becomes a quantity

## Aramco in-plant

### Control room / PIB / SIH / comms building — Fire alarm
`LP-11`
- **Install:** Mandatory addressable FA; spot smoke detectors in room, under raised floor and above suspended ceiling; local panel at building entrance; common alarm to plant control room via DCS or hardwired annunciator
- **Key numbers:** Designer: registered engineer with 5 yrs FA experience
- **Why:** Electronics-dense, continuously critical buildings; early smoke detection before damage
- **Basis:** LOCAL · SAES-B-014 (2004 public copy) 7.1-7.5 (verify current edition)
- **Scope:** applies only in SA; cite the standard before it becomes a quantity
- **Unverified:** summary, keyword extract, or an old public edition. Verify against the current controlled copy before citing.

### Floor-standing I/O, ESD, UPS cabinets — Fire alarm
`LP-12`
- **Install:** Air-sampling (high-sensitivity) or point smoke detection with adjustable set points
- **Why:** Very early warning inside cabinets where fires start small
- **Basis:** LOCAL · SAES-B-014 (2004 public copy) 7.6 (verify current edition)
- **Scope:** applies only in SA; cite the standard before it becomes a quantity
- **Unverified:** summary, keyword extract, or an old public edition. Verify against the current controlled copy before citing.

## Aramco plant (non-security CCTV)

### Process / plant operations area — CCTV
`LP-21`
- **Install:** IP CCTV for operations (not IDAS); separate VLAN on PAN with control traffic prioritised; VMS client-server; motion/scheduled recording preferred
- **Key numbers:** Latency <200 ms; VMS local recording >=72 h, archive (DAS/NAS) beyond 72 h; corporate uplink capped 100 Mbps/15%
- **Calculator:** `calc_engine.video_storage()`
- **Why:** Operational visibility without loading the process control network
- **Basis:** LOCAL · SAES-T-555 (2012 public copy) 5-9 (older edition - verify)
- **Scope:** applies only in SA; cite the standard before it becomes a quantity

## Aramco, >100 m2

### Electrical substation — Fire alarm
`LP-13`
- **Install:** Projected-beam smoke detection, addressable
- **Key numbers:** Applies to substations >100 m2
- **Why:** Large open volumes with high ceilings; beams cover long spans cheaply
- **Basis:** LOCAL · SAES-B-014 (2004 public copy) 7.8 (verify current edition)
- **Scope:** applies only in SA; cite the standard before it becomes a quantity
- **Unverified:** summary, keyword extract, or an old public edition. Verify against the current controlled copy before citing.

## HCIS light & non-industrial

### Electrical/electronic rooms & cable areas — Fire alarm
`LP-27`
- **Install:** Smoke detection & alarm in buildings/rooms/enclosures with electrical-electronic equipment and cabling; manual pull boxes in occupied buildings per Saudi Building Code
- **Why:** Cable/electronics fires are the dominant building hazard
- **Basis:** LOCAL · HCIS SAF (Light & Non-Industrial, 2017)
- **Scope:** applies only in SA; cite the standard before it becomes a quantity
- **Unverified:** summary, keyword extract, or an old public edition. Verify against the current controlled copy before citing.

## Healthcare

### Hospital - fire exits, medication/utility rooms, server, imaging, pharmacy, isolation, dept entrances — Access control
`LP-33`
- **Install:** Card access; electrically locked doors on escape routes interlocked with fire alarm
- **Why:** Restrict drugs/equipment; egress must release on alarm
- **Basis:** LOCAL · iHFG Part E
- **Scope:** applies only in SA; cite the standard before it becomes a quantity
- **Unverified:** summary, keyword extract, or an old public edition. Verify against the current controlled copy before citing.

### Hospital - pharmacy, medication rooms, labs, ED, loading dock, lift lobbies, fire stairs, CSSD, dept entrances — CCTV
`LP-32`
- **Install:** Internal + external CCTV at listed high-risk / high-traffic points; privacy respected in patient areas
- **Why:** Drug security, violence risk in ED, goods receipt, egress monitoring
- **Basis:** LOCAL · iHFG Part E; MOH Private Hospitals Design Guide (Scribd copy) 4-6-16
- **Scope:** applies only in SA; cite the standard before it becomes a quantity
- **Unverified:** summary, keyword extract, or an old public edition. Verify against the current controlled copy before citing.

## Industrial

### Gatehouse interior — Lighting / displays
`LP-08`
- **Install:** Dimmable interior lighting; bilingual (Arabic/English) status & alarm displays; alarm printer
- **Key numbers:** 300 lux at counter
- **Why:** Operators must read screens and see outside at night
- **Basis:** LOCAL · SAES-O-204 4.4; HCIS SEC-05 v2.0 (2017) 5.3.7
- **Scope:** applies only in SA; cite the standard before it becomes a quantity

### Plant control room — Access control
`LP-10`
- **Install:** Standalone scaled-down ACS; card readers + camera at every entry side; not required to link to company-wide ACS
- **Key numbers:** 2 or more card readers on entry side (SEC-05); UPS + generator backup
- **Why:** Control room is a vital asset inside an already-controlled restricted area
- **Basis:** LOCAL · SAES-O-205 (22-Mar-2023) 6.7; HCIS SEC-05 v2.0 (2017) 5.9
- **Scope:** applies only in SA; cite the standard before it becomes a quantity

### Security equipment room — Room design
`LP-17`
- **Install:** Redundant split/central AC (no window units), cabinet AC where in cabinets; transformers NOT in room (separate room with UPS); locked with entry control; CCTV inside room; no plumbing in walls/ceiling
- **Key numbers:** HVAC per SAES-K-003 / SAES-T-916
- **Why:** Protect core security servers/NVRs from heat, water and insider access
- **Basis:** LOCAL · SAES-O-205 (22-Mar-2023) 5.13
- **Scope:** applies only in SA; cite the standard before it becomes a quantity

### Security systems - all core equipment — Servers / network / storage
`LP-18`
- **Install:** High-availability (redundant units, hot-swap or virtualised); no single point of failure except field sensors; encrypted external interfaces with ICD/API; NTP; tamper alarms; outdoor cables in steel conduit
- **Key numbers:** Availability >=99.95%; spare 20% CPU/RAM, 20% ports, 20% bandwidth, 50% disk; full backup every 30 days + daily incremental, off-site
- **Why:** Security systems must survive single failures and cyber attack
- **Basis:** LOCAL · SAES-O-205 (22-Mar-2023) 5.1-5.10; HCIS SEC-05 v2.0 (2017) 5.2
- **Scope:** applies only in SA; cite the standard before it becomes a quantity

### Security systems - power — UPS
`LP-19`
- **Install:** All security systems on UPS backed by emergency generator; power per SAES-O-207 / HCIS SEC-07
- **Key numbers:** Autonomy value: see SAES-O-207/SEC-07 (NOT RETRIEVED - verify)
- **Calculator:** `calc_engine.dc_battery_bank()`
- **Why:** Security must keep running through utility loss
- **Basis:** LOCAL · HCIS SEC-05 v2.0 (2017) 5.2.10; SAES-O-205 (22-Mar-2023) 5.8
- **Scope:** applies only in SA; cite the standard before it becomes a quantity

## Industrial (HCIS/Aramco)

### Security cameras - all — CCTV spec
`LP-20`
- **Install:** IP cameras direct to LAN; optical colour low-light, thermal in selected locations; fixed for surveillance/analytics, PTZ for assessment; video analytics on fixed cameras; video-loss alarm; geospatial coordinates
- **Key numbers:** Optical 1080p @30 fps (may drop to 720p/7.5 fps when not in alarm); thermal LWIR >=320x240 @30 fps; IP66; VASS retention fixed 90 d / assessment 30 d / alarm events 90 d; recordings stored locally and at Dhahran (Aramco)
- **Calculator:** `calc_engine.video_storage()`
- **Why:** Consistent image quality for assessment and evidence
- **Basis:** LOCAL · SAES-O-205 (22-Mar-2023) 5.14, 6.3; HCIS SEC-05 v2.0 (2017) 5.7-5.8
- **Scope:** applies only in SA; cite the standard before it becomes a quantity

## Industrial, Class 1-3

### Security Control Center / 911 EC — Integrated security + support systems
`LP-09`
- **Install:** Single command & control platform (SACS, ALPRS, IDAS, IDMS, VASS, radio, dispatch); video wall; local ACS on SCC doors; fire detection per SAF-04; dedicated UPS + generator
- **Key numbers:** 24/7; voice recording 12 months; layout per ISO 11064; displays 1080p or better
- **Why:** One operator view for time-critical response; SCC is the ERP hub
- **Basis:** LOCAL · SAES-O-205 (22-Mar-2023) 6.8-6.9
- **Scope:** applies only in SA; cite the standard before it becomes a quantity

## Industrial, FSC Class 1-2

### Perimeter fence line — Intrusion + CCTV (IDAS)
`LP-01`
- **Install:** 2 or more independent sensor types (one volumetric, e.g. bi-static microwave or thermal/optical camera with analytics); fixed optical cameras along entire perimeter + PTZ assessment cameras that auto-slew to alarm zone; GIS map display
- **Key numbers:** Alarm zone <=150 m; localisation +/-75 m; Pd >=95%; nuisance & false <=1/zone/30 days; pre/post alarm 5-20 s; retention 60 days at 1080p30
- **Why:** Perimeter is the first detection layer; fixed cameras give continuous surveillance, PTZ gives operator assessment; two sensor types cut single-technology defeat
- **Basis:** LOCAL · SAES-O-205 (22-Mar-2023) 6.1; HCIS SEC-05 v2.0 (2017) 5.5
- **Scope:** applies only in SA; cite the standard before it becomes a quantity

## Industrial, FSC Class 1-3

### Main gate - pedestrian & vehicle — Access control (SACS)
`LP-06`
- **Install:** Turnstiles (pedestrian) and drop arms / anti-vehicle barriers (vehicles) as Single Entry Devices; PIV card + 4-digit or longer PIN, or PIV + biometric; bi-directional turnstile gets readers both sides; duress code; electro-mechanical emergency release
- **Key numbers:** Alarm response <0.5 s; data upload <=10 min; central data 36 months; PIN change every 6 months; one reader per SED; 2 or more controllers alternating readers
- **Why:** Cannot be bypassed; prevents tailgating; anti-passback keeps on-site muster list accurate
- **Basis:** LOCAL · SAES-O-205 (22-Mar-2023) 6.2; HCIS SEC-05 v2.0 (2017) 5.3
- **Scope:** applies only in SA; cite the standard before it becomes a quantity

### Main gate - pedestrian & vehicle — CCTV at gate
`LP-07`
**DO NOT USE — conflicts with KSA-CCTV-04.** LP-07 and the QuickRef set retention by CAMERA ROLE under Aramco/HCIS: gate surveillance 90 d, gate assessment (PTZ) 30 d, IDAS perimeter 60 d, VASS assessment 30 d. KSA-CCTV-04 records a 90-day statutory floor under the Law of the Use of Security Surveillance Cameras. The 30 d and 60 d figures sit BELOW that floor. If the premises fall under the camera law, the statutory minimum governs and a client standard cannot reduce it. Resolve per project: confirm whether the site is in scope of the law, and confirm the 90-day figure itself, which is still secondary-sourced.
- **Install:** Per gate: 1 fixed entry + 1 fixed exit (surveillance), 1 PTZ entry + 1 PTZ exit (assessment), 1 fixed user camera per card reader (2 s clip on swipe)
- **Key numbers:** User face recognisable for height 1.3-2.2 m; retention: gate surveillance 90 d, assessment 30 d, user 90 d
- **Calculator:** `calc_engine.video_storage()`
- **Why:** Records who used which credential and the general gate scene for investigation
- **Basis:** LOCAL · HCIS SEC-05 v2.0 (2017) 5.3.9-5.3.10; SAES-O-205 (22-Mar-2023) 6.2.6-6.2.7
- **Scope:** applies only in SA; cite the standard before it becomes a quantity

### Main gate - vehicle lanes — ALPR
`LP-05`
- **Install:** ALPR camera + co-located IR/visible illuminator per entry lane; IP65 lane display; siren for PNG plate; gatehouse workstation
- **Key numbers:** Camera <=50 m before gatehouse; shutter 1/1000 s; reads all GCC plates (Arabic/English + colour); new plate formats updated <=15 days
- **Why:** Validate vehicle against central list before it reaches the gatehouse
- **Basis:** LOCAL · SAES-O-205 (22-Mar-2023) 6.5; HCIS SEC-05 v2.0 (2017) 5.4
- **Scope:** applies only in SA; cite the standard before it becomes a quantity

## Industrial, FSC Class 3-4

### Perimeter fence line — CCTV (VASS)
`LP-02`
- **Install:** VASS cameras at perimeter/external contiguous areas as designated by Security Risk Assessment; IDAS not mandatory
- **Key numbers:** Class 4 coverage per SRA only
- **Why:** Lower consequence class - coverage scoped by SRA rather than full IDAS
- **Basis:** LOCAL · SAES-O-205 (22-Mar-2023) 6.3, 7
- **Scope:** applies only in SA; cite the standard before it becomes a quantity

## Industrial, all classes

### Perimeter fence line — Security lighting
`LP-03`
- **Install:** Fence-line poles (~5 m at ~20 m spacing) and area lighting on 10-30 m poles; generator-backed; auto on
- **Key numbers:** Area avg 5 lux; switch-on at 1.6x design lux or 15 lux; lamp replacement <=72 h
- **Why:** Optical cameras need light for colour assessment; lighting must not interfere with intrusion sensors
- **Basis:** LOCAL · SAES-O-204 (2012) 4; HCIS SEC-04
- **Scope:** applies only in SA; cite the standard before it becomes a quantity
- **Unverified:** summary, keyword extract, or an old public edition. Verify against the current controlled copy before citing.

## KSA environment

### Outdoor / coastal installations — All field devices
`LP-23`
- **Install:** Sealed housings (IP66 / NEMA 4X stainless in corrosive); sunshields; rated for extreme heat and sandstorm dust; salt-spray protection near coast
- **Key numbers:** Design max: indoor AC 35 C, outdoor sheltered 70 C, unsheltered 80 C (+15 C self-heating rule); dust up to 500 mg/m3; coastal = within 1 km of Gulf / 3 km of Red Sea
- **Why:** Gulf-region heat, dust and salt destroy under-rated equipment
- **Basis:** LOCAL · SAES-T-555 (2012 public copy) App. A (older edition - verify vs SAES-O-201)
- **Scope:** applies only in SA; cite the standard before it becomes a quantity

## MOH

### Hospital - ICU / OR / critical care — UPS / power
`LP-30`
- **Install:** Dedicated UPS for operations, ICU and critical care; outlets on three colour-coded sources (normal / emergency / UPS)
- **Key numbers:** Generator for >=3 h; loads designed at 120%
- **Calculator:** `calc_engine.dc_battery_bank()`
- **Why:** Life-support continuity
- **Basis:** LOCAL · MOH Private Hospitals Design Guide (Scribd copy) 2-6-7 to 2-6-19
- **Scope:** applies only in SA; cite the standard before it becomes a quantity
- **Unverified:** summary, keyword extract, or an old public edition. Verify against the current controlled copy before citing.

### Hospital - general — Other light current
`LP-34`
- **Install:** Master clock, MATV/satellite, telephone/IP data, intercom (incl. lift guard intercom), gas detection interfaced to FA, mosque audio system
- **Why:** Standard MOH light-current package
- **Basis:** LOCAL · MOH Private Hospitals Design Guide (Scribd copy) 4-6-7 to 4-6-19, 5-2-37
- **Scope:** applies only in SA; cite the standard before it becomes a quantity
- **Unverified:** summary, keyword extract, or an old public edition. Verify against the current controlled copy before citing.

### Hospital - light current systems — UPS
`LP-31`
- **Install:** UPS feeding light-current systems (IT, CCTV, fire alarm, etc.)
- **Key numbers:** >=30 min autonomy
- **Calculator:** `calc_engine.dc_battery_bank()`
- **Why:** Keep communications and life-safety signalling up during transfer
- **Basis:** LOCAL · MOH Private Hospitals Design Guide (Scribd copy) 2-6-12
- **Scope:** applies only in SA; cite the standard before it becomes a quantity
- **Unverified:** summary, keyword extract, or an old public edition. Verify against the current controlled copy before citing.

### Hospital - patient rooms & wards — Nurse call
`LP-29`
- **Install:** Integrated nurse call with over-door (corridor) flashers, cancel buttons at door and bed; bed-head unit with nurse call button, telephone and data
- **Why:** Staff must locate the calling patient quickly
- **Basis:** LOCAL · MOH Private Hospitals Design Guide (Scribd copy) 3-3-1-21, 2-6-22; iHFG Part E
- **Scope:** applies only in SA; cite the standard before it becomes a quantity
- **Unverified:** summary, keyword extract, or an old public edition. Verify against the current controlled copy before citing.

## MOH / private hospital

### Hospital - whole building — Fire alarm + interfaces
`LP-28`
- **Install:** NFPA 72 system; duct smoke detectors tied to FACP; FACP interfaces to lifts, AC, BMS, PA and magnetic door holders; external fire exits release on alarm; PA used for voice evacuation
- **Why:** Defend-in-place occupancy - compartmentation and controlled evacuation
- **Basis:** LOCAL · MOH Private Hospitals Design Guide (Scribd copy) 4-6-11 to 4-6-14, 8-1-13
- **Scope:** applies only in SA; cite the standard before it becomes a quantity
- **Unverified:** summary, keyword extract, or an old public edition. Verify against the current controlled copy before citing.

## Ministry of Islamic Affairs / Modon projects

### Mosque — Public address / prayer call
`LP-36`
- **Install:** Separate prayer-call (external horn/column speakers on minaret) and internal prayer-hall PA; zoned; not a listed voice-evac system unless designed as one
- **Key numbers:** Coverage/SPL per project spec
- **Why:** Adhan coverage outside + intelligible speech inside
- **Basis:** SPEC · Project practice (verify against project SOW)
- **Scope:** NOT scope on its own — needs a drawing or SOW clause
- **Unverified:** summary, keyword extract, or an old public edition. Verify against the current controlled copy before citing.

## Oil & gas

### Hazardous (classified) area — CCTV / devices
`LP-22`
- **Install:** Ex-certified cameras/housings per area classification drawing (Class I / Zone / Group)
- **Key numbers:** Per SAES-B-068 area classification
- **Why:** Ignition-source control
- **Basis:** LOCAL · SAES-T-555 (2012 public copy) 10.1
- **Scope:** applies only in SA; cite the standard before it becomes a quantity

## Remote / open-area or marine-side facilities

### Area outside perimeter — Long-range surveillance
`LP-04`
- **Install:** Radar (open areas) or thermal sensors cueing long-range PTZ camera; radar blanked toward protected facility
- **Key numbers:** LRS camera >=2 km (SEC-05); radar human detection >=3 km (SAES-O-205)
- **Why:** Detect threats before they reach the fence; range tied to response time
- **Basis:** LOCAL · SAES-O-205 (22-Mar-2023) 6.4; HCIS SEC-05 v2.0 (2017) 5.7.6
- **Scope:** applies only in SA; cite the standard before it becomes a quantity

## SBC

### High-rise building — Fire alarm / voice
`LP-42`
- **Install:** Automatic smoke detection + emergency voice/alarm communication; fire command centre; firefighter phones
- **Key numbers:** Occupied floor >23 m (75 ft) above fire-department access
- **Why:** Phased evacuation of tall buildings
- **Basis:** CODE · SBC 801 907.2.13 (IFC 2018 basis - verify)
- **Scope:** binds on its own
- **Unverified:** summary, keyword extract, or an old public edition. Verify against the current controlled copy before citing.

## SBC occupancy

### Apartments (Group R-2) — Fire alarm
`LP-41`
- **Install:** Manual FA where 3 or more stories or >16 dwelling units; smoke alarms in units
- **Key numbers:** 3 stories / 16 units
- **Why:** Sleeping occupants in multi-unit buildings
- **Basis:** CODE · SBC 801 907.2.9 (IFC 2018 basis - verify)
- **Scope:** binds on its own
- **Unverified:** summary, keyword extract, or an old public edition. Verify against the current controlled copy before citing.

### Hotel (Group R-1) — Fire alarm
`LP-40`
- **Install:** Manual FA + automatic smoke detection in interior corridors; smoke alarms in guest rooms; low-frequency 520 Hz sounders in sleeping rooms
- **Key numbers:** 75 dBA at pillow or 15 dB > ambient
- **Why:** Sleeping occupants
- **Basis:** CODE · SBC 801 907.2.8; NFPA 72 18.4.6
- **Scope:** binds on its own
- **Unverified:** summary, keyword extract, or an old public edition. Verify against the current controlled copy before citing.

### Mall / retail (Group M) — Fire alarm / voice
`LP-39`
- **Install:** Manual fire alarm for occupant load >=500 or >100 above/below exit discharge; EVACS in covered malls above size threshold
- **Key numbers:** 500 / 100 occupants
- **Why:** Large transient public
- **Basis:** CODE · SBC 801 907.2.7, 907.2.20 (IFC 2018 basis - verify)
- **Scope:** binds on its own
- **Unverified:** summary, keyword extract, or an old public edition. Verify against the current controlled copy before citing.

### Mosque (Group A-3) — Fire alarm
`LP-35`
- **Install:** Manual fire alarm system when occupant load >=300 (or >100 above/below exit discharge); automatic detection per specific rooms (electrical, AHU)
- **Key numbers:** Threshold 300 occupants
- **Why:** Assembly occupancy thresholds
- **Basis:** CODE · SBC 801 907.2.1 (IFC 2018 basis - verify Saudi amendment)
- **Scope:** binds on its own
- **Unverified:** summary, keyword extract, or an old public edition. Verify against the current controlled copy before citing.

### Office building (Group B) — Fire alarm
`LP-37`
- **Install:** Manual fire alarm when total occupant load >=500 or >100 above/below exit discharge; automatic sprinklers usually provide detection/notification
- **Key numbers:** 500 / 100 occupants
- **Why:** Business occupancy thresholds
- **Basis:** CODE · SBC 801 907.2.2 (IFC 2018 basis - verify)
- **Scope:** binds on its own
- **Unverified:** summary, keyword extract, or an old public edition. Verify against the current controlled copy before citing.

### School (Group E) — Fire alarm / voice
`LP-38`
- **Install:** Manual fire alarm for occupant load >=50; emergency voice/alarm communication when >100
- **Key numbers:** 50 / 100 occupants
- **Why:** Child occupants need controlled, intelligible evacuation
- **Basis:** CODE · SBC 801 907.2.3 (IFC 2018 basis - verify)
- **Scope:** binds on its own
- **Unverified:** summary, keyword extract, or an old public edition. Verify against the current controlled copy before citing.
