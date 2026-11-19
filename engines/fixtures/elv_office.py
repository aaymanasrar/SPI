"""The fixture office's ground floor (floor_plans.py) with ELV devices drawn on it.

Not a project. The layout is deliberately imperfect, so a review has something
to find: one smoke detector per small room, a heat detector in the kitchen,
two data outlets per office, two sounder-strobes for the whole floor, three
cameras, two card readers and two fire dampers no symbol map knows.

    python fixtures/elv_office.py out.dxf
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import ezdxf

sys.path.insert(0, str(Path(__file__).parent))
from floor_plans import LEVELS, build_dxf  # noqa: E402

DEVICE_LAYERS = ["E-FIRE", "E-SEC", "M-HVAC"]


def elv_ground_floor_dxf() -> bytes:
    doc = ezdxf.read(io.StringIO(build_dxf("Ground floor").decode()))
    for layer in ("A-AREA", "E-FIRE", "E-SEC", "M-HVAC"):
        doc.layers.add(layer)
    for b in ("SMOKE-DETECTOR", "HEAT-DETECTOR", "CALL-POINT", "SOUNDER-STROBE", "DOME-CAMERA",
              "CARD-READER", "DATA-OUTLET", "FD"):
        doc.blocks.new(b).add_circle((0, 0), 150)
    m = doc.modelspace()
    for name, x0, y0, x1, y1 in LEVELS["Ground floor"]["rooms"]:
        m.add_lwpolyline([(x0 * 1000, y0 * 1000), (x1 * 1000, y0 * 1000), (x1 * 1000, y1 * 1000),
                          (x0 * 1000, y1 * 1000)], close=True, dxfattribs={"layer": "A-AREA"})
        det = "HEAT-DETECTOR" if name == "Kitchen" else "SMOKE-DETECTOR"
        w = x1 - x0
        k = 1 if w < 7 else 2
        for i in range(k):
            m.add_blockref(det, ((x0 + w * (i + 1) / (k + 1)) * 1000, (y0 + (y1 - y0) * 0.7) * 1000),
                           dxfattribs={"layer": "E-FIRE"})
        if name.startswith("Office") or name == "Meeting":
            m.add_blockref("DATA-OUTLET", ((x0 + 0.4) * 1000, (y0 + 0.4) * 1000), dxfattribs={"layer": "E-SEC"})
            m.add_blockref("DATA-OUTLET", ((x1 - 0.4) * 1000, (y0 + 0.4) * 1000), dxfattribs={"layer": "E-SEC"})
    for x, y in ((3200, 300), (19600, 7000)):
        m.add_blockref("CALL-POINT", (x, y), dxfattribs={"layer": "E-FIRE"})
    for x in (5000, 15000):
        m.add_blockref("SOUNDER-STROBE", (x, 7000), dxfattribs={"layer": "E-FIRE"})
    for x, y in ((600, 600), (10000, 7300), (19400, 600)):
        m.add_blockref("DOME-CAMERA", (x, y), dxfattribs={"layer": "E-SEC"})
    for x, y in ((4600, 600), (11600, 6400)):
        m.add_blockref("CARD-READER", (x, y), dxfattribs={"layer": "E-SEC"})
    for x in (4000, 16000):
        m.add_blockref("FD", (x, 11500), dxfattribs={"layer": "M-HVAC"})
    out = io.StringIO()
    doc.write(out)
    return out.getvalue().encode("utf-8")


if __name__ == "__main__":
    Path(sys.argv[1]).write_bytes(elv_ground_floor_dxf())
