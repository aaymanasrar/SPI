# Saudi security surveillance camera law — CCTV rules

**Source:** Law of the Use of Security Surveillance Cameras (Royal Decree, 3 Oct 2022) and
Ministerial Decision No. 22688/1444. See
[the source record](../../standards-references/saudi-security-camera-law/README.md) for what was
and was not confirmed.

**System:** `cctv` · **Jurisdiction:** `SA` · **Rule codes:** `KSA-CCTV-01` … `KSA-CCTV-06`

> **LOCAL means jurisdiction-bound, not weak.** On a Saudi site these are statutory and carry
> per-camera fines. Outside Saudi Arabia they do not apply at all. The X-06 gate still asks for a
> citation before one becomes a BOQ quantity — here, the citation is what establishes that the
> site falls under this law.

| ID | Rule | Tag | Basis and note |
|---|---|---|---|
| KSA-CCTV-01 | Obtain **prior Ministry of Interior approval** before manufacturing, importing, selling, installing, operating or maintaining a security surveillance camera system. | LOCAL | Law of the Use of Security Surveillance Cameras. Approval is a precondition to the work, not a handover document. Penalties: SAR 500 per non-compliant camera, SAR 1,000 per improperly installed camera. |
| KSA-CCTV-02 | Confirm whether the premises fall within the **mandatory installation classes** before scoping: ministries and public institutions, power and desalination plants, oil facilities, commercial complexes, residential buildings, banks, the Two Holy Mosques and mosques, entertainment venues, stadiums, hospitals, highways, schools, fuel stations, public transport, restaurants, museums, and any other facility the MOI deems necessary. | LOCAL | The list is broad enough that most SmartPage project types fall inside it. Confirm per project rather than assuming either way. |
| KSA-CCTV-03 | **Do not place a camera** in a medical operating room, medical examination room, changing room, restroom, women's salon, any private space, or a residential unit in tourist accommodation. | LOCAL | A hard placement constraint. Check against the room schedule and reflected ceiling plan at design stage, in the same pass as B-04. A camera in one of these rooms is unlawful regardless of client instruction. |
| KSA-CCTV-04 | Retain recordings for the required period — **reported as 90 days** — and preserve them **unaltered** where an incident has been reported, until investigation procedures complete. | LOCAL | The unaltered-pending-investigation duty is confirmed. The **90-day figure is from secondary sources only** and has not been read in an official document. Retention drives NVR and storage sizing, so confirm it against Ministerial Decision 22688/1444 before quoting storage. |
| KSA-CCTV-05 | **Do not transfer or publish** recordings except with Ministry approval, a court order, or an investigative authority request. Reflect this in VMS access control and the credential handover record. | LOCAL | Penalty up to SAR 20,000 for unlawful transfer or publication, or destruction of equipment. Makes C-04 a legal exposure, not only an IT-policy preference. |
| KSA-CCTV-06 | Meet the MOI **general technical specification** for camera systems — reported as **HD resolution or higher**. | LOCAL | **Unconfirmed.** Resolution floor reported by secondary sources only. Where the MOI specification sets a floor, that floor binds and C-07 (pixel density per task tier) is the method used to satisfy it, not an alternative to it. |

## Inspection checklist (liftable into an ITP)

- [ ] MOI approval obtained and on file **before** installation begins
- [ ] Premises class confirmed against the mandatory-installation list
- [ ] No camera placed in a prohibited location — signed off against the room schedule
- [ ] Retention period configured and evidenced on the recorder, with the source clause cited
- [ ] Incident-hold procedure documented (recordings preserved unaltered pending investigation)
- [ ] VMS export and publication permissions restricted, and the restriction recorded at handover
- [ ] Camera resolution verified against the MOI technical specification
