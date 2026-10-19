# CCTV — rule pack

33 rules. Generated from the database; see
[`../rule-packs/README.md`](README.md) for how to use these and what to output.

**3 rule(s) in this pack are marked DO NOT USE.** They are contradicted by another rule and the conflict is unresolved. Skip them.

---
### C-02 — PoE budget sized from the switch down
- **Limit:** headroom 20 %; method sum_port_maximum_power_then_compare_switch_total_budget; headroom confidence spec; classes ["802.3af", "802.3at", "802.3bt"]
- **When:** device.powered_by eq "poe"
- **Calculator:** `calc_engine.poe_budget()` — do not do this arithmetic yourself; call the module and quote its CalcResult.
- **Does not apply / exception:** Thermal PTZ heads and IR illuminators often need at or bt class. Do not assume af.; The 20 percent headroom is a design margin, not a code requirement.
- **Basis:** CODE · IEEE 802.3af/at/bt
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### C-03 — PoE bundle temperature rise and heat dissipation
- **Limit:** record certification_record in; checks ["bundle_temperature_rise", "switch_heat_dissipation", "enclosure_heat_dissipation"]; worst case ["bundled_runs", "conduit_runs"]
- **When:** pathway.carries_poe eq true
- **Calculator:** `calc_engine.poe_budget()` — do not do this arithmetic yourself; call the module and quote its CalcResult.
- **Does not apply / exception:** Add to the certification record when high-power devices are used.
- **Basis:** CODE · TIA TSB-184-A
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### CC-01 — Pixel density - DORI
- **Limit:** Detect 25 px/m; Observe 62.5; Recognise 125; Identify 250
- **When:** Target at max design distance
- **Calculation:** Scene width W = 2 d tan(HFOV/2); PPM = H_res / W
- **In plain English:** Work out how wide the camera's view is at the target distance, then divide the camera's horizontal pixels by that width. The result (pixels per metre) tells you whether you can detect, observe, recognise or identify a person.
- **Does not apply / exception:** Thermal/analytics cameras use vendor detection criteria
- **Basis:** CODE · IEC 62676-4 · KSA/client: HCIS SEC directives / Aramco security SAES - verify required class per zone
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### CC-02 — Required horizontal resolution
- **Limit:** H_res >= PPM_req x W
- **When:** Per camera view
- **Calculation:** H_res = PPM x 2 d tan(HFOV/2)
- **In plain English:** To find the camera resolution you need: multiply the required pixels per metre by the width of the scene at the target distance.
- **Does not apply / exception:** Wide dynamic range/night reduces effective PPM - add margin
- **Basis:** CODE · IEC 62676-4 · KSA/client: Project SOW
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### CC-03 — Max distance for target PPM
- **Limit:** d_max = H_res / (PPM x 2 tan(HFOV/2))
- **When:** Fixed lens
- **Calculation:** e.g., 2688 px, 90 deg HFOV, 250 px/m -> 5.4 m
- **In plain English:** Rearranges the formula to find the furthest distance at which a camera still gives enough detail. Example: a 2688-pixel camera with a 90 degree view needs the person within 5.4 m to identify them (250 px/m).
- **Does not apply / exception:** Varifocal: compute at chosen focal length
- **Basis:** CODE · IEC 62676-4 (derived)
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### CC-07 — PoE power per camera
- **Limit:** Match camera class (af 15.4 W / at 30 W / bt 60-90 W)
- **When:** PTZ with heater/IR usually >= at/bt
- **Calculation:** Switch budget >= sum P_class x 1.2
- **Calculator:** `calc_engine.poe_budget()` — do not do this arithmetic yourself; call the module and quote its CalcResult.
- **In plain English:** The switch must supply enough power for all cameras. Add up each camera's PoE class power and add 20% extra.
- **Does not apply / exception:** External PSU for >90 W (heaters, wipers)
- **Basis:** CODE · IEEE 802.3af/at/bt
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### CC-08 — Copper link length
- **Limit:** <= 100 m channel
- **When:** Cat6/6A to camera
- **Calculation:** Beyond -> fibre + media converter / extender
- **In plain English:** If a copper cable run would go beyond 100 m, switch to fibre with a media converter, or use an extender.
- **Does not apply / exception:** Listed PoE extenders
- **Basis:** CODE · ANSI/TIA-568 · KSA/client: SAES-T-916 (Aramco) - verify
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### CC-10 — Outdoor enclosure
- **Limit:** IP66/IP67, IK10; rated to site ambient + solar gain
- **When:** Outdoor, KSA climate
- **Does not apply / exception:** Indoor conditioned spaces
- **Basis:** CODE · IEC 60529 / IEC 62262 · KSA/client: Aramco: design ambient per SAES/SOW (hazardous areas: Ex certified)
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### CC-12 — Time sync & cyber hygiene
- **Limit:** NTP sync; unique credentials; security VLAN; firmware management
- **When:** All IP cameras/NVRs
- **Does not apply / exception:** Air-gapped systems still require local NTP
- **Basis:** CODE · IEC 62676-1 / vendor hardening · KSA/client: NCA ECC-2:2024 (and OTCC-1 for OT sites)
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### KSA-CCTV-01 — Prior Ministry of Interior approval before any camera work
- **Limit:** authority ministry_of_interior; is precondition to work yes; approval required before ["manufacture", "import", "sale", "installation", "operation", "maintenance"]
- **When:** site.country eq "SA"
- **Does not apply / exception:** Penalties: SAR 500 per non-compliant camera, SAR 1000 per improperly installed camera.; This is a precondition to starting work, not a handover document.
- **Basis:** LOCAL · Law of the Use of Security Surveillance Cameras (Royal Decree, 3 Oct 2022)
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity

### KSA-CCTV-02 — Mandatory installation premises classes
- **Limit:** open ended any_other_facility_the_ministry_deems_necessary; mandatory classes ["ministry", "public_institution", "power_plant", "desalination_plant", "oil_facility", "commercial_complex", "residential_building", "bank", "two_holy_mosques", "mosque", "entertainment_venue", "stadium", "hospital", "highway", "school", "fuel_station", "public_transport", "restaurant", "museum"]
- **When:** site.country eq "SA"
- **Does not apply / exception:** Broad enough that most SmartPage project types fall inside it. Confirm per project rather than assuming either way.
- **Basis:** LOCAL · Law of the Use of Security Surveillance Cameras (Royal Decree, 3 Oct 2022)
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity

### KSA-CCTV-03 — Prohibited camera locations
- **Limit:** check against ["room_schedule", "reflected_ceiling_plan"]; prohibited locations ["medical_operating_room", "medical_examination_room", "changing_room", "restroom", "women_salon", "private_space", "tourist_accommodation_residential_unit"]
- **When:** site.country eq "SA"
- **Does not apply / exception:** A hard placement constraint. A camera in one of these rooms is unlawful regardless of client instruction.; Check in the same design pass as B-04.
- **Basis:** LOCAL · Law of the Use of Security Surveillance Cameras (Royal Decree, 3 Oct 2022)
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity

### KSA-CCTV-04 — Recording retention and incident hold
**DO NOT USE — conflicts with SPT-CC-04.** CC-04 records retention as commonly 30-90 days per HCIS or project spec, tagged Practice. KSA-CCTV-04 records 90 days as a statutory minimum under the Law of the Use of Security Surveillance Cameras. For a Saudi site the statutory floor governs and 30 days is not available. Both remain unconfirmed against their primary sources.
**DO NOT USE — conflicts with SPT-LP-07.** LP-07 and the QuickRef set retention by CAMERA ROLE under Aramco/HCIS: gate surveillance 90 d, gate assessment (PTZ) 30 d, IDAS perimeter 60 d, VASS assessment 30 d. KSA-CCTV-04 records a 90-day statutory floor under the Law of the Use of Security Surveillance Cameras. The 30 d and 60 d figures sit BELOW that floor. If the premises fall under the camera law, the statutory minimum governs and a client standard cannot reduce it. Resolve per project: confirm whether the site is in scope of the law, and confirm the 90-day figure itself, which is still secondary-sourced.

- **Limit:** min retention 90 days; until completion_of_investigation_procedures; drives ["nvr_sizing", "storage_sizing"]; preserve unaltered on incident yes
- **When:** site.country eq "SA"
- **Calculator:** `calc_engine.video_storage()` — do not do this arithmetic yourself; call the module and quote its CalcResult.
- **Does not apply / exception:** Penalty up to SAR 5000 for failing to retain recordings.; Do not size storage from the 90-day figure until it is confirmed against the Implementing Regulation.
- **Basis:** LOCAL · Ministerial Decision 22688/1444 (Implementing Regulation)
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### KSA-CCTV-05 — Restriction on transferring or publishing recordings
- **Limit:** transfer or publication prohibited; implement via ["vms_export_permissions", "credential_handover_record"]; permitted only with ["ministry_approval", "court_order", "investigative_authority_request"]
- **When:** site.country eq "SA"
- **Does not apply / exception:** Penalty up to SAR 20000 for unlawful transfer or publication, or destruction of equipment.; Makes C-04 a legal exposure rather than only an IT-policy preference.
- **Basis:** LOCAL · Law of the Use of Security Surveillance Cameras (Royal Decree, 3 Oct 2022)
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity

### KSA-CCTV-06 — Ministry of Interior technical specification for camera systems
- **Limit:** min resolution hd_or_higher; relationship to ELV C 07 where the MOI specification sets a floor, that floor binds and C-07 pixel density is the method used to satisfy it
- **When:** site.country eq "SA"
- **Does not apply / exception:** Resolve together with C-07 and X-01 rather than treating them as alternatives.
- **Basis:** LOCAL · MOI general technical specifications for security surveillance camera systems
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### LP-01 — Perimeter fence line - Intrusion + CCTV (IDAS)
- **Limit:** why Perimeter is the first detection layer; fixed cameras give continuous surveillance, PTZ gives operator assessment; two sensor types cut single-technology defeat; key numbers Alarm zone <=150 m; localisation +/-75 m; Pd >=95%; nuisance & false <=1/zone/30 days; pre/post alarm 5-20 s; retention 60 days at 1080p30; what is used 2 or more independent sensor types (one volumetric, e.g. bi-static microwave or thermal/optical camera with analytics); fixed optical cameras along entire perimeter + PTZ assessment cameras that auto-slew to alarm zone; GIS map display
- **Basis:** LOCAL · SAES-O-205 (22-Mar-2023) 6.1; HCIS SEC-05 v2.0 (2017) 5.5
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity

### LP-02 — Perimeter fence line - CCTV (VASS)
- **Limit:** why Lower consequence class - coverage scoped by SRA rather than full IDAS; key numbers Class 4 coverage per SRA only; what is used VASS cameras at perimeter/external contiguous areas as designated by Security Risk Assessment; IDAS not mandatory
- **Basis:** LOCAL · SAES-O-205 (22-Mar-2023) 6.3, 7
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity

### LP-04 — Area outside perimeter - Long-range surveillance
- **Limit:** why Detect threats before they reach the fence; range tied to response time; key numbers LRS camera >=2 km (SEC-05); radar human detection >=3 km (SAES-O-205); what is used Radar (open areas) or thermal sensors cueing long-range PTZ camera; radar blanked toward protected facility
- **Basis:** LOCAL · SAES-O-205 (22-Mar-2023) 6.4; HCIS SEC-05 v2.0 (2017) 5.7.6
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity

### LP-05 — Main gate - vehicle lanes - ALPR
- **Limit:** why Validate vehicle against central list before it reaches the gatehouse; key numbers Camera <=50 m before gatehouse; shutter 1/1000 s; reads all GCC plates (Arabic/English + colour); new plate formats updated <=15 days; what is used ALPR camera + co-located IR/visible illuminator per entry lane; IP65 lane display; siren for PNG plate; gatehouse workstation
- **Basis:** LOCAL · SAES-O-205 (22-Mar-2023) 6.5; HCIS SEC-05 v2.0 (2017) 5.4
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity

### LP-07 — Main gate - pedestrian & vehicle - CCTV at gate
**DO NOT USE — conflicts with KSA-CCTV-04.** LP-07 and the QuickRef set retention by CAMERA ROLE under Aramco/HCIS: gate surveillance 90 d, gate assessment (PTZ) 30 d, IDAS perimeter 60 d, VASS assessment 30 d. KSA-CCTV-04 records a 90-day statutory floor under the Law of the Use of Security Surveillance Cameras. The 30 d and 60 d figures sit BELOW that floor. If the premises fall under the camera law, the statutory minimum governs and a client standard cannot reduce it. Resolve per project: confirm whether the site is in scope of the law, and confirm the 90-day figure itself, which is still secondary-sourced.

- **Limit:** why Records who used which credential and the general gate scene for investigation; key numbers User face recognisable for height 1.3-2.2 m; retention: gate surveillance 90 d, assessment 30 d, user 90 d; what is used Per gate: 1 fixed entry + 1 fixed exit (surveillance), 1 PTZ entry + 1 PTZ exit (assessment), 1 fixed user camera per card reader (2 s clip on swipe)
- **Calculator:** `calc_engine.video_storage()` — do not do this arithmetic yourself; call the module and quote its CalcResult.
- **Basis:** LOCAL · HCIS SEC-05 v2.0 (2017) 5.3.9-5.3.10; SAES-O-205 (22-Mar-2023) 6.2.6-6.2.7
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity

### LP-20 — Security cameras - all - CCTV spec
- **Limit:** why Consistent image quality for assessment and evidence; key numbers Optical 1080p @30 fps (may drop to 720p/7.5 fps when not in alarm); thermal LWIR >=320x240 @30 fps; IP66; VASS retention fixed 90 d / assessment 30 d / alarm events 90 d; recordings stored locally and at Dhahran (Aramco); what is used IP cameras direct to LAN; optical colour low-light, thermal in selected locations; fixed for surveillance/analytics, PTZ for assessment; video analytics on fixed cameras; video-loss alarm; geospatial coordinates
- **Calculator:** `calc_engine.video_storage()` — do not do this arithmetic yourself; call the module and quote its CalcResult.
- **Basis:** LOCAL · SAES-O-205 (22-Mar-2023) 5.14, 6.3; HCIS SEC-05 v2.0 (2017) 5.7-5.8
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity

### LP-21 — Process / plant operations area - CCTV
- **Limit:** why Operational visibility without loading the process control network; key numbers Latency <200 ms; VMS local recording >=72 h, archive (DAS/NAS) beyond 72 h; corporate uplink capped 100 Mbps/15%; what is used IP CCTV for operations (not IDAS); separate VLAN on PAN with control traffic prioritised; VMS client-server; motion/scheduled recording preferred
- **Calculator:** `calc_engine.video_storage()` — do not do this arithmetic yourself; call the module and quote its CalcResult.
- **Basis:** LOCAL · SAES-T-555 (2012 public copy) 5-9 (older edition - verify)
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity

### LP-22 — Hazardous (classified) area - CCTV / devices
- **Limit:** why Ignition-source control; key numbers Per SAES-B-068 area classification; what is used Ex-certified cameras/housings per area classification drawing (Class I / Zone / Group)
- **Basis:** LOCAL · SAES-T-555 (2012 public copy) 10.1
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity

### LP-32 — Hospital - pharmacy, medication rooms, labs, ED, loading dock, lift lobbies, fire stairs, CSSD, dept entrances - CCTV
- **Limit:** why Drug security, violence risk in ED, goods receipt, egress monitoring; what is used Internal + external CCTV at listed high-risk / high-traffic points; privacy respected in patient areas
- **Basis:** LOCAL · iHFG Part E; MOH Private Hospitals Design Guide (Scribd copy) 4-6-16
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### LP-43 — Parking / outdoor lots - CCTV
- **Limit:** why Vehicle crime, incident evidence; key numbers >=5 lux for colour image; what is used Pole-mounted outdoor IP cameras (IP66, sunshield), PoE where <=100 m else fibre; lighting check >=5 lux or IR/day-night
- **Basis:** LOCAL · SAES-T-555 (2012 public copy) 5.3.5, 10.5
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity

### C-01 — Outdoor and perimeter camera cabling protection
- **Limit:** measures ["outdoor_rated_cable", "sealed_entries", "high_impact_metallic_conduit"]; conduit only when ["risk_assessment", "sow"]
- **When:** camera.location in ["outdoor", "perimeter"]
- **Does not apply / exception:** A common over-pricing trap. Conduit here is SPEC, so X-06 blocks it from becoming scope without a citation.
- **Basis:** SPEC · Project risk assessment
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### C-04 — Security network segmentation and credential hygiene
- **Limit:** deadline before_handover; measures ["dedicated_vlan", "routing_restricted_to_vms_and_controllers", "unused_ports_disabled", "unused_services_disabled", "default_credentials_changed"]
- **Does not apply / exception:** Credential handover record belongs in the handover pack.
- **Basis:** SPEC · Client IT security policy
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### C-07 — Camera pixel density per task tier
- **Limit:** record per_camera; tier source client; tiers ["detect", "observe", "recognise", "identify"]
- **Does not apply / exception:** Camera count and lens selection follow the tier. Agreeing the tier late is a common cause of redesign.
- **Basis:** SPEC · IEC 62676-4
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### CC-04 — Storage
**DO NOT USE — conflicts with KSA-CCTV-04.** CC-04 records retention as commonly 30-90 days per HCIS or project spec, tagged Practice. KSA-CCTV-04 records 90 days as a statutory minimum under the Law of the Use of Security Surveillance Cameras. For a Saudi site the statutory floor governs and 30 days is not available. Both remain unconfirmed against their primary sources.

- **Limit:** Recording retention per spec
- **When:** Continuous/motion recording
- **Calculation:** TB = sum(Mbps) x 3600 x h/day x days / 8 / 10^6 x (1+overhead)
- **Calculator:** `calc_engine.video_storage()` — do not do this arithmetic yourself; call the module and quote its CalcResult.
- **In plain English:** Add up all camera bitrates (Mbps), convert to data per second, multiply by the seconds recorded each day and the number of days kept. Divide by 8 to turn bits into bytes and by 1,000,000 to get terabytes, then add extra for RAID and free space.
- **Does not apply / exception:** Event-only recording: apply duty-cycle factor
- **Basis:** SPEC · Practice (vendor calculators) · KSA/client: HCIS / project spec retention (commonly 30-90 days) - verify
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### CC-05 — Storage redundancy
- **Limit:** RAID 5/6 + >= 1 hot spare; + 20% free space
- **When:** NVR/VMS storage
- **Calculation:** Usable = raw x (n-k)/n
- **In plain English:** Some disks in a RAID array hold backup (parity) data, not recordings. Usable storage = raw storage x (total disks - parity disks) / total disks.
- **Does not apply / exception:** Edge (SD) recording as failover
- **Basis:** SPEC · Practice · KSA/client: Client spec
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### CC-06 — Network bandwidth
- **Limit:** Link utilisation <= 70%
- **When:** Camera uplinks / NVR NICs
- **Calculation:** BW = sum stream Mbps (main + sub + live view)
- **Calculator:** `calc_engine.network_bandwidth()` — do not do this arithmetic yourself; call the module and quote its CalcResult.
- **In plain English:** Network bandwidth needed = the sum of every video stream: main recording stream, secondary stream and any live viewing.
- **Does not apply / exception:** Multicast live view reduces load
- **Basis:** SPEC · Practice
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### CC-09 — Face ID camera geometry
- **Limit:** Vertical angle to face <= 15 deg; horizontal <= 30 deg off-axis
- **When:** Identification views (entries)
- **Calculation:** theta = atan((h_cam - 1.6)/d)
- **In plain English:** Work out the camera's downward angle to a face: the height difference between the camera and a face (1.6 m) divided by the distance, then take the angle. It must be 15 degrees or less to identify faces.
- **Does not apply / exception:** Stereo/overhead analytics
- **Basis:** SPEC · IEC 62676-4 guidance / practice · KSA/client: HCIS / project SOW
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### CC-11 — Coverage overlap
- **Limit:** Adjacent perimeter views overlap; no blind zones at fence line
- **When:** Perimeter security
- **Calculation:** Overlap = FOV_n intersect FOV_n+1 > 0 at detection distance
- **In plain English:** Check that each camera's field of view overlaps the next one at the detection distance, so there are no gaps along the perimeter.
- **Does not apply / exception:** Radar/PIDS-cued PTZ designs
- **Basis:** SPEC · Practice · KSA/client: HCIS perimeter directives - verify
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.
