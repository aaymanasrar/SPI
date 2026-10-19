# Access Control — rule pack

16 rules. Generated from the database; see
[`../rule-packs/README.md`](README.md) for how to use these and what to output.

---
### C-06 — Door failure mode set from the egress and fire strategy
- **Limit:** see also ELV-B-09; linked to fire_alarm_release; modes ["fail_safe", "fail_secure"]; determined by ["egress_strategy", "fire_strategy"]
- **When:** door.has_access_control eq true
- **Does not apply / exception:** The door schedule and the cause-and-effect matrix must agree. X-03 is where that is proven.
- **Basis:** CODE · NFPA 101 and local building code
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### AC-01 — Free egress
- **Limit:** Egress door opens from egress side without key, tool, or special knowledge
- **When:** All means of egress
- **Does not apply / exception:** Approved delayed egress / controlled egress (healthcare)
- **Basis:** CODE · NFPA 101 §7.2.1.5; IBC §1010 · KSA/client: SBC 201 Ch.10; SBC 801
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### AC-02 — Electrically locked egress doors (maglocks)
- **Limit:** Release by approach sensor (REX) AND manual push button within 1.5 m of door at 1.0-1.2 m AFF, 'PUSH TO EXIT', unlock >= 30 s
- **When:** Sensor-release egress doors
- **Does not apply / exception:** Mechanical free-egress hardware (fail-secure strike) avoids this
- **Basis:** CODE · NFPA 101 §7.2.1.6.2; IBC §1010.2.14 · KSA/client: SBC 201 Ch.10
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### AC-03 — Fire alarm & power-loss release
- **Limit:** Egress locks unlock on FA activation and on loss of power
- **When:** Sensor-release / delayed egress
- **Calculation:** FA relay -> lock PSU input (hard-wired, not software)
- **In plain English:** The fire alarm relay cuts power to the lock power supply directly through wiring, not through software, so doors unlock even if the software fails.
- **Does not apply / exception:** Fail-secure hardware with mechanical egress
- **Basis:** CODE · NFPA 101 §7.2.1.6; IBC §1010 · KSA/client: SBC 801 §907 interface; Civil Defense
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### AC-04 — Delayed egress
- **Limit:** Release <= 15 s (30 s with AHJ); irreversible; signage; building sprinklered or detected
- **When:** Approved occupancies only
- **Does not apply / exception:** Not permitted in assembly/some occupancies
- **Basis:** CODE · NFPA 101 §7.2.1.6.1; IBC §1010.2.13 · KSA/client: SBC 201; AHJ approval
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### AC-05 — Door hardware height
- **Limit:** Operable parts 0.865-1.22 m (34-48 in) AFF
- **When:** Egress doors
- **Does not apply / exception:** Existing buildings
- **Basis:** CODE · NFPA 101 §7.2.1.5; IBC §1010 · KSA/client: SBC 201
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### AC-06 — Reader mounting
- **Limit:** Operable part <= 1.22 m AFF (reach range)
- **When:** Accessible route
- **Does not apply / exception:** Vehicle readers per lane geometry
- **Basis:** CODE · ADA / ICC A117.1 reach range · KSA/client: SBC 201 accessibility
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### AC-11 — Security grade
- **Limit:** Select grade 1-4 per risk
- **When:** System design
- **Basis:** CODE · IEC 60839-11-1 · KSA/client: HCIS directives for industrial facilities (SEC-01 general requirements)
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### LP-06 — Main gate - pedestrian & vehicle - Access control (SACS)
- **Limit:** why Cannot be bypassed; prevents tailgating; anti-passback keeps on-site muster list accurate; key numbers Alarm response <0.5 s; data upload <=10 min; central data 36 months; PIN change every 6 months; one reader per SED; 2 or more controllers alternating readers; what is used Turnstiles (pedestrian) and drop arms / anti-vehicle barriers (vehicles) as Single Entry Devices; PIV card + 4-digit or longer PIN, or PIV + biometric; bi-directional turnstile gets readers both sides; duress code; electro-mechanical emergency release
- **Basis:** LOCAL · SAES-O-205 (22-Mar-2023) 6.2; HCIS SEC-05 v2.0 (2017) 5.3
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity

### LP-10 — Plant control room - Access control
- **Limit:** why Control room is a vital asset inside an already-controlled restricted area; key numbers 2 or more card readers on entry side (SEC-05); UPS + generator backup; what is used Standalone scaled-down ACS; card readers + camera at every entry side; not required to link to company-wide ACS
- **Basis:** LOCAL · SAES-O-205 (22-Mar-2023) 6.7; HCIS SEC-05 v2.0 (2017) 5.9
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity

### LP-33 — Hospital - fire exits, medication/utility rooms, server, imaging, pharmacy, isolation, dept entrances - Access control
- **Limit:** why Restrict drugs/equipment; egress must release on alarm; what is used Card access; electrically locked doors on escape routes interlocked with fire alarm
- **Basis:** LOCAL · iHFG Part E
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### C-05 — OSDP with Secure Channel active, not Wiegand
- **Limit:** not wiegand; wiring supervised; protocol osdp; encryption aes_128; secure channel required_active
- **When:** reader.supports_osdp eq true; controller.supports_osdp eq true
- **Does not apply / exception:** Confirm Secure Channel is active on each reader at handover, not merely supported.
- **Basis:** SPEC · IEC 60839-11-5:2020 (OSDP v2.2.2)
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced

### AC-07 — Reader cable length
- **Limit:** Wiegand typ. <= 150 m; OSDP/RS-485 <= 1,200 m
- **When:** Per vendor cable spec
- **Does not apply / exception:** Fibre/IP readers
- **Basis:** SPEC · SIA OSDP / vendor · KSA/client: NCA ECC - prefer OSDP Secure Channel
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### AC-08 — Door monitoring
- **Limit:** Door position switch + REX on every controlled door (held/forced alarms)
- **When:** Controlled doors
- **Does not apply / exception:** Free-exit doors with no monitoring requirement
- **Basis:** SPEC · UL 294 / IEC 60839-11-1 · KSA/client: HCIS / Aramco security SAES - verify grade
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### AC-09 — Lock power supply
- **Limit:** PSU >= 1.25 x sum lock + reader current; battery backup per spec
- **When:** Electrified locks
- **Calculation:** I_PSU = 1.25 x (sum I_lock + sum I_reader)
- **In plain English:** Lock power supply size = total current of all locks and readers, plus 25% extra.
- **Does not apply / exception:** PoE-powered locks within PSE budget
- **Basis:** SPEC · Practice / UL 294 · KSA/client: Project spec (backup duration)
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### AC-10 — Controller spare capacity
- **Limit:** >= 20% spare doors/inputs/outputs
- **When:** Controllers & panels
- **Calculation:** Spare = 1 - used/max
- **In plain English:** Spare capacity = 1 minus (used points / maximum points). Must be at least 20%.
- **Basis:** SPEC · Practice · KSA/client: Project spec
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.
