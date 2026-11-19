# 0002 — Revit models are read as IFC, by our own reader

Status: accepted · Date: 2026-11-10 · Supersedes: nothing

## Context

Consultants increasingly issue Revit models instead of, or as well as, DWG/DXF
drawings. A model already holds what CADCraft has to reconstruct from linework:
which storey a device is on, how high it is mounted, the room it serves, and
the room's outline and height.

## Decision

**Read IFC, not `.rvt`.** A fifth engine, BIMCraft (`engines/craft/bim/`), reads
IFC2X3, IFC4 and IFC4X3 — the ISO 16739 exchange format that Revit exports
natively (File → Export → IFC), as does every other BIM tool.

`.rvt` is not read and is not reverse-engineered:

1. **It is undocumented and unstable.** An `.rvt` is an OLE compound file of
   compressed, version-specific streams. Autodesk publishes no specification and
   the layout changes with each annual release; a reader built from observation
   breaks every year and is wrong silently in between.
2. **The licence terms.** Autodesk's licence prohibits reverse engineering its
   software and formats. The only third-party reader is the ODA SDK, which the
   licence policy already forbids (D-8).
3. **IFC carries what the tools need.** Classes, predefined types, family and
   type names, storeys, rooms, placements and quantities are all in a
   default IFC export.

An uploaded `.rvt` is recognised by its OLE signature and refused with the
export instructions, rather than reported as an unreadable file.

**Our own STEP reader, not IfcOpenShell.** IfcOpenShell is LGPL-3.0, which
`scripts/check-licenses` treats as forbidden (0001). The tools read attributes,
relationships and simple extrusions, never boolean or brep geometry, so the
reader is a few hundred lines (`bim/step.py`, `bim/geometry.py`) with no new
dependency. If brep geometry is ever needed, LGPL-as-separate-process is the
decision to revisit, not a fuller hand-written kernel.

### What the reader does about Revit's habits

Each one is covered by `engines/tests/test_bim.py` and was found in a real
Revit 2021 export:

| Habit | Handling |
|---|---|
| FILE_NAME header names the exporter add-in, never "Revit" | Authoring tool read from `IfcApplication` |
| Family exported with placement at the origin, location in the geometry (22 of 116 elements in the sample) | Insertion point taken from the mapped-item transform or extrusion; `position_basis: "geometry"` and an info finding |
| An own offset of (0, 0, −elevation) cancelling the storey | Origin test done in world coordinates, not on the own offset |
| Devices contained in the storey, not the room | Room found by outline and height; `space_basis: "located"` |
| Devices exported as `IfcBuildingElementProxy` or `USERDEFINED` | Not guessed: `missing_data` until a family-name rule maps them |
| Detectors in IFC2X3 as `IfcDistributionControlElement` | Identified through their `IfcSensorType` |
| Non-ASCII names as `\X2\` escapes | Decoded |
| Elevations of `-0.0` | Normalised |

### Element mapping is data

The CAD rule applies unchanged: a family name is a project convention, so the
mapping from family to device type is an `ElementMap` with a required
`source_document`. The shipped default maps only IFC's standard predefined
types (IfcSensor SMOKESENSOR, IfcAlarm MANUALPULLBOX, …) and interprets no
family name.

### The simulator

`simulator/` builds a page from `bim.scene_3d`: the model in 3D, coverage
checks, and a fire-drill sequence. Every number it applies comes from a rule in
the rules library (SPT-FA-01/02/04/13/15, SPT-CC-01/03/09); `simulator/rules.py`
copies the rule text into the page and stops the build if the text no longer
states the value the page uses. Values that are in neither the model nor a rule
— sounder output, ambient levels, smoke spread — start empty and are entered by
a person; an explicit "illustrative values" button fills them, and every result
computed from one says so.

## Alternatives rejected

| Option | Why not |
|---|---|
| Reverse-engineer `.rvt` | Undocumented, changes yearly, prohibited by the licence (above) |
| ODA SDK / Teigha BIM | Forbidden by the licence policy (D-8) |
| IfcOpenShell | LGPL-3.0, forbidden unless the policy changes |
| Autodesk Platform Services (Model Derivative API) | Sends client models to a third-party cloud and bills per conversion; a reasonable later option for clients who cannot export IFC themselves |
| A Revit add-in exporting JSON | Needs a Revit licence on the machine that runs it; IFC export already exists in every copy of Revit |
