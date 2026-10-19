# Part C — Security, CCTV and access control

**Source:** ELV & Telecom Installation Rule Guide Book, 21 Sep 2026, Part C.
See [the source record](../../standards-references/elv-telecom-installation-rule-guide/README.md)
for provenance, confidence tags and what is still unverified.

**Systems:** `cctv` (C-01, C-02, C-03, C-04, C-07) and `acs` (C-05, C-06)
**Rule codes:** `ELV-C-01` … `ELV-C-07`
The access-control rules are cross-referenced from
[`access-control/rules/elv-guide-part-c.md`](../../access-control/rules/elv-guide-part-c.md);
C-02 to C-04 also belong to [`cctv/network/`](../network/) as PoE and segmentation rules.

> **This is the weakest-sourced Part.** The Scope Fire case study shows a CCTV and graded intruder
> alarm project (Brookhouse Aerospace) but says nothing about conduit, VLANs, OSDP or PoE, and the
> Eureka PatSnap article has no CCTV content at all. Treat the case-study bullets as project
> practice, not codes.

| ID | Rule | Tag | Basis and note |
|---|---|---|---|
| C-01 | Protect outdoor and perimeter camera cabling from tampering: outdoor-rated cable, sealed entries, and high-impact metallic conduit **where the risk assessment or SOW calls for it**. | SPEC | Not a code rule. Metallic conduit is a security-risk decision; if it is not on the drawings or in the SOW, do not price it. |
| C-02 | Size PoE from the switch budget down: add up the maximum power each port can supply to its device (802.3af, at or bt class), then compare with the switch total budget **with headroom**. | CODE | IEEE 802.3 gives the class limits. A common design margin is 20 percent, which is SPEC not CODE. Thermal PTZ heads and IR illuminators often need at or bt class — do not assume af. |
| C-03 | For PoE loads, check cable bundle temperature rise and switch and enclosure heat dissipation, especially in bundled or conduit runs. | CODE | TIA TSB-184-A covers current-carrying limits for bundled cables. Add to the certification record when high-power devices are used. Reference is from general knowledge and unconfirmed. |
| C-04 | Put physical security devices on their own VLAN, restrict routing to the VMS and controllers, disable unused ports and services, and change every default credential before handover. | SPEC | Network security practice, not a cabling code. Follow the client IT security policy if one exists. |
| C-05 | Connect card readers to controllers over **OSDP with Secure Channel switched on**, not Wiegand, where the controller and readers support it. | SPEC | SIA: OSDP Secure Channel uses AES-128 encryption and supervised wiring; published as IEC 60839-11-5:2020, current version 2.2.2. |
| C-06 | Set door hardware failure mode (fail-safe or fail-secure) from the egress and fire strategy, and link it to fire alarm release. | CODE | Same requirement as B-09. Drawings must state which doors are which. |
| C-07 | Design camera views to the required **pixel density** for the task (detect, observe, recognise, identify) and record it per camera. | SPEC | Added by the guide, not from the case studies. IEC 62676-4 defines the tiers; ask the client which tier each area needs. |

## NSI Gold and UL 294 are not installation rules

NSI Gold is a UK inspectorate approval for installers; UL 294 is a US safety and performance
listing for access control equipment. Both are **LOCAL**: evidence that a vendor or installer is
approved in that country, not a requirement on a Saudi or GCC site unless the SOW names them.
Neither is encoded as a rule.

## Inspection checklist (liftable into an ITP)

- [ ] Cable route and protection for every outdoor camera matches the drawings
- [ ] PoE budget sheet per switch signed off, with headroom
- [ ] Security VLAN, port lockdown and credential change recorded per switch
- [ ] OSDP Secure Channel confirmed **active** on each reader, not only supported
- [ ] Door failure modes match the schedule and the fire cause-and-effect matrix
- [ ] Camera views tested against the agreed pixel-density tier
