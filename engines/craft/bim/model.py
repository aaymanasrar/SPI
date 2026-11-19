"""The parts of an IFC model the tools read: units, storeys, what contains what,
which type an element is an occurrence of, and where it sits.

Attribute positions are fixed by the IFC schema and are the same in IFC2x3 and
IFC4 for everything read here unless a comment says otherwise.
"""
from __future__ import annotations

import io
import math
import zipfile

from ..core import InvalidInput
from .step import Entity, Enum, Ref, StepFile, Typed

# Attribute positions (0-based) on the entities this module reads.
NAME, DESCRIPTION, OBJECT_TYPE, PLACEMENT, TAG = 2, 3, 4, 5, 7
OCCURRENCE_PREDEFINED = 8      # IFC4 element classes
TYPE_ELEMENT_TYPE, TYPE_PREDEFINED = 8, 9

SI_PREFIX = {"EXA": 1e18, "PETA": 1e15, "TERA": 1e12, "GIGA": 1e9, "MEGA": 1e6,
             "KILO": 1e3, "HECTO": 1e2, "DECA": 1e1, "DECI": 1e-1, "CENTI": 1e-2,
             "MILLI": 1e-3, "MICRO": 1e-6, "NANO": 1e-9}

# IFC2x3 has no IfcSensor or IfcAlarm occurrence: a detector is an
# IfcDistributionControlElement whose *type* is an IfcSensorType. For these
# generic classes the type object says what the element is.
GENERIC_CLASSES = {
    "IFCBUILDINGELEMENTPROXY", "IFCDISTRIBUTIONELEMENT", "IFCDISTRIBUTIONFLOWELEMENT",
    "IFCDISTRIBUTIONCONTROLELEMENT", "IFCFLOWTERMINAL", "IFCFLOWCONTROLLER",
    "IFCENERGYCONVERSIONDEVICE", "IFCFLOWMOVINGDEVICE", "IFCFLOWSTORAGEDEVICE",
    "IFCFLOWTREATMENTDEVICE", "IFCFLOWFITTING", "IFCFLOWSEGMENT",
}

SPATIAL_CLASSES = {"IFCPROJECT", "IFCSITE", "IFCBUILDING", "IFCBUILDINGSTOREY",
                   "IFCSPACE", "IFCFACILITY", "IFCFACILITYPART"}

_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

EXPORT_HINT = ("Export it from Revit as IFC (File → Export → IFC; IFC4 Reference "
               "View or IFC2x3 Coordination View 2.0) and upload the .ifc.")


def open_ifc(raw: bytes, storage_key: str) -> "IfcModel":
    """Shared loader. Says exactly why a file that is not IFC cannot be read."""
    if raw.startswith(_OLE_MAGIC):
        raise InvalidInput(
            f"{storage_key} is a native Revit file (.rvt/.rfa), not IFC. The Revit "
            "format is proprietary and undocumented; the only readers are Revit "
            "itself and the ODA SDK, which is not licence-compatible. " + EXPORT_HINT)
    if raw.startswith(b"PK"):
        # .ifczip: a zip holding one .ifc.
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                inner = [n for n in z.namelist() if n.lower().endswith(".ifc")]
                if not inner:
                    raise InvalidInput(f"{storage_key} is a zip with no .ifc inside.")
                raw = z.read(inner[0])
        except zipfile.BadZipFile as e:
            raise InvalidInput(f"{storage_key} is not a readable .ifczip: {e}") from e
    head = raw[:200].lstrip(b"\xef\xbb\xbf \r\n\t")
    if head.startswith(b"<"):
        raise InvalidInput(
            f"{storage_key} is XML (ifcXML), which is not read. " + EXPORT_HINT)
    if not head.startswith(b"ISO-10303-21"):
        raise InvalidInput(
            f"{storage_key} is not an IFC file: it does not start with "
            "ISO-10303-21. " + EXPORT_HINT)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("cp1252", "replace")
    return IfcModel(StepFile(text))


def _text(value) -> str | None:
    """A label attribute as text. Blank is the same as unset."""
    if isinstance(value, Typed):
        value = value.value
    if isinstance(value, str) and not isinstance(value, Enum) and value.strip():
        return value.strip()
    return None


def _number(value) -> float | None:
    if isinstance(value, Typed):
        value = value.value
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _refs(value) -> list[Ref]:
    return [v for v in value if isinstance(v, Ref)] if isinstance(value, list) else []


class IfcModel:
    def __init__(self, step: StepFile):
        self.step = step
        schemas = self.step.header.get("FILE_SCHEMA", [[]])
        names = schemas[0] if schemas and isinstance(schemas[0], list) else []
        self.schema: str = str(names[0]).upper() if names else "UNKNOWN"
        if not self.schema.startswith("IFC"):
            raise InvalidInput(
                f"This STEP file declares schema {self.schema!r}, not IFC. "
                + EXPORT_HINT)
        #: IFC2x3 has no PredefinedType on most occurrences; position 8 holds
        #: something else there (CompositionType on a proxy), so it is only read
        #: from IFC4 onwards.
        self.is_ifc2x3 = self.schema.startswith("IFC2")

        file_name = self.step.header.get("FILE_NAME", [])
        at = lambda i: _text(file_name[i]) if i < len(file_name) else None  # noqa: E731
        self.timestamp = at(1)
        self.preprocessor = at(4)
        self.originating_system = at(5)

        self.length_unit, self.metres_per_unit = self._unit("LENGTHUNIT", 1)
        self.area_unit, self.sqm_per_unit = self._unit("AREAUNIT", 2)

        self.container: dict[int, int] = {}     # element/child -> containing structure
        self.parent: dict[int, int] = {}        # decomposition child -> parent
        self.type_ref: dict[int, int] = {}      # occurrence -> type object
        self.definitions: dict[int, list[int]] = {}   # object -> psets / quantity sets
        self._index_relationships()
        self._placements: dict[int, tuple | None] = {}

    # -- header-level facts -------------------------------------------------

    @property
    def authoring_application(self) -> str | None:
        """The IfcApplication record: the only reliable statement of what wrote
        the file. Revit's FILE_NAME header names its exporter add-in and its
        STEP writer, and never the word Revit."""
        for app in self.step.of_type("IFCAPPLICATION"):
            return " ".join(x for x in (_text(app.arg(2)), _text(app.arg(1))) if x) or None
        return None

    @property
    def is_revit(self) -> bool:
        return "revit" in f"{self.authoring_application or ''} {self.originating_system or ''}".lower()

    def project(self) -> Entity | None:
        found = self.step.of_type("IFCPROJECT")
        return found[0] if found else None

    def _unit(self, unit_type: str, power: int) -> tuple[str | None, float | None]:
        """(name, SI factor) for the project's length or area unit, or
        (name, None) when the file does not say enough to convert."""
        for assignment in self.step.of_type("IFCUNITASSIGNMENT"):
            for ref in _refs(assignment.arg(0)):
                unit = self.step.get(ref)
                if unit is None:
                    continue
                if unit.type == "IFCSIUNIT" and unit.arg(1) == unit_type:
                    prefix, name = unit.arg(2), str(unit.arg(3) or "")
                    scale = SI_PREFIX.get(str(prefix), 1.0) if prefix else 1.0
                    label = f"{str(prefix).lower() if prefix else ''}{name.lower()}"
                    return label, scale ** power
                if unit.type == "IFCCONVERSIONBASEDUNIT" and unit.arg(1) == unit_type:
                    label = (_text(unit.arg(2)) or "conversion-based unit").lower()
                    measure = self.step.get(unit.arg(3))
                    factor = _number(measure.arg(0)) if measure else None
                    base = self.step.get(measure.arg(1)) if measure else None
                    if factor is None or base is None or base.type != "IFCSIUNIT":
                        return label, None
                    prefix = base.arg(2)
                    scale = SI_PREFIX.get(str(prefix), 1.0) if prefix else 1.0
                    return label, factor * scale ** power
        return None, None

    # -- relationships ------------------------------------------------------

    def _index_relationships(self) -> None:
        for rel in self.step.of_type("IFCRELCONTAINEDINSPATIALSTRUCTURE"):
            structure = rel.arg(5)
            if isinstance(structure, Ref):
                for el in _refs(rel.arg(4)):
                    self.container[int(el)] = int(structure)
        for rel in self.step.of_type("IFCRELAGGREGATES", "IFCRELNESTS"):
            whole = rel.arg(4)
            if isinstance(whole, Ref):
                for part in _refs(rel.arg(5)):
                    self.parent[int(part)] = int(whole)
        for rel in self.step.of_type("IFCRELDEFINESBYTYPE"):
            type_obj = rel.arg(5)
            if isinstance(type_obj, Ref):
                for el in _refs(rel.arg(4)):
                    self.type_ref[int(el)] = int(type_obj)
        for rel in self.step.of_type("IFCRELDEFINESBYPROPERTIES"):
            definition = rel.arg(5)
            if isinstance(definition, Ref):
                for el in _refs(rel.arg(4)):
                    self.definitions.setdefault(int(el), []).append(int(definition))

    def storey_of(self, element_id: int) -> Entity | None:
        """The storey an element or space belongs to, however deep it is nested."""
        seen: set[int] = set()
        current: int | None = element_id
        while current is not None and current not in seen:
            seen.add(current)
            if self.step.type_of(current) == "IFCBUILDINGSTOREY":
                return self.step.get(current)
            current = self.container.get(current, self.parent.get(current))
        return None

    def space_of(self, element_id: int) -> Entity | None:
        """The space an element is placed in, when the model says so directly."""
        holder = self.container.get(element_id)
        if holder is not None and self.step.type_of(holder) == "IFCSPACE":
            return self.step.get(holder)
        return None

    def storeys(self) -> list[dict]:
        out = []
        for s in self.step.of_type("IFCBUILDINGSTOREY"):
            elevation = _number(s.arg(9))
            out.append({
                "global_id": _text(s.arg(0)),
                "name": _text(s.arg(NAME)) or f"#{s.id}",
                # + 0.0 turns Revit's -0.0 into 0.0.
                "elevation_m": (round(elevation * self.metres_per_unit, 4) + 0.0
                                if elevation is not None and self.metres_per_unit else None),
            })
        return sorted(out, key=lambda s: (s["elevation_m"] is None, s["elevation_m"] or 0, s["name"]))

    # -- what an element is -------------------------------------------------

    def describe(self, el: Entity) -> dict:
        """Everything a mapping rule may match on, read off the element and its
        type object. Nothing here is interpreted."""
        type_obj = self.step.get(self.type_ref.get(el.id))
        effective = el.type
        if (type_obj is not None and el.type in GENERIC_CLASSES
                and type_obj.type.endswith("TYPE")
                and type_obj.type[:-4] not in GENERIC_CLASSES):
            effective = type_obj.type[:-4]

        predefined = None
        if not self.is_ifc2x3 and isinstance(el.arg(OCCURRENCE_PREDEFINED), Enum):
            predefined = str(el.arg(OCCURRENCE_PREDEFINED))
        if predefined in (None, "NOTDEFINED") and type_obj is not None \
                and isinstance(type_obj.arg(TYPE_PREDEFINED), Enum):
            predefined = str(type_obj.arg(TYPE_PREDEFINED))

        return {
            "id": el.id,
            "global_id": _text(el.arg(0)),
            "ifc_class": effective,
            "occurrence_class": el.type,
            "predefined_type": predefined,
            "name": _text(el.arg(NAME)),
            "object_type": _text(el.arg(OBJECT_TYPE)),
            "tag": _text(el.arg(TAG)),
            "type_name": _text(type_obj.arg(NAME)) if type_obj else None,
            "type_label": _text(type_obj.arg(TYPE_ELEMENT_TYPE)) if type_obj else None,
        }

    # -- where an element is ------------------------------------------------

    def position_m(self, el: Entity) -> list[float] | None:
        """The element's insertion point in metres, in the model's own
        coordinate system. None when the placement or the unit is not usable."""
        return self.locate(el)["position_m"]

    def locate(self, el: Entity) -> dict:
        """Where an element is: position in metres, plan orientation, and which
        of the two places the exporter put the location was used.

        Normally the placement says where an element is. Some Revit families are
        exported with the placement at the origin and the location baked into the
        geometry instead; for those the body geometry's own origin is used, and
        `basis` says so, because the two are not the same point on the family.
        """
        from .geometry import anchor   # geometry imports this module

        none = {"position_m": None, "yaw_deg": None, "basis": None}
        world = self._world(el.arg(PLACEMENT), 0)
        if world is None or self.metres_per_unit is None:
            return none
        rot, origin = world
        point, basis = origin, "placement"

        # The telltale is a placement that lands on the model origin in plan
        # while the geometry is somewhere else. Tested in world terms, not on
        # the element's own offset: Revit also writes an own offset of
        # (0, 0, -elevation) that cancels the storey and lands on the origin.
        if abs(origin[0]) < 1e-6 and abs(origin[1]) < 1e-6:
            local = anchor(self, el)
            if local is not None:
                world_point = tuple(origin[i] + sum(rot[i][j] * local[j] for j in range(3))
                                    for i in range(3))
                if abs(world_point[0]) > 1e-6 or abs(world_point[1]) > 1e-6:
                    point, basis = world_point, "geometry"

        # Plan orientation of the element's local X axis. Which way a family
        # "faces" is the family author's choice; this is the axis, not a claim
        # about where a camera looks.
        yaw = math.degrees(math.atan2(rot[1][0], rot[0][0]))
        return {"position_m": [round(c * self.metres_per_unit, 4) for c in point],
                "yaw_deg": round(yaw, 2), "basis": basis}

    def _world(self, ref, depth: int):
        """(rotation, origin) of an IfcLocalPlacement in world coordinates."""
        if not isinstance(ref, Ref) or depth > 64:
            return None
        key = int(ref)
        if key in self._placements:
            return self._placements[key]
        placement = self.step.get(ref)
        result = None
        if placement is not None and placement.type == "IFCLOCALPLACEMENT":
            local = self._axis_placement(self.step.get(placement.arg(1)))
            if local is not None:
                if placement.arg(0) is None:
                    result = local
                else:
                    outer = self._world(placement.arg(0), depth + 1)
                    if outer is not None:
                        rot, origin = outer
                        lrot, lorigin = local
                        result = (_matmul(rot, lrot),
                                  tuple(origin[i] + sum(rot[i][j] * lorigin[j] for j in range(3))
                                        for i in range(3)))
        self._placements[key] = result
        return result

    def _axis_placement(self, axis: Entity | None):
        if axis is None or axis.type not in ("IFCAXIS2PLACEMENT3D", "IFCAXIS2PLACEMENT2D"):
            return None
        origin = self._triple(self.step.get(axis.arg(0)), (0.0, 0.0, 0.0))
        if axis.type == "IFCAXIS2PLACEMENT3D":
            z = _unit_vector(self._triple(self.step.get(axis.arg(1)), (0.0, 0.0, 1.0)))
            x_hint = self._triple(self.step.get(axis.arg(2)), (1.0, 0.0, 0.0))
        else:
            z = (0.0, 0.0, 1.0)
            x_hint = self._triple(self.step.get(axis.arg(1)), (1.0, 0.0, 0.0))
        if z is None:
            return None
        dot = sum(x_hint[i] * z[i] for i in range(3))
        x = _unit_vector(tuple(x_hint[i] - dot * z[i] for i in range(3)))
        if x is None:
            return None
        y = (z[1] * x[2] - z[2] * x[1], z[2] * x[0] - z[0] * x[2], z[0] * x[1] - z[1] * x[0])
        return (tuple((x[i], y[i], z[i]) for i in range(3)), origin)

    @staticmethod
    def _triple(entity: Entity | None, default: tuple) -> tuple:
        if entity is None or not isinstance(entity.arg(0), list):
            return default
        nums = [float(v) for v in entity.arg(0) if isinstance(v, (int, float))]
        return tuple((nums + [0.0, 0.0, 0.0])[:3]) if nums else default


def _unit_vector(v: tuple) -> tuple | None:
    length = sum(c * c for c in v) ** 0.5
    return tuple(c / length for c in v) if length > 1e-12 else None


def _matmul(a: tuple, b: tuple) -> tuple:
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3))
                 for i in range(3))
