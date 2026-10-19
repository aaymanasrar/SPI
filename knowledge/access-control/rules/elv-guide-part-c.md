# Part C (access control subset) — reader encryption and door failure mode

**Source:** ELV & Telecom Installation Rule Guide Book, 21 Sep 2026, Part C.
Full Part C text, including the CCTV and network rules, lives in
[`cctv/rules/elv-guide-part-c.md`](../../cctv/rules/elv-guide-part-c.md).
Provenance: [source record](../../standards-references/elv-telecom-installation-rule-guide/README.md).

**System:** `acs` · **Rule codes:** `ELV-C-05`, `ELV-C-06`

| ID | Rule | Tag | Basis and note |
|---|---|---|---|
| C-05 | Connect card readers to controllers over **OSDP with Secure Channel switched on**, not Wiegand, where the controller and readers support it. | SPEC | SIA: OSDP Secure Channel uses AES-128 encryption and supervised wiring; published as IEC 60839-11-5:2020, current version 2.2.2. |
| C-06 | Set door hardware failure mode (fail-safe or fail-secure) from the egress and fire strategy, and link it to fire alarm release. | CODE | Same requirement as B-09 (maglocks release on alarm and on power loss). Drawings must state which doors are which. |

**Life-safety interaction.** C-06 and B-09 are the same physical requirement approached from two
systems. Both are encoded, both point at the same cause-and-effect matrix (X-03), and a design
that satisfies one but not the other is a conflict the rules engine must surface rather than
resolve silently (ARCHITECTURE.md §9.3).

See also [`access-control/exceptions/`](../exceptions/) — free-egress overrides belong there once
SmartPage supplies them. None were supplied with this guide.
