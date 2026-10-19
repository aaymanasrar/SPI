# UPS — rule pack

15 rules. Generated from the database; see
[`../rule-packs/README.md`](README.md) for how to use these and what to output.

---
### LP-16 — Battery room - Ventilation / UPS
- **Limit:** why H2 off-gassing; KSA ambient shortens VRLA life; key numbers Q = 0.05 x n x Igas x Crt x 10^-3 m3/h; what is used Mechanical ventilation sized for hydrogen dilution; conditioned room
- **Basis:** CODE · IEC 62485-2 (see rule UP-05)
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### UP-02 — Battery runtime sizing
- **Limit:** Runtime per spec at end-of-life
- **When:** VRLA/Li-ion
- **Calculation:** Wh = P_load x t / (eta_inv x DoD); Ah = Wh / V_DC x 1.25 aging x temp factor
- **Calculator:** `calc_engine.dc_battery_bank()` — do not do this arithmetic yourself; call the module and quote its CalcResult.
- **Does not apply / exception:** Generator-backed: shorter runtime acceptable
- **Basis:** CODE · IEEE 1184 (UPS batteries); IEEE 485 (lead-acid method) · KSA/client: Project spec runtime
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### UP-03 — Battery temperature
- **Limit:** Rated life at 20-25 C; life ~halves per +10 C
- **When:** Battery room/cabinet
- **Calculation:** Life_T = Life_25 x 0.5^((T-25)/10)
- **Does not apply / exception:** Li-ion tolerates higher T per vendor
- **Basis:** CODE · IEC 60896-21/22; vendor · KSA/client: KSA ambient -> conditioned battery room required
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### UP-05 — Battery room ventilation
- **Limit:** Airflow to keep H2 < 4% (dilution)
- **When:** Lead-acid batteries
- **Calculation:** Q (m3/h) = 0.05 x n_cells x I_gas x C_rt x 10^-3 (VRLA float I_gas = 1 mA/Ah)
- **Does not apply / exception:** Sealed Li-ion per vendor
- **Basis:** CODE · IEC 62485-2 · KSA/client: SBC 501
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### UP-06 — Protection & cabling
- **Limit:** Input/output devices & cables per electrical code with continuous-load factor
- **When:** All UPS
- **Calculation:** I_breaker >= 1.25 x I_input_max
- **Does not apply / exception:** Coordinate with vendor recommendations
- **Basis:** CODE · IEC 60364 · KSA/client: SBC 401
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### UP-10 — Supply characteristics
- **Limit:** Input 230/400 V, 60 Hz
- **When:** KSA sites
- **Does not apply / exception:** Aramco in-plant voltages per SAES-P
- **Basis:** CODE · IEC 60038 · KSA/client: SASO / SEC: KSA is 60 Hz; confirm legacy 127/220 V sites
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### UP-11 — Fire alarm secondary supply
- **Limit:** FACP keeps own batteries; UPS only if it meets NFPA 72 Ch.10 secondary-supply rules
- **When:** Life-safety panels
- **Does not apply / exception:** AHJ-approved central UPS
- **Basis:** CODE · NFPA 72 Ch.10 · KSA/client: SBC 801
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### LP-19 — Security systems - power - UPS
- **Limit:** why Security must keep running through utility loss; key numbers Autonomy value: see SAES-O-207/SEC-07 (NOT RETRIEVED - verify); what is used All security systems on UPS backed by emergency generator; power per SAES-O-207 / HCIS SEC-07
- **Calculator:** `calc_engine.dc_battery_bank()` — do not do this arithmetic yourself; call the module and quote its CalcResult.
- **Basis:** LOCAL · HCIS SEC-05 v2.0 (2017) 5.2.10; SAES-O-205 (22-Mar-2023) 5.8
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity

### LP-30 — Hospital - ICU / OR / critical care - UPS / power
- **Limit:** why Life-support continuity; key numbers Generator for >=3 h; loads designed at 120%; what is used Dedicated UPS for operations, ICU and critical care; outlets on three colour-coded sources (normal / emergency / UPS)
- **Calculator:** `calc_engine.dc_battery_bank()` — do not do this arithmetic yourself; call the module and quote its CalcResult.
- **Basis:** LOCAL · MOH Private Hospitals Design Guide (Scribd copy) 2-6-7 to 2-6-19
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### LP-31 — Hospital - light current systems - UPS
- **Limit:** why Keep communications and life-safety signalling up during transfer; key numbers >=30 min autonomy; what is used UPS feeding light-current systems (IT, CCTV, fire alarm, etc.)
- **Calculator:** `calc_engine.dc_battery_bank()` — do not do this arithmetic yourself; call the module and quote its CalcResult.
- **Basis:** LOCAL · MOH Private Hospitals Design Guide (Scribd copy) 2-6-12
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### UP-01 — UPS rating
- **Limit:** Load <= 80% of UPS kW rating incl. growth
- **When:** All UPS
- **Calculation:** kW_req = sum P_load x (1 + growth 0.2-0.25) / 0.8; kVA = kW / PF_UPS
- **Calculator:** `calc_engine.ups_sizing()` — do not do this arithmetic yourself; call the module and quote its CalcResult.
- **In plain English:** UPS size in kW = total load x (1 + 20-25% growth) / 0.8, so the UPS runs at no more than 80%. Then kVA = kW / the UPS power factor.
- **Basis:** SPEC · Practice / vendor · KSA/client: Project spec
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### UP-04 — Topology
- **Limit:** Online double-conversion VFI-SS-111
- **When:** Critical ICT/ELV
- **Does not apply / exception:** Line-interactive for non-critical desktops
- **Basis:** SPEC · IEC 62040-3 · KSA/client: Client spec
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### UP-07 — Maintenance bypass
- **Limit:** External wraparound bypass for service without load drop
- **When:** Critical UPS
- **Does not apply / exception:** Parallel redundant systems
- **Basis:** SPEC · Practice · KSA/client: Client spec
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### UP-08 — Input harmonics
- **Limit:** THDi < 5% at full load (IGBT rectifier)
- **When:** Grid-connected
- **Does not apply / exception:** Small UPS < 10 kVA
- **Basis:** SPEC · IEEE 519 / vendor · KSA/client: SEC grid code
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### UP-09 — Redundancy
- **Limit:** N+1 for critical loads
- **When:** Data/security systems
- **Calculation:** Modules = N + 1
- **Basis:** SPEC · Uptime tier / practice · KSA/client: Client spec
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.
