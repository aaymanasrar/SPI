# Part B — Fire detection and life safety (NFPA 72, BS 5839)

**Source:** ELV & Telecom Installation Rule Guide Book, 21 Sep 2026, Part B.
See [the source record](../../standards-references/elv-telecom-installation-rule-guide/README.md)
for provenance, confidence tags and what is still unverified.

**System:** `fire_alarm` · **Rule codes:** `ELV-B-01` … `ELV-B-11`

Eleven rules covering detector placement, aspirating detection, system category and the outputs a
fire alarm must drive.

> **Read this before quoting any number below.** The Scope Fire case studies confirm the projects
> (a BS 5839-1 takeover, an L1 new build, aspirating detection in a factory) but state **none** of
> these figures. Every number here comes from NFPA 72 or BS 5839 as recalled, not from an opened
> copy of the current edition. B-07 in particular is flagged by the guide's own author as
> approximate. Confirm against a licensed copy before this reaches a client.

| ID | Rule | Tag | Basis and note |
|---|---|---|---|
| B-01 | Smooth flat ceiling: space smoke detectors no more than **30 ft (9.1 m)** apart, with a wall distance of no more than half the listed spacing (**15 ft / 4.6 m**). | CODE | NFPA 72, per the EngineersUniverse spacing guide. Always use the spacing on the detector listing if it is smaller. |
| B-02 | Heat detectors: use the listed spacing (**50 ft / 15 m** on smooth ceilings up to 10 ft high) and reduce it as ceiling height rises. | CODE | NFPA 72, same source. At a 20 ft ceiling, fixed-temperature detectors need roughly **0.7 ×** the listed spacing. |
| B-03 | Keep every detector at least **3 ft (0.9 m)** from an air supply diffuser. | CODE | Matches the case-study figure. Smoke dilution delays detection. |
| B-04 | Ceiling height, beams, joists, partitions and airflow change the layout. Redo spacing whenever the reflected ceiling plan shows a beam, joist, partition or diffuser that changes coverage. | CODE | NFPA 72 Chapter 17. Check the reflected ceiling plan and HVAC drawings before fixing detector positions. |
| B-05 | Use **aspirating (ASD)** detection where high airflow, tall ceilings, hidden spaces or very early warning is required by the design brief. Size the pipe network with the manufacturer's calculation software and keep it within the maximum smoke transport time. | SPEC | Listed ASD equipment is recognised by NFPA 72 and EN 54-20. VESDA is one manufacturer's brand — say *aspirating smoke detection* in the BOQ unless the SOW names a brand. |
| B-06 | Fix the BS 5839-1 **system category** (L1, L2, L3, L4, L5, P1, P2 or M) in the design brief **before** counting detectors. L1 covers all areas, L2 covers defined risk areas. | CODE | BS 5839-1. Silentnight and Real Food Hall are both BS 5839-1 projects in the Scope Fire pages. |
| B-07 | Under BS 5839-1 use the coverage radius for each detector type: about **7.5 m for smoke** and **5.3 m for heat** on normal ceilings. | CODE | **Approximate, from memory of the standard.** Confirm in the current edition before use. |
| B-08 | Shut down or control air handling units automatically on the fire alarm signal, using the arrangement the mechanical design specifies. | CODE | NFPA 90A and NFPA 72 control functions. Shows as an output on the FACP and a relay or module in the point list. |
| B-09 | Electromagnetic locks on egress doors must release on a fire alarm signal **and** on loss of power. | CODE | NFPA 101 and the local building code. The case study calls this a mandatory fail-safe linkage. |
| B-10 | Provide emergency voice evacuation where the building class or fire strategy requires it, with speech intelligibility tested on completion. | CODE | NFPA 72 Chapter 24. Not every building needs it, so tie it to the fire strategy. |
| B-11 | Test **100 percent** of devices at acceptance and keep the test record. Arrange monitoring of the panel to a receiving point as the fire strategy requires. | SPEC | NFPA 72 Chapter 14 sets testing. The Silentnight case study cites 24/7 monitoring. |

## Inspection checklist (liftable into an ITP)

- [ ] Design brief states the system category or NFPA occupancy class
- [ ] Detector spacing checked against diffusers, beams and partitions on the reflected ceiling plan
- [ ] Every detector at least 0.9 m from supply diffusers
- [ ] Cause-and-effect matrix lists AHU, door release, lifts and voice alarm outputs
- [ ] Maglock release tested on alarm and on power loss
- [ ] Aspirating pipe network calculation and transport time recorded
- [ ] 100 percent device test sheet signed and filed
