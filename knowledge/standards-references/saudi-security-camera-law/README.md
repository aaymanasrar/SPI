# Law of the Use of Security Surveillance Cameras (Saudi Arabia) — source record

| Field | Value |
|---|---|
| Law | Law of the Use of Security Surveillance Cameras |
| Instrument | Royal Decree, 3 October 2022 (Council of Ministers decision, 27 September 2022) |
| Implementing Regulation | Ministerial Decision No. **22688/1444**, approving the Implementing Regulation **and** the Security Conditions and Requirements Document (Terms of Reference) |
| Regulator | Ministry of Interior (MOI / MOII) |
| Rules encoded | `KSA-CCTV-01` … `KSA-CCTV-06` |
| Retrieved | 24 September 2026 |
| Encoded by migration | `supabase/migrations/0016_tia568b_verification_and_ksa_cctv.sql` |

---

## 1. Why this matters more than the rest of Part C

The ELV guide's Part C is its weakest section: the guide says so itself, and the case studies
behind it are UK CCTV and intruder projects that state nothing about conduit, VLANs, OSDP or PoE.
Part C carries no rule from the jurisdiction SmartPage actually builds in.

This law does. For a Saudi site it is not advisory and not good practice — it is **statute, with
per-camera fines**, and it constrains the design directly: where a camera may not be pointed, how
long recordings must be kept, and whether the work may lawfully begin at all.

**Tagged LOCAL, and that is not a demotion.** LOCAL in this rule set means *bounded to one
jurisdiction* (see the confidence table in the ELV guide source record), not *weak*. On a Saudi
project these rules are mandatory; on a project anywhere else they do not apply at all. The X-06
scope gate still requires a citation before a LOCAL rule becomes a BOQ quantity, which is correct
here: the citation is what establishes that the site falls under this law.

---

## 2. What the sources state

### Confirmed — Saudipedia summary of the Law (opened 24 Sep 2026)

**Prior approval.** It is prohibited to manufacture, import, sell, install, operate or maintain
surveillance cameras *"without prior approval from the Ministry of Interior."*

**Premises within scope.** Ministries, public institutions, power and desalination plants, oil
facilities, commercial complexes, residential buildings, banks, the Grand Mosque and the Prophet's
Mosque, mosques, entertainment venues, stadiums, hospitals, highways, schools, fuel stations,
public transport, restaurants, museums, and *"any other location or facility the Ministry of
Interior deems necessary."*

**Prohibited camera locations.** Medical operating rooms, medical examination rooms, changing
rooms, restrooms, women's salons, private spaces, and residential units in tourist accommodation.

**Recording integrity.** Recordings must be retained and *"remain unaltered in the event of a
report on a specific incident, until the completion of investigation procedures."*

**Disclosure.** Transferring or publishing recordings is prohibited except with Ministry approval,
a court order, or an investigative authority request.

**Penalties.** SAR 500 per non-compliant camera · SAR 1,000 per improperly installed camera ·
up to SAR 5,000 for failing to retain recordings · up to SAR 20,000 for unlawful transfer or
publication, or destruction of equipment. Appeals within 60 days.

### Not confirmed — the technical specification

The **90-day retention period** and the **HD-or-higher resolution** requirement are reported
consistently across secondary sources (law-firm briefings, integrator and news sites) and the
SAR 5,000 penalty is described as applying to a failure to keep 90 days of recordings. **Neither
figure was read in an official document.**

Retention is the single most commercially significant number in this file — it sets NVR and
storage sizing, and therefore a large part of the CCTV BOQ. A wrong retention figure is a wrong
storage quotation. `KSA-CCTV-04` and `KSA-CCTV-06` are therefore seeded with
`source_verified = false` and a note naming what must be obtained.

**What to obtain, in order of authority:**

1. **Ministerial Decision No. 22688/1444** — the Implementing Regulation and the *Security
   Conditions and Requirements Document*. This is the operative technical instrument.
2. The MOI **general technical specifications for security surveillance camera systems**, issued
   alongside the executive regulations.
3. The Arabic *وثيقة الشروط - كاميرات المراقبة الأمنية* (2024) MOII conditions document.

### Sources tried

| Source | Status | Used for |
|---|---|---|
| [Saudipedia: Law of the Use of Security Surveillance Cameras](https://saudipedia.com/en/law-of-the-use-of-security-surveillance-cameras-in-saudi-arabia) | Opened, usable | KSA-CCTV-01 … 05 |
| [Scribd: وثيقة الشروط كاميرات المراقبة الأمنية 2024 (MOII)](https://www.scribd.com/document/856218504/) | **Landing page only** — body not readable | Nothing |
| [NFPA list of codes and standards](https://www.nfpa.org/for-professionals/codes-and-standards/list-of-codes-and-standards) | **Returned no list** — client-rendered, header only | Nothing |
| [Lexis Middle East: Ministerial Decision 22688/1444](https://www.lexismiddleeast.com/law/SaudiArabia/MinisterialDecision_22688_1444/en) | Citation only (paywalled) | The official reference above |
| Secondary briefings (Ghazzawi Law Firm, Saudi Gazette, Arab News, CDIT, SAMA Rulebook) | Opened | 90-day retention and HD resolution, **unconfirmed** |

Two of the three links supplied resolved to nothing usable. The NFPA page failed the same way the
ELV guide already recorded it failing — the list is rendered client-side, so an automated fetch
returns the header alone. The NFPA edition question raised by rule X-01 is therefore **still
open**: confirm the editions the project SOW and the AHJ adopt, per X-01, rather than from a
website listing.

---

## 3. Interaction with the existing rules

- **C-07 (pixel density per task tier)** is SPEC and was added by the guide itself. Where the MOI
  technical specification sets a resolution floor, that floor is the binding requirement and C-07
  becomes the design method used to satisfy it. Resolve the two together, per X-01.
- **C-04 (segmentation and credential hygiene)** sits alongside the disclosure prohibition in
  `KSA-CCTV-05`: unlawful publication carries a SAR 20,000 penalty, which makes access control on
  the VMS a legal exposure and not only an IT-policy preference.
- **KSA-CCTV-03 (prohibited locations)** is a hard placement constraint and should be checked
  against the reflected ceiling plan and room schedule at design stage, in the same pass as B-04.
