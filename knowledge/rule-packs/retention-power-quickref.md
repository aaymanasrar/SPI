# Retention, power & network quick reference (Saudi)

Lookup table from *Saudi Project Practice* (SPT Pre-Sales, 29 Sep 2026). These are the
figures that size storage, batteries and links — the numbers that turn into money.

> **Retention is not one number.** It depends on the camera's role. A PTZ assessment camera
> keeps 30 days; a fixed gate surveillance camera keeps 90. Sizing every camera at the
> longest figure overprices the NVR; sizing at the shortest underdelivers.

> **Conflict, unresolved.** The 30-day and 60-day figures below come from Aramco/HCIS client
> standards. The Saudi Law of the Use of Security Surveillance Cameras carries a reported
> **90-day statutory floor** (rule KSA-CCTV-04). A client standard cannot reduce a statutory
> minimum. Before sizing storage, confirm (a) whether the premises fall under the camera law,
> and (b) the 90-day figure itself, which is still secondary-sourced.

---

## CCTV retention

| Item | Value | Source |
|---|---|---|
| IDAS perimeter surveillance & assessment | **60 days @1080p30 (alarm-associated)** | SAES-O-205 6.1.12 / SEC-05 5.5.3.4 |
| Gate surveillance (fixed) | **90 days** | SEC-05 5.3.10 / SAES-O-205 6.2.7 |
| Gate assessment (PTZ) | **30 days** | SEC-05 5.3.10 |
| Card-reader user camera | **90 days (2 s clip per swipe)** | SEC-05 5.3.9-5.3.10 |
| VASS fixed surveillance | **90 days (motion-triggered)** | SEC-05 5.7.7 |
| VASS assessment | **30 days** | SEC-05 5.7.7 |
| VASS alarm events | **90 days** | SEC-05 5.7.7 |
| Plant-ops CCTV (non-security) local | **>=72 h on VMS; longer -> archive** | SAES-T-555 7.1.7, 8.3 (2012) |

## Data retention

| Item | Value | Source |
|---|---|---|
| ACS central personnel & access data | **36 months online** | SEC-05 5.3.1.1 / SAES-O-205 6.2.1 |
| ID management (PIV) data | **5 years** | SEC-05 5.6.2 / SAES-O-205 6.6 |
| SCC voice recording | **12 months** | SAES-O-205 6.8.10 |

## Backup

| Item | Value | Source |
|---|---|---|
| Security system data | **Full <=30 days + daily incremental, off-site** | SEC-05 5.2.7 / SAES-O-205 5.5 |

## Camera spec

| Item | Value | Source |
|---|---|---|
| Optical | **1080p @30 fps (min 720p @7.5 fps non-alarm)** | SEC-05 5.8.1 |
| Thermal | **LWIR >=320x240 @30 fps** | SEC-05 5.8.1 |
| Housing | **IP66 or higher** | SEC-05 5.8.6 |

## Spare capacity

| Item | Value | Source |
|---|---|---|
| Security core systems | **20% CPU/RAM, 20% ports, 20% bandwidth, 50% disk** | SAES-O-205 5.1.4 |

## Availability

| Item | Value | Source |
|---|---|---|
| Security core components | **>=99.95% each** | SAES-O-205 5.1.2 |

## UPS

| Item | Value | Source |
|---|---|---|
| All HCIS security systems | **UPS + emergency generator (autonomy per SEC-07 - NOT RETRIEVED)** | SEC-05 5.2.10 |
| Hospital light-current systems | **>=30 min** | MOH design guide 2-6-12 |
| FACP batteries (NFPA) | **24 h standby + 5 min alarm (15 min EVACS)** | NFPA 72 10.6.7 (rule FA-18) |

## Generator

| Item | Value | Source |
|---|---|---|
| Hospital emergency | **>=3 h operation; loads +20%** | MOH design guide 2-6-7/8 |

## Network

| Item | Value | Source |
|---|---|---|
| CCTV on Aramco corporate uplink | **<=100 Mbps / 15% of core-facing BW** | SAES-T-555 6.1.4-6.1.6 (2012) |
| CCTV on leased remote-site link | **<=10% of link; >=20% free first** | SAES-T-555 6.1.8 (2012) |
| CCTV latency | **<200 ms** | SAES-T-555 6.2.1 (2012) |

---

## Source register

| Document | Issuer | Edition | How used | Currency |
|---|---|---|---|---|
| SAES-O-205 Security Systems for Industrial Facilities | Saudi Aramco | 22-Mar-2023 (next rev. 1-Jul-2025) | Read in full | Current as of copy; confirm latest |
| HCIS SEC-05 Security Systems at Industrial Facilities | HCIS / MOI | v2.0, 2-Apr-2017 | Read pp.1-31 | Latest known HCIS release |
| HCIS Security Directives index (SEC-01..12) | HCIS | 2017 | Index only | - |
| HCIS SEC complete - classes 1-4, application table | HCIS | 2017 | Summary | - |
| SAES-O-201 Application of Security Directives | Saudi Aramco | 10-Mar-2012 | Summary | Superseded wording likely - verify |
| SAES-O-204 Security Lighting | Saudi Aramco | 10-Mar-2012 | Summary | Verify current |
| SAES-T-555 IP Based CCTV | Saudi Aramco | 24-Jul-2012 | Read in full | OLD - newer revisions exist; use for method only |
| SAES-B-014 Safety Requirements for Plant & Ops Support Buildings | Saudi Aramco | 29-Feb-2004 | Summary | OLD - verify current clauses |
| SAES-M-100 Saudi Aramco Building Code | Saudi Aramco | (pdfcoffee copy) | Summary | Verify edition |
| SAES-T-916 Telecom Building Cable Systems | Saudi Aramco | 31-Dec-2003 | Summary | OLD - Cat5-era; verify current |
| SAES-T-624 Telecom OSP - Fiber Optics | Saudi Aramco | 3-Nov-2009 | Summary | Verify current |
| HCIS SAF Directives - Light & Non-Industrial | HCIS | 2017 | Keyword extract | - |
| HCIS SAF-01 General Requirements | HCIS | v2.0, 2-Apr-2017 | Summary | - |
| MOH Private Hospitals Design Guide (English) | Ministry of Health | (Scribd copy, undated) | Keyword extract | Verify current MOH edition |
| iHFG Part E - ELV & ICT systems | TAHPI (used in GCC) | current web | Summary | Guideline, not KSA law |
| SBC 801 Saudi Fire Protection Code | SBC National Committee | 2018 / 2024 | NOT RETRIEVED (site timed out) | Thresholds taken from IFC 2018 basis - verify |
| Not usable: Scribd 'LOW CURRENT SYSTEMS' (obfuscated font), SEC-07 & older SEC-05 copies (deleted), SAF-04 (blank) | - | - | Failed | - |

## Stated limitations

- Sources are client/authority standards (Aramco SAES, HCIS SEC/SAF, MOH), not contractor as-built BOQs - none usable were publicly available.
- Several public Aramco copies are old editions (SAES-T-555 2012, SAES-B-014 2004, SAES-T-916 2003) - verify against current controlled copies.
- SEC-07 (security power autonomy) and SBC 801 907.2 could not be retrieved.

**Three figures could not be retrieved at all:** SEC-07 / SAES-O-207 (security power
autonomy), SBC 801 §907.2 (the occupancy thresholds in LP-35 to LP-42 come from the IFC 2018
basis instead), and SAF-04. Anything depending on them is an open assumption.
