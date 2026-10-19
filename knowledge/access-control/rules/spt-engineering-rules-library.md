# Access Control - SPT Engineering Rules Library

**Source:** Engineering Rules Library - ELV / ICT / Fire (SPT Pre-Sales, compiled
29 Sep 2026), `Engineering_Rules_Library.xlsx`. See
[the source record](../../standards-references/spt-engineering-rules-library/README.md) for the basis legend, the precedence
order, the library's stated limitations, and how these rules relate to the 57 already
encoded from the earlier documents.

**System:** `acs` · **Rules:** 11 (Code 5, Code - verify 2, Practice 4)

> **Basis is not confidence.** `Code` and `Code - verify` are both encoded with
> `confidence = code`; the difference is that `Code - verify` needs its clause, edition
> or value checked before it reaches a submittal, which is recorded in
> `verification_note` and raised as `critical_review` rather than `error`. `Practice`
> is encoded as `confidence = spec` and cannot become scope on its own (ELV-X-06).

| ID | Requirement | Value / limit | Condition | Calculation | Source | Saudi / client overlay | Exception | Basis |
|---|---|---|---|---|---|---|---|---|
| AC-01 | Free egress | Egress door opens from egress side without key, tool, or special knowledge | All means of egress | — | NFPA 101 §7.2.1.5; IBC §1010 | SBC 201 Ch.10; SBC 801 | Approved delayed egress / controlled egress (healthcare) | Code |
| AC-02 | Electrically locked egress doors (maglocks) | Release by approach sensor (REX) AND manual push button within 1.5 m of door at 1.0-1.2 m AFF, 'PUSH TO EXIT', unlock >= 30 s | Sensor-release egress doors | — | NFPA 101 §7.2.1.6.2; IBC §1010.2.14 | SBC 201 Ch.10 | Mechanical free-egress hardware (fail-secure strike) avoids this | Code |
| AC-03 | Fire alarm & power-loss release | Egress locks unlock on FA activation and on loss of power | Sensor-release / delayed egress | FA relay -> lock PSU input (hard-wired, not software) | NFPA 101 §7.2.1.6; IBC §1010 | SBC 801 §907 interface; Civil Defense | Fail-secure hardware with mechanical egress | Code |
| AC-04 | Delayed egress | Release <= 15 s (30 s with AHJ); irreversible; signage; building sprinklered or detected | Approved occupancies only | — | NFPA 101 §7.2.1.6.1; IBC §1010.2.13 | SBC 201; AHJ approval | Not permitted in assembly/some occupancies | Code |
| AC-05 | Door hardware height | Operable parts 0.865-1.22 m (34-48 in) AFF | Egress doors | — | NFPA 101 §7.2.1.5; IBC §1010 | SBC 201 | Existing buildings | Code |
| AC-06 | Reader mounting | Operable part <= 1.22 m AFF (reach range) | Accessible route | — | ADA / ICC A117.1 reach range | SBC 201 accessibility | Vehicle readers per lane geometry | Code - verify |
| AC-07 | Reader cable length | Wiegand typ. <= 150 m; OSDP/RS-485 <= 1,200 m | Per vendor cable spec | — | SIA OSDP / vendor | NCA ECC - prefer OSDP Secure Channel | Fibre/IP readers | Practice |
| AC-08 | Door monitoring | Door position switch + REX on every controlled door (held/forced alarms) | Controlled doors | — | UL 294 / IEC 60839-11-1 | HCIS / Aramco security SAES - verify grade | Free-exit doors with no monitoring requirement | Practice |
| AC-09 | Lock power supply | PSU >= 1.25 x sum lock + reader current; battery backup per spec | Electrified locks | I_PSU = 1.25 x (sum I_lock + sum I_reader) | Practice / UL 294 | Project spec (backup duration) | PoE-powered locks within PSE budget | Practice |
| AC-10 | Controller spare capacity | >= 20% spare doors/inputs/outputs | Controllers & panels | Spare = 1 - used/max | Practice | Project spec | — | Practice |
| AC-11 | Security grade | Select grade 1-4 per risk | System design | — | IEC 60839-11-1 | HCIS directives for industrial facilities (SEC-01 general requirements) | — | Code - verify |

## Plain-English explanations of the calculations

> **Authored by the supplier, not present in the workbook.** Explanatory
> only. Stored as `calculation.plain_english` with a provenance marker, and
> never the basis of a calculation or a quoted value — the `value_limit`
> and `calculation` fields above are the source of record. The wording may be
> edited freely; the values above may not.

| ID | In plain English |
|---|---|
| AC-03 | The fire alarm relay cuts power to the lock power supply directly through wiring, not through software, so doors unlock even if the software fails. |
| AC-09 | Lock power supply size = total current of all locks and readers, plus 25% extra. |
| AC-10 | Spare capacity = 1 minus (used points / maximum points). Must be at least 20%. |

## Relationship to rules already encoded

| This rule | Existing rule | Relationship | Note |
|---|---|---|---|
| AC-02 | ELV-B-09 | **refines** | ELV-B-09 required maglock release on alarm and on power loss. AC-02 adds the sensor-release arrangement: REX plus a manual push button within 1.5 m at 1.0-1.2 m AFF, PUSH TO EXIT signage, and a minimum 30 s unlock. |
| AC-03 | ELV-C-06 | **refines** | Adds the implementation constraint that the fire alarm to lock interface is hard-wired through the lock PSU, not a software link. |
| AC-07 | ELV-C-05 | **agrees** | Both prefer OSDP over Wiegand. AC-07 adds the cable-length limits (Wiegand ~150 m, OSDP/RS-485 ~1200 m) and cites NCA ECC. |
