# ELV building simulator

A page that loads a building from its IFC model — the one Revit exports — and
lets an engineer walk it, check device coverage against the rules library, try
what-ifs, and run a fire-drill sequence.

## Building

```sh
simulator/build.sh                        # the Revit-style fixture office
simulator/build.sh model.ifc              # any IFC (Revit: File → Export → IFC)
simulator/build.sh model.ifc map.json     # with the project's element map
```

Writes `out/simulator/<model>-simulator.html`, one self-contained file. It runs
the real `bim.scene_3d` tool, so what the page shows is what the engine read.
The page can also open any scene JSON made with
`python -m craft.bim scene model.ifc --out scene.json` (run from `engines/`),
from its panel or by dropping the file on it.

Without an element map, only IFC's standard device types are counted; Revit
families exported as proxies are listed under "Not counted" until a rule maps
them (`engines/fixtures/spt_element_map.json` shows the shape).

## Parts

| File | What it holds |
|---|---|
| `head.html`, `body.html` | stylesheet with light/dark tokens, and the markup |
| `sim/00-core.js` | state, settings and where each value came from, geometry helpers |
| `sim/10-render.js` | three.js scene, 3D / plan / walk views, picking, labels |
| `sim/20-analysis.js` | coverage checks and the what-if proposals |
| `sim/30-drill.js` | the fire-drill sequence |
| `sim/40-ui.js` | the panel, inspector, scene loading |
| `rules.py` | copies the applied rules out of migration 0017 and checks them |
| `build.sh` | assembles and checks the page |

## What it checks

| Check | Rule | From the model | Entered by a person |
|---|---|---|---|
| Smoke detection | SPT-FA-01, SPT-FA-02: every ceiling point ≤ 0.7 × S from a detector | detector positions, room outlines | S if not 9.1 m |
| Heat detection | SPT-FA-04: listed spacing × ceiling-height factor | room heights | listed spacing |
| CCTV | SPT-CC-01 DORI px/m, SPT-CC-03 max distance, SPT-CC-09 face height | camera positions and heights | resolution, field of view, aim |
| Sounders | SPT-FA-13: ≥ max(avg + 15, max + 5) dBA at 1.5 m, ≤ 110 | sounder positions | output at 1 m, ambient levels, wall loss |

A room is checked against the devices in it; detection and sight do not pass
through walls. Sound may, if enabled with a wall loss.

The fire drill is a sequence, not a fire model: smoke spreads across the room of
origin at an entered speed, detectors in that room alarm, the panel starts the
sounders in the chosen scope. It exists to show the order of events and the
gaps (a room with no detector, a floor with no sounder).

## What it is honest about

- Values not in the model or a rule start empty. "Use illustrative values" fills
  them, and every result computed from one is labelled.
- A camera's aim is not in IFC; it starts along the family's X axis and the page
  says so.
- Proposals made in the page are exported as proposals, never as quantities.
- The fixture office is not a project. Its open-plan office is one detector
  short and its meeting room has none, so the checks have something to find.
