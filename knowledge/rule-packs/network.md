# Network — rule pack

11 rules. Generated from the database; see
[`../rule-packs/README.md`](README.md) for how to use these and what to output.

---
### NW-01 — PoE power per port (at PSE)
- **Limit:** af 15.4 W; at 30 W; bt Type 3 60 W; bt Type 4 90 W
- **When:** PD class
- **Calculation:** PD available: 12.95 / 25.5 / 51 / 71.3 W
- **Calculator:** `calc_engine.poe_budget()` — do not do this arithmetic yourself; call the module and quote its CalcResult.
- **In plain English:** The switch sends more power than the device actually receives because some is lost in the cable. Devices actually get 12.95 W, 25.5 W, 51 W or 71.3 W depending on class.
- **Does not apply / exception:** Proprietary UPoE per vendor
- **Basis:** CODE · IEEE 802.3af/at/bt
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### NW-05 — Copper Ethernet reach
- **Limit:** 100 m channel
- **When:** 1/2.5/5/10GBASE-T
- **Does not apply / exception:** 10GBASE-T on Cat6 limited to ~55 m
- **Basis:** CODE · IEEE 802.3 / TIA-568 · KSA/client: SAES-T-916 - verify
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### NW-06 — Fibre reach (10G)
- **Limit:** OM3 300 m; OM4 400 m (SR); OS2 10 km (LR)
- **When:** 10GBASE-SR/LR
- **Calculation:** Check against loss budget (SC-12)
- **In plain English:** Check the fibre run against the loss budget in SC-12 as well as the maximum distance for the fibre type.
- **Does not apply / exception:** Higher speeds reduce MM reach
- **Basis:** CODE · IEEE 802.3ae
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### NW-07 — Segmentation
- **Limit:** Security/ELV/OT systems on separate VLANs/VRFs with ACL/firewall
- **When:** Converged networks
- **Does not apply / exception:** Physically separate networks
- **Basis:** CODE · IEC 62443 zones & conduits · KSA/client: NCA ECC-2:2024 (network security mgmt); NCA OTCC-1:2022 for OT
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### NW-08 — Logging & monitoring
- **Limit:** Central logs, NTP, SIEM integration
- **When:** Critical systems
- **Basis:** CODE · ISO/IEC 27001 · KSA/client: NCA ECC-2:2024 (event logs & monitoring)
- **Scope:** binds on its own
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### LP-18 — Security systems - all core equipment - Servers / network / storage
- **Limit:** why Security systems must survive single failures and cyber attack; key numbers Availability >=99.95%; spare 20% CPU/RAM, 20% ports, 20% bandwidth, 50% disk; full backup every 30 days + daily incremental, off-site; what is used High-availability (redundant units, hot-swap or virtualised); no single point of failure except field sensors; encrypted external interfaces with ICD/API; NTP; tamper alarms; outdoor cables in steel conduit
- **Basis:** LOCAL · SAES-O-205 (22-Mar-2023) 5.1-5.10; HCIS SEC-05 v2.0 (2017) 5.2
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity

### LP-24 — Remote sites (wells, bulk plants, AFOs) - CCTV / network
- **Limit:** why No local building; bandwidth is scarce; key numbers Camera traffic <=10% of leased link, with >=20% free before adding cameras; what is used Camera access switch at camera site; leased IP-VPN link
- **Calculator:** `calc_engine.network_bandwidth()` — do not do this arithmetic yourself; call the module and quote its CalcResult.
- **Basis:** LOCAL · SAES-T-555 (2012 public copy) 6.1.8, 6.1.10
- **Scope:** applies only in SA; cite the instrument before it becomes a quantity

### NW-02 — Switch PoE budget
- **Limit:** sum PD max class x 1.2 <= switch PoE budget
- **When:** Access switches
- **Calculation:** Budget_req = 1.2 x sum P_class
- **Calculator:** `calc_engine.poe_budget()` — do not do this arithmetic yourself; call the module and quote its CalcResult.
- **In plain English:** Switch PoE budget needed = the sum of every device's class power, plus 20% extra.
- **Does not apply / exception:** LLDP power negotiation allows tighter sizing
- **Basis:** SPEC · Practice
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### NW-03 — Port spare capacity
- **Limit:** Active ports + 20-25% spare
- **When:** Access layer
- **Calculation:** Ports = ceil(active x 1.2)
- **In plain English:** Number of ports = active devices x 1.2 (20% spare), rounded up to a whole port.
- **Basis:** SPEC · Practice · KSA/client: Project spec
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### NW-04 — Oversubscription
- **Limit:** Access->distribution <= 20:1; distribution->core <= 4:1
- **When:** Data networks
- **Calculation:** Ratio = sum access port BW / uplink BW
- **In plain English:** Oversubscription ratio = total bandwidth of all user ports / bandwidth of the uplink. Example: 48 x 1 Gbps ports on a 10 Gbps uplink = 4.8:1. *(example invented, not from the workbook)*
- **Does not apply / exception:** CCTV/storage traffic: size for sustained load, not ratio
- **Basis:** SPEC · Vendor design guides (practice)
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.

### NW-09 — Redundancy
- **Limit:** Dual PSU + redundant uplinks at core/distribution
- **When:** Critical services
- **Does not apply / exception:** Small standalone systems
- **Basis:** SPEC · Practice · KSA/client: Client spec
- **Scope:** NOT scope on its own — needs a drawing or SOW clause to be priced
- **Unverified:** the cited source was not read, or is a superseded edition. Do not quote to a client without checking.
