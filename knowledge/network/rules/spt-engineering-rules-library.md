# Network - SPT Engineering Rules Library

**Source:** Engineering Rules Library - ELV / ICT / Fire (SPT Pre-Sales, compiled
29 Sep 2026), `Engineering_Rules_Library.xlsx`. See
[the source record](../../standards-references/spt-engineering-rules-library/README.md) for the basis legend, the precedence
order, the library's stated limitations, and how these rules relate to the 57 already
encoded from the earlier documents.

**System:** `network` · **Rules:** 9 (Code 3, Code - verify 2, Practice 4)

> **Basis is not confidence.** `Code` and `Code - verify` are both encoded with
> `confidence = code`; the difference is that `Code - verify` needs its clause, edition
> or value checked before it reaches a submittal, which is recorded in
> `verification_note` and raised as `critical_review` rather than `error`. `Practice`
> is encoded as `confidence = spec` and cannot become scope on its own (ELV-X-06).

| ID | Requirement | Value / limit | Condition | Calculation | Source | Saudi / client overlay | Exception | Basis |
|---|---|---|---|---|---|---|---|---|
| NW-01 | PoE power per port (at PSE) | af 15.4 W; at 30 W; bt Type 3 60 W; bt Type 4 90 W | PD class | PD available: 12.95 / 25.5 / 51 / 71.3 W | IEEE 802.3af/at/bt | — | Proprietary UPoE per vendor | Code |
| NW-02 | Switch PoE budget | sum PD max class x 1.2 <= switch PoE budget | Access switches | Budget_req = 1.2 x sum P_class | Practice | — | LLDP power negotiation allows tighter sizing | Practice |
| NW-03 | Port spare capacity | Active ports + 20-25% spare | Access layer | Ports = ceil(active x 1.2) | Practice | Project spec | — | Practice |
| NW-04 | Oversubscription | Access->distribution <= 20:1; distribution->core <= 4:1 | Data networks | Ratio = sum access port BW / uplink BW | Vendor design guides (practice) | — | CCTV/storage traffic: size for sustained load, not ratio | Practice |
| NW-05 | Copper Ethernet reach | 100 m channel | 1/2.5/5/10GBASE-T | — | IEEE 802.3 / TIA-568 | SAES-T-916 - verify | 10GBASE-T on Cat6 limited to ~55 m | Code |
| NW-06 | Fibre reach (10G) | OM3 300 m; OM4 400 m (SR); OS2 10 km (LR) | 10GBASE-SR/LR | Check against loss budget (SC-12) | IEEE 802.3ae | — | Higher speeds reduce MM reach | Code |
| NW-07 | Segmentation | Security/ELV/OT systems on separate VLANs/VRFs with ACL/firewall | Converged networks | — | IEC 62443 zones & conduits | NCA ECC-2:2024 (network security mgmt); NCA OTCC-1:2022 for OT | Physically separate networks | Code - verify |
| NW-08 | Logging & monitoring | Central logs, NTP, SIEM integration | Critical systems | — | ISO/IEC 27001 | NCA ECC-2:2024 (event logs & monitoring) | — | Code - verify |
| NW-09 | Redundancy | Dual PSU + redundant uplinks at core/distribution | Critical services | — | Practice | Client spec | Small standalone systems | Practice |

## Plain-English explanations of the calculations

> **Authored by the supplier, not present in the workbook.** Explanatory
> only. Stored as `calculation.plain_english` with a provenance marker, and
> never the basis of a calculation or a quoted value — the `value_limit`
> and `calculation` fields above are the source of record. The wording may be
> edited freely; the values above may not.

| ID | In plain English |
|---|---|
| NW-01 | The switch sends more power than the device actually receives because some is lost in the cable. Devices actually get 12.95 W, 25.5 W, 51 W or 71.3 W depending on class. |
| NW-02 | Switch PoE budget needed = the sum of every device's class power, plus 20% extra. |
| NW-03 | Number of ports = active devices x 1.2 (20% spare), rounded up to a whole port. |
| NW-04 | Oversubscription ratio = total bandwidth of all user ports / bandwidth of the uplink. Example: 48 x 1 Gbps ports on a 10 Gbps uplink = 4.8:1. **(illustrative example, invented — not a workbook value)** |
| NW-06 | Check the fibre run against the loss budget in SC-12 as well as the maximum distance for the fibre type. |

## Relationship to rules already encoded

| This rule | Existing rule | Relationship | Note |
|---|---|---|---|
| NW-07 | ELV-C-04 | **resolves** | ELV-C-04 was SPEC, deferring to any client IT policy. NW-07 and CC-12 name NCA ECC-2:2024 and OTCC-1:2022, which is a national authority for Saudi sites rather than a preference. |
| NW-05 | ELV-A-01 | **agrees** | Same 100 m channel, with the added note that 10GBASE-T on Cat 6 is limited to about 55 m. |
