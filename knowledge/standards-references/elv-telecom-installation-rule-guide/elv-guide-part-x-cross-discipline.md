# Part X — Cross-discipline rules and handover pack

**Source:** ELV & Telecom Installation Rule Guide Book, 21 Sep 2026, Section 6.
Provenance: [source record](./README.md).

**System:** none — these apply to every system on a project, and are encoded with
`engineering_rules.system_id = null`. **Rule codes:** `ELV-X-01` … `ELV-X-06`

Six rules, each sitting at an interface between trades.

| ID | Rule | Tag | Basis and note |
|---|---|---|---|
| X-01 | Confirm the adopted code editions and any client standards with the **authority having jurisdiction** and the SOW before design, and record them on the first page of the design basis. | CODE | Tailwind tells installers to confirm requirements with the AHJ before starting work. |
| X-02 | Coordinate pathways with electrical, HVAC, plumbing and fire systems **before first fix**. Route low-voltage cabling through the wall or ceiling while it is open, not as surface trunking afterwards. | SPEC | Practice described in the Voltiq office cabling case study. |
| X-03 | Keep **one cause-and-effect matrix** for every system that talks to the fire alarm: AHUs, door locks, lifts, voice alarm, CCTV call-up. Test each line at acceptance. | CODE | Ties together B-08, B-09, B-10 and C-06. A line that is not tested is an output nobody has proven. |
| X-04 | Keep a **firestop log**: location, assembly rating, product and installer for every sealed penetration. | CODE | Supports A-06. Needed to close out the fire authority inspection. |
| X-05 | Give each shared network element (switch, PoE budget, VLAN, IP range) a **named owner and one schedule**. | SPEC | Supports C-02 to C-04. Avoids two trades sizing the same switch. |
| X-06 | Every rule used in a BOQ, TBE or method statement must **carry its tag** and **cite the drawing or SOW clause** that makes it a scope item. SPEC and LOCAL rules are not scope by themselves. | SPEC | Applies SmartPage's BOQ traceability requirement to this guide. |

## X-06 is enforced, not advisory

X-06 is the rule that makes the other 41 safe to hold in a database. It is implemented in
migration `0014_rule_provenance_and_scope_gate.sql`:

- `engineering_rules.confidence` stores the tag (`code` / `spec` / `local`) and is **not null** —
  a rule with no tag cannot be represented.
- `forbid_unsupported_scope()` fires when a BOQ moves to `validated`, `approved` or `issued`. If
  any BOQ item's quantity traces back through `rule_executions` to a `spec` or `local` rule, that
  item must carry a `boq_item_sources` row of type `sow_clause`, `drawing` or `client_standard`.
  Otherwise the transition is rejected and the offending items are named in the error.

## Handover pack contents

- Copper and fibre certification results in the tester's native format, plus the PDF summary
- Fire alarm device test record, cause-and-effect matrix and aspirating pipe calculation
- Firestop log and photographs
- PoE budget sheet, IP and VLAN schedule, and credential handover record
- Door schedule with failure mode and release tests
- As-built drawings with cable IDs matching the labels
- Generator distance survey and noise record, where Part D applies
