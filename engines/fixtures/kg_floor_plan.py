"""The KG building, traced from the supplied raster floor plan.

Overall width 23.00 m is printed on the drawing twice (top and bottom chains).
The vertical is NOT consistent on the drawing: the west chain reads 23.56 m and
the east chain 21.40 m, differing by exactly 2.16 m, which is the entrance band.
The west chain is used because it runs the full height in six segments matching
the six west rooms; the discrepancy is reported, not silently resolved.

Room positions are traced from a raster image, not read from a DXF. They are
faithful in arrangement and close in size; they are not survey dimensions.
"""
import io, json, ezdxf

W, H = 23.00, 23.56          # printed width; west vertical chain

# name, type, x0, y0, x1, y1   (metres, origin at south-west corner)
ROOMS = [
  # --- west strip, from the 4.23 / 4 / 4 / 4.99 / 2.16 / 4.18 chain ---
  ("OFFICE 4",          "office",      0.00,  0.00,  4.05,  4.18),
  ("AIR LOCK",          "lobby",       0.00,  4.18,  2.55,  6.34),
  ("RECEPTION",         "reception",   0.00,  6.34,  5.60, 11.33),
  ("OFFICE 3",          "office",      0.00, 11.33,  4.50, 15.33),
  ("OFFICE 2",          "office",      0.00, 15.33,  4.50, 19.33),
  ("OFFICE 1",          "office",      0.00, 19.33,  4.50, 23.56),
  # --- north strip, from the 4.5 / 3.67 / 3.06 / 3.06 / 3.54 / 1.98 chain ---
  ("KITCHENETTE",       "kitchenette", 4.50, 21.00,  8.17, 23.56),
  ("TOILET A",          "toilet",      8.90, 21.00, 11.96, 23.56),
  ("TOILET B",          "toilet",     11.96, 21.00, 15.02, 23.56),
  ("STORE RM N",        "store",      15.02, 21.00, 18.56, 23.56),
  ("ELEC. RM.",         "electrical", 18.56, 21.00, 21.00, 23.56),
  ("JAN. RM",           "janitor",    21.00, 19.60, 23.00, 23.56),
  # --- circulation ---
  ("CORRIDOR N",        "corridor",    4.50, 19.60, 21.00, 21.00),
  ("CORRIDOR W",        "corridor",    5.60, 11.33,  6.30, 19.60),
  # --- teaching block ---
  ("PRE SCHOOL CLASS 1","classroom",   6.30, 10.60, 13.60, 19.60),
  ("PRE SCHOOL CLASS 2","classroom",  14.30, 10.60, 21.30, 19.60),
  ("PRE SCHOOL CLASS 3","classroom",   6.30,  0.00, 13.60,  9.10),
  ("PRE SCHOOL CLASS 4","classroom",  14.30,  0.00, 21.30,  9.10),
  ("STORE RM C1",       "store",      13.60, 10.00, 16.40, 12.40),
  ("STORE RM C2",       "store",      13.60,  7.40, 16.40, 10.00),
]
# Children's WC cubicles: 4 on the west side of the block, 4 on the east.
for i in range(4):
    ROOMS.append((f"WC W{i+1}", "wc", 6.30, 9.10 + i*0.68 + 0.05, 7.55, 9.10 + i*0.68 + 0.63))
    ROOMS.append((f"WC E{i+1}", "wc", 21.30, 7.60 + i*0.78 + 0.05, 23.00, 7.60 + i*0.78 + 0.70))

# Openings: (kind, mark, x, y, width, facing)  facing: 'h' along X, 'v' along Y
DOORS = [
  ("D1", 21.30, 14.60, 1.10, "v"), ("D1", 21.30, 5.20, 1.10, "v"),
  ("D2", 4.50, 21.40, 0.90, "v"),  ("D2", 8.17, 22.20, 0.90, "v"),
  ("D2", 11.96, 22.20, 0.90, "v"), ("D2", 15.02, 22.20, 0.90, "v"),
  ("D2", 18.56, 22.20, 0.90, "v"), ("D2", 21.00, 21.80, 0.90, "v"),
  ("D2", 7.60, 19.60, 0.90, "h"),  ("D2", 15.60, 19.60, 0.90, "h"),
  ("D2", 13.60, 11.40, 0.90, "v"), ("D2", 16.40, 8.20, 0.90, "v"),
  ("D2", 9.80, 9.10, 0.90, "h"),   ("D2", 17.60, 9.10, 0.90, "h"),
  ("D2", 4.05, 2.60, 0.90, "v"),   ("D2", 4.50, 13.00, 0.90, "v"),
  ("D2", 4.50, 17.00, 0.90, "v"),  ("D2", 4.50, 20.60, 0.90, "v"),
  ("D3", 7.40, 23.56, 0.90, "h"),  ("D3", 21.60, 23.56, 0.90, "h"),
  ("DE", 0.00, 5.20, 1.20, "v"),
]
WINDOWS = [  # mark, x, y, width, facing
  ("W1", 0.00, 2.10, 1.88, "v"), ("W1", 0.00, 8.80, 1.88, "v"),
  ("W1", 0.00, 13.30, 1.88, "v"), ("W1", 0.00, 17.30, 1.88, "v"),
  ("W1", 0.00, 21.40, 1.88, "v"),
  ("W1", 2.20, 23.56, 1.88, "h"), ("W6", 6.30, 23.56, 1.65, "h"),
  ("W4", 10.40, 23.56, 0.60, "h"), ("W4", 13.00, 23.56, 0.60, "h"),
  ("W5", 16.80, 23.56, 1.00, "h"),
  ("W1", 23.00, 14.60, 1.88, "v"), ("W5", 23.00, 11.80, 1.03, "v"),
  ("W5", 23.00, 6.60, 1.03, "v"), ("W1", 23.00, 2.10, 1.88, "v"),
  ("W1", 2.20, 0.00, 1.88, "h"), ("W5", 5.10, 0.00, 1.00, "h"),
  ("W1", 7.60, 0.00, 1.88, "h"), ("W1", 10.40, 0.00, 1.88, "h"),
  ("W1", 16.00, 0.00, 1.88, "h"), ("W1", 19.30, 0.00, 1.88, "h"),
]

def build_dxf(path):
    d = ezdxf.new("R2010", setup=True); d.header["$INSUNITS"] = 6   # metres
    for l in ("ROOM-BOUNDARY", "ROOM-NAMES"):
        d.layers.add(l)
    m = d.modelspace()
    for name, _t, x0, y0, x1, y1 in ROOMS:
        m.add_lwpolyline([(x0,y0),(x1,y0),(x1,y1),(x0,y1)], close=True,
                         dxfattribs={"layer":"ROOM-BOUNDARY"})
        m.add_text(name, dxfattribs={"layer":"ROOM-NAMES","height":0.2}
                   ).set_placement(((x0+x1)/2,(y0+y1)/2))
    s = io.StringIO(); d.write(s)
    open(path,"w").write(s.getvalue())

if __name__ == "__main__":
    import sys
    build_dxf(sys.argv[1] if len(sys.argv) > 1 else "KG_L01.dxf")
    print(f"{len(ROOMS)} rooms, {len(DOORS)} doors, {len(WINDOWS)} windows")
    print(f"envelope {W} x {H} m")
    import collections
    print(collections.Counter(t for _n,t,*_ in ROOMS))
