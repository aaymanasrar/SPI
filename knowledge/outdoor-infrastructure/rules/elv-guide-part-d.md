# Part D — Outdoor infrastructure and mast siting

**Source:** ELV & Telecom Installation Rule Guide Book, 21 Sep 2026, Part D.
See [the source record](../../standards-references/elv-telecom-installation-rule-guide/README.md)
for provenance, confidence tags and what is still unverified.

**System:** `outdoor_infrastructure` · **Rule codes:** `ELV-D-01` … `ELV-D-06`

> **Almost every rule here is LOCAL, and all of it is Nigerian.** The only hard number in the
> sources is a 5 m generator setback from a 2009 Nigerian regulator guideline. Use this Part as a
> checklist of what to look up for a site, **not** as a source of numbers. The guide also notes
> Part D is probably outside a typical Saudi ICT and ELV bid.

| ID | Rule | Tag | Basis and note |
|---|---|---|---|
| D-01 | Mast setbacks from homes, schools and high-voltage lines are set by the local regulator and municipality. **Obtain the figure in writing before design.** | LOCAL | The Mubi study finds operators often ignore the national minimum setback, so the rule exists but is widely broken. It gives no universal distance. |
| D-02 | Place a backup generator at least **5 m** from the neighbouring property line, not counting fences. | LOCAL | **Nigeria only:** section 3(5) of the 2009 NCC Guidelines on Technical Specifications for Masts and Towers, quoted in the Harlem Solicitors case analysis. |
| D-03 | Generators must be sound-proofed and mounted on shock absorbers to keep vibration to a minimum. | LOCAL | Same 2009 NCC guideline. Directing exhaust away from neighbours is good practice but is not stated in the sources. |
| D-04 | Keep noise within the residential limit set by the environmental regulator. | LOCAL | The court in the Helios case noted Nigerian limits of **50 dB by day and 35 dB by night** for residential areas. Find the equivalent regulator and limit for the country you build in. |
| D-05 | Show that RF exposure at accessible locations is within the national limit, and mark and fence any area above it. | LOCAL | Most regulators base limits on ICNIRP guidelines, but each regulator issues its own. In Saudi Arabia, CST cites its own Regulation on Exposure to EMF — get that document, not a summary. |
| D-06 | Keep an as-built **distance survey** and a **noise measurement record** for every generator and mast. | SPEC | The practical lesson from the case: the Court of Appeal ruled for the tower company because the neighbour could not prove the distance or that noise exceeded the limit. Your own records are the defence. |

**Two cautions on the supplied links.** The Taylor & Francis paper refused automated access
(HTTP 403), so its abstract is unchecked. The Judy Legal record is behind a login and shows only
that the trial court first found for the claimant; the Court of Appeal outcome comes from the
Harlem Solicitors article, not from the court record.

## Inspection checklist (liftable into an ITP)

- [ ] Setback distances obtained in writing from the municipality and telecom regulator
- [ ] Generator position surveyed and measured from the property line
- [ ] Generator acoustic enclosure and anti-vibration mounts fitted
- [ ] Noise reading taken at the boundary and filed
- [ ] RF exposure assessment and warning signs on file where required
