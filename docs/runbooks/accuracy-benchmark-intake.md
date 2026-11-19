# Intake checklist — the accuracy benchmark

The benchmark is built (`engines/validate_project.py`) and every step runs. It
has **never been run against a real project**, so there is no measurement of
accuracy and none may be claimed. It refuses to run on invented inputs by
design: a synthetic drawing with a synthetic answer proves the harness works and
says nothing about the engine.

What follows is everything needed to close that. One floor is enough to start.

## Required

- [ ] **1. The original DXF** for one floor.
      Not a PDF, not a screenshot. ASCII DXF, or DWG converted upstream — there
      is no DWG reader because the usual one (ODA SDK) is not licence
      compatible.
      *Why:* a raster is traced, and tracing is where the 2.16 m chain conflict
      on the kindergarten sheet became unresolvable.
- [ ] **2. The BOQ an engineer issued for that same floor and revision.**
      CSV with `device_type,quantity` is enough to start; the issued workbook is
      better. **It must be the same revision as the DXF.** A BOQ from Rev 03
      against a Rev 05 drawing measures the revision gap, not the engine.
- [ ] **3. The legend sheet** for that drawing, so blocks can be mapped.
      *Why:* `SD` is a smoke detector on a fire alarm layer and a smoke damper
      on a mechanical one. The default map refuses 16 such codes rather than
      guess.
- [ ] **4. The layer names** holding room outlines and room name text.
      *Why:* there is no reliable convention, and guessing which layer is
      architectural is how a corridor becomes a room.

## Needed for anything beyond counting

- [ ] **5. Ceiling heights** from the sections or RCP, per area if they vary.
      Without this every ceiling device sits at an assumed height and carries an
      `ASSUMED-CEILING-HEIGHT` finding.
- [ ] **6. The specification clauses** that governed the design — the standard,
      edition and jurisdiction.
      *Why:* the rules library holds NFPA 72, BS 5839-1 and Saudi practice, and
      they disagree. Checking against the wrong one measures nothing.
- [ ] **7. Obstructions** — columns, beams, bulkheads, diffusers — if placement
      accuracy is to be judged rather than counting accuracy.
- [ ] **8. Which rooms were deliberately excluded** from each system, and why.
      An engineer's exclusion is not an engine error, and without the list it
      reads as one.

## Useful but not blocking

- [ ] **9.** The approved product list and prices used on that BOQ, to test
      pricing provenance rather than only quantities.
- [ ] **10.** A second floor or project, to tell a general result from a
      coincidence.

## Running it

```sh
cd engines
PYTHONPATH=$PWD ./.venv/bin/python validate_project.py --config project.json
```

`project.json` is documented in the module docstring. Every engineering figure
in it comes from you; the harness holds none.

## What it reports

Four classes, kept apart and never netted off, because a net difference of zero
can hide a device type invented against another missed:

| Class | Meaning |
|---|---|
| matched exactly | engine quantity equals the issued quantity |
| quantity discrepancies | both present, different numbers |
| false positives | engine produced it, the engineer did not |
| false negatives | the engineer issued it, the engine missed it |

plus unresolved items (unmapped symbols, missing mounting heights, open BOQ
lines) counted separately again.

A blocker finding — a dimension conflict, a drawing that contradicts itself —
fails the run regardless of the quantities. A number produced from a drawing
that cannot be trusted is not evidence of accuracy either way.
