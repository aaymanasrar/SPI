# Walkthrough viewer

The 3D walkthrough page: rooms extruded from a drawing, furnished by room type,
with ELV devices placed at coordinates and heights that each carry the rule they
came from.

## Parts

| File | What it holds |
|---|---|
| `head.html` | title, Google Fonts link, the whole stylesheet and its theme tokens |
| `body.html` | the canvas and the instrument rail |
| `build1.js` | palette, finishes, and the furniture builders |
| `build2.js` | the ELV devices, modelled as the real products |
| `build3.js` | floors, walls with door and window openings, interior fit-out |
| `build4.js` | device placement, markers, coverage, camera modes, the rail |

They are separate files because one 1,000-line page is unreviewable. They are
concatenated at build time because an Artifact is a single HTML file.

## Building

```sh
cd engines && PYTHONPATH=$PWD ./.venv/bin/python fixtures/build_kg_scene.py
viewer/build.sh
```

The first command runs the real engine tools over the floor plan and writes
`out/walkthrough/kg.json`. The second assembles the page and refuses to finish
if any inline script fails to parse or references an element id that is not in
the markup.

`out/` is gitignored. Everything there is regenerable from this directory and
`engines/fixtures/`, so nothing generated is committed.

## What the page is honest about

The rail states, on the page itself and not only here: the devices are proposals
rather than a design, the plan is traced from a raster image, the drawing's own
vertical chains disagree by 2.16 m, the ceiling height is assumed, and the
furniture is indicative with no quantities. CCTV, access control and data are
absent because none are drawn and no rule says where they go.
