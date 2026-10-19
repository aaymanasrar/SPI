# UPS - SPT Engineering Rules Library

**Source:** Engineering Rules Library - ELV / ICT / Fire (SPT Pre-Sales, compiled
29 Sep 2026), `Engineering_Rules_Library.xlsx`. See
[the source record](../../standards-references/spt-engineering-rules-library/README.md) for the basis legend, the precedence
order, the library's stated limitations, and how these rules relate to the 57 already
encoded from the earlier documents.

**System:** `ups` · **Rules:** 11 (Code 2, Code - verify 4, Practice 5)

> **Basis is not confidence.** `Code` and `Code - verify` are both encoded with
> `confidence = code`; the difference is that `Code - verify` needs its clause, edition
> or value checked before it reaches a submittal, which is recorded in
> `verification_note` and raised as `critical_review` rather than `error`. `Practice`
> is encoded as `confidence = spec` and cannot become scope on its own (ELV-X-06).

| ID | Requirement | Value / limit | Condition | Calculation | Source | Saudi / client overlay | Exception | Basis |
|---|---|---|---|---|---|---|---|---|
| UP-01 | UPS rating | Load <= 80% of UPS kW rating incl. growth | All UPS | kW_req = sum P_load x (1 + growth 0.2-0.25) / 0.8; kVA = kW / PF_UPS | Practice / vendor | Project spec | — | Practice |
| UP-02 | Battery runtime sizing | Runtime per spec at end-of-life | VRLA/Li-ion | Wh = P_load x t / (eta_inv x DoD); Ah = Wh / V_DC x 1.25 aging x temp factor | IEEE 1184 (UPS batteries); IEEE 485 (lead-acid method) | Project spec runtime | Generator-backed: shorter runtime acceptable | Code |
| UP-03 | Battery temperature | Rated life at 20-25 C; life ~halves per +10 C | Battery room/cabinet | Life_T = Life_25 x 0.5^((T-25)/10) | IEC 60896-21/22; vendor | KSA ambient -> conditioned battery room required | Li-ion tolerates higher T per vendor | Code - verify |
| UP-04 | Topology | Online double-conversion VFI-SS-111 | Critical ICT/ELV | — | IEC 62040-3 | Client spec | Line-interactive for non-critical desktops | Practice |
| UP-05 | Battery room ventilation | Airflow to keep H2 < 4% (dilution) | Lead-acid batteries | Q (m3/h) = 0.05 x n_cells x I_gas x C_rt x 10^-3 (VRLA float I_gas = 1 mA/Ah) | IEC 62485-2 | SBC 501 | Sealed Li-ion per vendor | Code |
| UP-06 | Protection & cabling | Input/output devices & cables per electrical code with continuous-load factor | All UPS | I_breaker >= 1.25 x I_input_max | IEC 60364 | SBC 401 | Coordinate with vendor recommendations | Code - verify |
| UP-07 | Maintenance bypass | External wraparound bypass for service without load drop | Critical UPS | — | Practice | Client spec | Parallel redundant systems | Practice |
| UP-08 | Input harmonics | THDi < 5% at full load (IGBT rectifier) | Grid-connected | — | IEEE 519 / vendor | SEC grid code | Small UPS < 10 kVA | Practice |
| UP-09 | Redundancy | N+1 for critical loads | Data/security systems | Modules = N + 1 | Uptime tier / practice | Client spec | — | Practice |
| UP-10 | Supply characteristics | Input 230/400 V, 60 Hz | KSA sites | — | IEC 60038 | SASO / SEC: KSA is 60 Hz; confirm legacy 127/220 V sites | Aramco in-plant voltages per SAES-P | Code - verify |
| UP-11 | Fire alarm secondary supply | FACP keeps own batteries; UPS only if it meets NFPA 72 Ch.10 secondary-supply rules | Life-safety panels | — | NFPA 72 Ch.10 | SBC 801 | AHJ-approved central UPS | Code - verify |

## Plain-English explanations of the calculations

> **Authored by the supplier, not present in the workbook.** Explanatory
> only. Stored as `calculation.plain_english` with a provenance marker, and
> never the basis of a calculation or a quoted value — the `value_limit`
> and `calculation` fields above are the source of record. The wording may be
> edited freely; the values above may not.

| ID | In plain English |
|---|---|
| UP-01 | UPS size in kW = total load x (1 + 20-25% growth) / 0.8, so the UPS runs at no more than 80%. Then kVA = kW / the UPS power factor. |

Not received (supplying message truncated): UP-02, UP-03, UP-05, UP-06, UP-09.

## Relationship to rules already encoded

| This rule | Existing rule | Relationship | Note |
|---|---|---|---|
| UP-11 | ELV-B-11 | **refines** | Adds that a FACP keeps its own batteries and a central UPS only qualifies if it meets NFPA 72 Ch.10 secondary-supply rules. |
