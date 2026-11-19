"""A synthetic two-storey office written the way Revit's IFC exporter writes one.

This is a fixture, not a project. No client has supplied a Revit model, and the
public Revit samples are architectural or structural with no ELV devices in
them, so this file reproduces the Revit export habits the BIM engine has to
cope with:

* occurrence names as 'Family:Type:ElementId', ObjectType 'Family:Type', the
  element id in Tag;
* devices contained in the storey, never in the room they sit in;
* rooms aggregated under the storey and extruded from a polyline, an indexed
  polycurve with an arc, or a composite curve;
* a room name outside ASCII, written as a \\X2\\ escape;
* families exported as IfcBuildingElementProxy, which no IFC class identifies;
* one family exported with its placement at the origin and its location in a
  mapped-item transform;
* one room with no area quantity at all, and one with only Revit's Area
  property;
* in IFC2X3, detectors as IfcDistributionControlElement typed by IfcSensorType,
  because IFC2X3 has no IfcSensor occurrence.

Two gaps are deliberate, so the simulator has something to find: the open-plan
office has three detectors where its 16 m x 14 m needs four at a 6.37 m radius,
and the meeting room has none at all.

    python fixtures/revit_elv_office.py [IFC4|IFC2X3] > SPT-Demo-Office.ifc
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass


class E(str):
    """An enumeration value."""


@dataclass
class T:
    """A typed value, e.g. IFCAREAMEASURE(12.5)."""
    type: str
    value: object


def _fmt(v) -> str:
    if v is None:
        return "$"
    if isinstance(v, E):
        return f".{v}."
    if isinstance(v, bool):
        return ".T." if v else ".F."
    if isinstance(v, T):
        return f"{v.type}({_fmt(v.value)})"
    if isinstance(v, str):
        if v.startswith("#") and v[1:].isdigit():
            return v
        out = []
        for ch in v:
            if ch == "'":
                out.append("''")
            elif ch == "\\":
                out.append("\\\\")
            elif ord(ch) > 126:
                out.append(f"\\X2\\{ord(ch):04X}\\X0\\")
            else:
                out.append(ch)
        return "'" + "".join(out) + "'"
    if isinstance(v, float):
        s = repr(v)
        return s if ("." in s or "e" in s or "E" in s) else s + "."
    if isinstance(v, int):
        return str(v)
    if isinstance(v, (list, tuple)):
        return "(" + ",".join(_fmt(x) for x in v) + ")"
    raise TypeError(type(v))


class Writer:
    def __init__(self):
        self.lines: list[str] = []
        self.n = 0
        self._guid = 0

    def add(self, etype: str, *args) -> str:
        self.n += 1
        self.lines.append(f"#{self.n}={etype}({','.join(_fmt(a) for a in args)});")
        return f"#{self.n}"

    def guid(self) -> str:
        # 22-character IFC GlobalIds, deterministic so the fixture is stable.
        alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$"
        self._guid += 1
        n, out = self._guid * 7919 + 104729, []
        for _ in range(22):
            out.append(alphabet[n % 64])
            n //= 64
        return "3" + "".join(out)[1:]


def build(schema: str = "IFC4") -> str:
    schema = schema.upper()
    ifc4 = schema == "IFC4"
    w = Writer()

    person = w.add("IFCPERSON", None, "Engineer", None, None, None, None, None, None)
    org = w.add("IFCORGANIZATION", None, "SmartPage Technology Arabia", None, None, None)
    porg = w.add("IFCPERSONANDORGANIZATION", person, org, None)
    adsk = w.add("IFCORGANIZATION", None, "Autodesk Revit 2024 (ENU)", None, None, None)
    app = w.add("IFCAPPLICATION", adsk, "2024", "Autodesk Revit 2024 (ENU)", "Revit")
    owner = w.add("IFCOWNERHISTORY", porg, app, None, E("NOCHANGE"), None, None, None, 0)

    def pt(*c):
        return w.add("IFCCARTESIANPOINT", [float(x) for x in c])

    def dirn(*c):
        return w.add("IFCDIRECTION", [float(x) for x in c])

    origin3, z_up = pt(0, 0, 0), dirn(0, 0, 1)

    def axis3(x=0.0, y=0.0, z=0.0, yaw_deg: float | None = None):
        refd = None
        if yaw_deg is not None:
            refd = dirn(round(math.cos(math.radians(yaw_deg)), 9),
                        round(math.sin(math.radians(yaw_deg)), 9), 0.0)
        loc = origin3 if (x, y, z) == (0, 0, 0) else pt(x, y, z)
        return w.add("IFCAXIS2PLACEMENT3D", loc, z_up if refd else None, refd)

    world = axis3()
    ctx = w.add("IFCGEOMETRICREPRESENTATIONCONTEXT", None, "Model", 3, 0.01, world, None)
    body_ctx = w.add("IFCGEOMETRICREPRESENTATIONSUBCONTEXT", "Body", "Model", None, None,
                     None, None, ctx, None, E("MODEL_VIEW"), None)

    mm = w.add("IFCSIUNIT", "*", E("LENGTHUNIT"), E("MILLI"), E("METRE"))
    m2 = w.add("IFCSIUNIT", "*", E("AREAUNIT"), None, E("SQUARE_METRE"))
    m3 = w.add("IFCSIUNIT", "*", E("VOLUMEUNIT"), None, E("CUBIC_METRE"))
    rad = w.add("IFCSIUNIT", "*", E("PLANEANGLEUNIT"), None, E("RADIAN"))
    units = w.add("IFCUNITASSIGNMENT", [mm, m2, m3, rad])
    project = w.add("IFCPROJECT", w.guid(), owner, "SPT-DEMO-001", None, None,
                    "SPT Demo Office", "Fixture — not a project", [ctx], units)

    site_pl = w.add("IFCLOCALPLACEMENT", None, axis3())
    site = w.add("IFCSITE", w.guid(), owner, "Default", None, None, site_pl, None, None,
                 E("ELEMENT"), None, None, None, None, None)
    bldg_pl = w.add("IFCLOCALPLACEMENT", site_pl, axis3())
    bldg = w.add("IFCBUILDING", w.guid(), owner, "SPT Demo Office", None, None, bldg_pl,
                 None, None, E("ELEMENT"), None, None, None)
    w.add("IFCRELAGGREGATES", w.guid(), owner, None, None, project, [site])
    w.add("IFCRELAGGREGATES", w.guid(), owner, None, None, site, [bldg])

    storeys: dict[str, tuple[str, str, float]] = {}
    for name, elev in (("Level 1", 0.0), ("Level 2", 4000.0)):
        pl = w.add("IFCLOCALPLACEMENT", bldg_pl, axis3(0, 0, elev))
        st = w.add("IFCBUILDINGSTOREY", w.guid(), owner, name, None, "Level:8mm Head",
                   pl, None, name, E("ELEMENT"), elev)
        storeys[name] = (st, pl, elev)
    w.add("IFCRELAGGREGATES", w.guid(), owner, None, None, bldg,
          [s[0] for s in storeys.values()])

    def shape(solid):
        rep = w.add("IFCSHAPEREPRESENTATION", body_ctx, "Body", "SweptSolid", [solid])
        return w.add("IFCPRODUCTDEFINITIONSHAPE", None, None, [rep])

    def box(dx, dy, dz, at=(0.0, 0.0, 0.0)):
        prof = w.add("IFCRECTANGLEPROFILEDEF", E("AREA"), None,
                     w.add("IFCAXIS2PLACEMENT2D", w.add("IFCCARTESIANPOINT", [0.0, 0.0]), None),
                     float(dx), float(dy))
        return w.add("IFCEXTRUDEDAREASOLID", prof, axis3(*at), z_up, float(dz))

    contained: dict[str, list[str]] = {k: [] for k in storeys}
    rooms_by_storey: dict[str, list[str]] = {k: [] for k in storeys}
    eid = [300000]

    def next_id() -> int:
        eid[0] += 1137
        return eid[0]

    # -- rooms -------------------------------------------------------------
    def room(storey, number, name, curve, height=2800.0, area=None, area_prop=None):
        _st, st_pl, _ = storeys[storey]
        pl = w.add("IFCLOCALPLACEMENT", st_pl, axis3())
        prof = w.add("IFCARBITRARYCLOSEDPROFILEDEF", E("AREA"), None, curve)
        solid = w.add("IFCEXTRUDEDAREASOLID", prof, axis3(), z_up, height)
        # IFC4: CompositionType, PredefinedType, ElevationWithFlooring.
        # IFC2X3: CompositionType, InteriorOrExteriorSpace, ElevationWithFlooring.
        sp = w.add("IFCSPACE", w.guid(), owner, number, None, None, pl, shape(solid),
                   name, E("ELEMENT"), E("INTERNAL"), None)
        rooms_by_storey[storey].append(sp)
        if area is not None:
            q = w.add("IFCQUANTITYAREA", "NetFloorArea", None, None, float(area),
                      *([None] if ifc4 else []))
            qs = w.add("IFCELEMENTQUANTITY", w.guid(), owner, "BaseQuantities", None, None, [q])
            w.add("IFCRELDEFINESBYPROPERTIES", w.guid(), owner, None, None, [sp], qs)
        if area_prop is not None:
            p = w.add("IFCPROPERTYSINGLEVALUE", "Area", None, T("IFCAREAMEASURE", float(area_prop)), None)
            ps = w.add("IFCPROPERTYSET", w.guid(), owner, "PSet_Revit_Dimensions", None, [p])
            w.add("IFCRELDEFINESBYPROPERTIES", w.guid(), owner, None, None, [sp], ps)
        return sp

    def poly(*xy):
        pts = [w.add("IFCCARTESIANPOINT", [float(x), float(y)]) for x, y in xy]
        return w.add("IFCPOLYLINE", pts + [pts[0]])

    # Level 1 — 24 m x 14 m.
    room("Level 1", "101", "Reception", poly((0, 0), (8000, 0), (8000, 6000), (0, 6000)), area=48.0)
    room("Level 1", "102", "Open Office", poly((8000, 0), (24000, 0), (24000, 14000), (8000, 14000)), area=224.0)
    room("Level 1", "103", "Meeting", poly((0, 6000), (5000, 6000), (5000, 10000), (0, 10000)), area_prop=20.0)
    room("Level 1", "104", "غرفة الخوادم", poly((5000, 6000), (8000, 6000), (8000, 10000), (5000, 10000)), area=12.0)
    if ifc4:
        # Lobby with a curved north wall: an indexed polycurve with an arc.
        plist = w.add("IFCCARTESIANPOINTLIST2D", [[0.0, 10000.0], [8000.0, 10000.0],
                                                  [8000.0, 14000.0], [4000.0, 15500.0],
                                                  [0.0, 14000.0]])
        curve = w.add("IFCINDEXEDPOLYCURVE", plist,
                      [T("IFCLINEINDEX", [1, 2, 3]), T("IFCARCINDEX", [3, 4, 5]),
                       T("IFCLINEINDEX", [5, 1])], False)
        room("Level 1", "105", "Lobby", curve)          # no area quantity at all
    else:
        room("Level 1", "105", "Lobby", poly((0, 10000), (8000, 10000), (8000, 14000), (0, 14000)))

    # Level 2 — composite-curve rooms, as Revit writes bounded rooms.
    def composite(*xy):
        segs = []
        for (x1, y1), (x2, y2) in zip(xy, xy[1:] + xy[:1]):
            line = w.add("IFCPOLYLINE", [w.add("IFCCARTESIANPOINT", [float(x1), float(y1)]),
                                         w.add("IFCCARTESIANPOINT", [float(x2), float(y2)])])
            segs.append(w.add("IFCCOMPOSITECURVESEGMENT", E("CONTINUOUS"), True, line))
        return w.add("IFCCOMPOSITECURVE", segs, False)

    room("Level 2", "201", "Office A", composite((0, 0), (12000, 0), (12000, 8000), (0, 8000)), area=96.0)
    room("Level 2", "202", "Office B", composite((12000, 0), (24000, 0), (24000, 8000), (12000, 8000)), area=96.0)
    room("Level 2", "203", "Corridor", composite((0, 8000), (24000, 8000), (24000, 10000), (0, 10000)), area=48.0)
    room("Level 2", "204", "Training", composite((0, 10000), (24000, 10000), (24000, 14000), (0, 14000)), area=96.0)

    for storey, rooms in rooms_by_storey.items():
        w.add("IFCRELAGGREGATES", w.guid(), owner, None, None, storeys[storey][0], rooms)

    # -- walls ---------------------------------------------------------------
    def wall(storey, x1, y1, x2, y2, height=4000.0, thick=200.0):
        _st, st_pl, _ = storeys[storey]
        length = math.hypot(x2 - x1, y2 - y1)
        yaw = math.degrees(math.atan2(y2 - y1, x2 - x1))
        pl = w.add("IFCLOCALPLACEMENT", st_pl, axis3(x1, y1, 0.0, yaw))
        prof = w.add("IFCRECTANGLEPROFILEDEF", E("AREA"), None,
                     w.add("IFCAXIS2PLACEMENT2D",
                           w.add("IFCCARTESIANPOINT", [length / 2, 0.0]), None),
                     float(length), float(thick))
        solid = w.add("IFCEXTRUDEDAREASOLID", prof, axis3(), z_up, float(height))
        i = next_id()
        cls = "IFCWALLSTANDARDCASE"
        args = [w.guid(), owner, f"Basic Wall:Interior - 200mm:{i}", None,
                "Basic Wall:Interior - 200mm", pl, shape(solid), str(i)]
        if ifc4:
            args.append(E("NOTDEFINED"))
        contained[storey].append(w.add(cls, *args))

    for storey in storeys:
        for x1, y1, x2, y2 in ((0, 0, 24000, 0), (24000, 0, 24000, 14000),
                               (24000, 14000, 0, 14000), (0, 14000, 0, 0)):
            wall(storey, x1, y1, x2, y2)
    for x1, y1, x2, y2 in ((8000, 0, 8000, 14000), (0, 6000, 8000, 6000),
                           (0, 10000, 8000, 10000), (5000, 6000, 5000, 10000)):
        wall("Level 1", x1, y1, x2, y2)
    for x1, y1, x2, y2 in ((12000, 0, 12000, 8000), (0, 8000, 24000, 8000),
                           (0, 10000, 24000, 10000)):
        wall("Level 2", x1, y1, x2, y2)

    # -- device types ----------------------------------------------------------
    types: dict[str, str] = {}

    def type_obj(key, cls, family_type, predefined, element_type=None):
        if key in types:
            return types[key]
        args = [w.guid(), owner, family_type, None, None, None, None, str(next_id()),
                element_type, E(predefined)]
        types[key] = w.add(cls, *args)
        return types[key]

    typed: dict[str, list[str]] = {}

    def device(storey, cls, family_type, x, y, z, *, predefined=None, type_cls=None,
               type_predefined=None, yaw=None, size=(150, 150, 60), mapped=False,
               object_type=None):
        _st, st_pl, _ = storeys[storey]
        i = next_id()
        if mapped:
            # Placement at the origin; the location lives in the mapped item.
            pl = w.add("IFCLOCALPLACEMENT", st_pl, axis3())
            rmap = w.add("IFCREPRESENTATIONMAP", axis3(),
                         w.add("IFCSHAPEREPRESENTATION", body_ctx, "Body", "SweptSolid",
                               [box(*size)]))
            op = w.add("IFCCARTESIANTRANSFORMATIONOPERATOR3D", None, None,
                       pt(x, y, z), 1.0, None)
            item = w.add("IFCMAPPEDITEM", rmap, op)
            rep = w.add("IFCSHAPEREPRESENTATION", body_ctx, "Body", "MappedRepresentation", [item])
            prod = w.add("IFCPRODUCTDEFINITIONSHAPE", None, None, [rep])
        else:
            pl = w.add("IFCLOCALPLACEMENT", st_pl, axis3(x, y, z, yaw))
            prod = shape(box(*size))
        args = [w.guid(), owner, f"{family_type}:{i}", None, object_type or family_type,
                pl, prod, str(i)]
        if cls == "IFCBUILDINGELEMENTPROXY":
            args.append(E("NOTDEFINED") if ifc4 else None)   # 2X3: CompositionType
        elif ifc4:
            args.append(E(predefined) if predefined else None)
        else:
            args.append(None)                                  # 2X3: ControlElementId
        el = w.add(cls, *args)
        contained[storey].append(el)
        if type_cls:
            t = type_obj(family_type, type_cls, family_type,
                         type_predefined or predefined or "NOTDEFINED")
            typed.setdefault(t, []).append(el)
        return el

    ceiling = 2800.0
    # IFC2X3 has no IfcSensor or IfcAlarm occurrence; the type says what it is.
    sensor_cls = "IFCSENSOR" if ifc4 else "IFCDISTRIBUTIONCONTROLELEMENT"
    alarm_cls = "IFCALARM" if ifc4 else "IFCDISTRIBUTIONCONTROLELEMENT"

    def smoke(storey, x, y, **kw):
        device(storey, sensor_cls, "SPT_FA_Detector_Optical:Ceiling", x, y, ceiling,
               predefined="SMOKESENSOR", type_cls="IFCSENSORTYPE",
               type_predefined="SMOKESENSOR", size=(110, 110, 50), **kw)

    def mcp(storey, x, y):
        device(storey, alarm_cls, "SPT_FA_ManualCallPoint:Surface", x, y, 1400.0,
               predefined="MANUALPULLBOX", type_cls="IFCALARMTYPE",
               type_predefined="MANUALPULLBOX", size=(90, 60, 90))

    def sounder(storey, x, y):
        device(storey, "IFCBUILDINGELEMENTPROXY", "SPT_FA_Sounder_Beacon:Wall", x, y, 2300.0,
               size=(110, 80, 110))

    # Level 1 detectors. The open office (16 m x 14 m) gets three, one short;
    # the meeting room gets none.
    for x, y in ((2500, 3000), (5500, 3000)):
        smoke("Level 1", x, y)
    for x, y in ((12000, 3500), (20000, 3500), (12000, 10500)):
        smoke("Level 1", x, y)
    smoke("Level 1", 6500, 8000, mapped=True)          # the mapped-item family
    smoke("Level 1", 2000, 12000)
    smoke("Level 1", 6000, 12000)
    for x, y in ((3000, 2000), (9000, 2000), (9000, 6000), (15000, 2000), (21000, 2000),
                 (15000, 6000), (21000, 6000), (3000, 6000), (9000, 9000), (15000, 9000),
                 (21000, 9000), (3000, 9000), (3000, 12000), (9000, 12000),
                 (15000, 12000), (21000, 12000)):
        smoke("Level 2", x, y)

    for storey in storeys:
        mcp(storey, 200 + 150, 1200)
        mcp(storey, 23650, 12800)
    for storey, pts in (("Level 1", ((4000, 5850), (16000, 150), (16000, 13850), (4000, 13850))),
                        ("Level 2", ((6000, 7850), (18000, 7850), (12000, 13850)))):
        for x, y in pts:
            sounder(storey, x, y)

    if ifc4:
        cam = dict(predefined="CAMERA", type_cls="IFCAUDIOVISUALAPPLIANCETYPE",
                   type_predefined="CAMERA", size=(120, 220, 120))
        device("Level 1", "IFCAUDIOVISUALAPPLIANCE", "SPT_CCTV_Dome:4MP", 300, 300, 2700, yaw=45, **cam)
        device("Level 1", "IFCAUDIOVISUALAPPLIANCE", "SPT_CCTV_Bullet:4MP", 23700, 300, 2700, yaw=135, **cam)
        device("Level 1", "IFCAUDIOVISUALAPPLIANCE", "SPT_CCTV_Bullet:4MP", 23700, 13700, 2700, yaw=-135, **cam)
        device("Level 1", "IFCAUDIOVISUALAPPLIANCE", "SPT_CCTV_Dome:4MP", 300, 13700, 2700, yaw=-45, **cam)
        device("Level 2", "IFCAUDIOVISUALAPPLIANCE", "SPT_CCTV_Dome:4MP", 300, 9000, 2700, yaw=0, **cam)
        for storey, x, y in (("Level 1", 8150, 3000), ("Level 1", 5000, 9850),
                             ("Level 2", 12000, 7850)):
            device(storey, "IFCBUILDINGELEMENTPROXY", "SPT_ACS_CardReader:Mullion",
                   x, y, 1100, size=(50, 30, 120))
        for storey, pts in (("Level 1", ((12000, 7000), (20000, 7000), (4000, 3000))),
                            ("Level 2", ((6000, 4000), (18000, 4000), (12000, 12000)))):
            for x, y in pts:
                device(storey, "IFCCOMMUNICATIONSAPPLIANCE", "SPT_DATA_WAP:Ceiling", x, y, ceiling,
                       predefined="USERDEFINED", object_type="Wireless Access Point",
                       size=(200, 200, 40))
        for x, y in ((9000, 150), (13000, 150), (17000, 150)):
            device("Level 1", "IFCOUTLET", "SPT_DATA_Outlet:Twin RJ45", x, y, 300,
                   predefined="DATAOUTLET", size=(86, 30, 86))
            device("Level 1", "IFCOUTLET", "Power Outlet:Twin 13A", x + 300, y, 300,
                   predefined="POWEROUTLET", size=(86, 30, 86))

    for t, els in typed.items():
        w.add("IFCRELDEFINESBYTYPE", w.guid(), owner, None, None, els, t)
    for storey, els in contained.items():
        w.add("IFCRELCONTAINEDINSPATIALSTRUCTURE", w.guid(), owner, None, None, els,
              storeys[storey][0])

    view = "ReferenceView_V1.2" if ifc4 else "CoordinationView_V2.0"
    head = [
        "ISO-10303-21;",
        "HEADER;",
        f"FILE_DESCRIPTION(('ViewDefinition [{view}]'),'2;1');",
        "FILE_NAME('SPT-Demo-Office.ifc','2026-11-10T09:00:00',(''),(''),"
        "'The EXPRESS Data Manager Version 5.02.0100.07 : 28 Aug 2013',"
        "'24.1.0.45 - Exporter 24.1.0.45 - Alternate UI 24.1.0.45','');",
        f"FILE_SCHEMA(('{schema}'));",
        "ENDSEC;",
        "",
        "DATA;",
    ]
    return "\n".join(head + w.lines + ["ENDSEC;", "", "END-ISO-10303-21;", ""])


if __name__ == "__main__":
    sys.stdout.write(build(sys.argv[1] if len(sys.argv) > 1 else "IFC4"))
