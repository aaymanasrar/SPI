"""Element mapping — the BIM counterpart of cad/symbols.py, and data for the
same reason.

An IFC class with a standard predefined type is unambiguous: IfcSensor with
SMOKESENSOR is a smoke detector in every model. But Revit exports a great many
devices as IfcBuildingElementProxy or with USERDEFINED, and then the only thing
that says what the element is, is a family name someone typed. That is a
project convention, so it is supplied as a rule and never guessed.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator

from ..core import InvalidInput


class ElementRule(BaseModel):
    """One mapping line. At least one of ifc_class/name must be set."""
    ifc_class: str | None = Field(
        None, description="IFC class, e.g. IfcSensor. For a generic IFC2x3 "
                          "occurrence this is matched against its type object's "
                          "class, so IfcSensor also matches an "
                          "IfcDistributionControlElement typed by IfcSensorType.")
    predefined_type: str | None = Field(
        None, description="IFC predefined type, e.g. SMOKESENSOR")
    name: str | None = Field(
        None, description="matched against the element name, its Revit "
                          "'Family:Type', its type name and its user-defined type "
                          "label; a regex if is_regex")
    is_regex: bool = False
    ignore: bool = Field(
        False, description="this element is deliberately not a device to count "
                           "(a power socket in an ELV take-off). It is reported "
                           "under `ignored` rather than vanishing.")
    system: str | None = Field(None, description="e.g. fire_alarm, cctv, access_control")
    device_type: str | None = Field(None, description="what to count it as")
    unit: str = "no"
    note: str | None = None

    @model_validator(mode="after")
    def _complete(self) -> "ElementRule":
        if self.ifc_class is None and self.name is None:
            raise ValueError("a rule needs ifc_class or name, or it would match everything")
        if not self.ignore and not (self.system or "").strip():
            raise ValueError("system is required unless ignore is true")
        if not self.ignore and not (self.device_type or "").strip():
            raise ValueError("device_type is required unless ignore is true")
        return self

    def matches(self, d: dict) -> bool:
        if self.ifc_class is not None and self.ifc_class.casefold() != d["ifc_class"].casefold():
            return False
        if self.predefined_type is not None and \
                self.predefined_type.casefold() != (d["predefined_type"] or "").casefold():
            return False
        if self.name is None:
            return True
        for candidate in candidates(d):
            if self.is_regex:
                if re.fullmatch(self.name, candidate, re.IGNORECASE):
                    return True
            elif self.name.casefold() == candidate.casefold():
                return True
        return False


def candidates(d: dict) -> list[str]:
    """The names a rule may match. Revit names an occurrence
    'Family:Type:ElementId'; the id is stripped so one rule covers the family."""
    out = []
    for value in (d["name"], d["object_type"], d["type_name"], d["type_label"]):
        if value and value not in out:
            out.append(value)
            stripped = re.sub(r":\d+$", "", value)
            if stripped not in out:
                out.append(stripped)
    return out


class ElementMap(BaseModel):
    """A project's modelling convention, as data."""
    name: str
    version: str
    source_document: str = Field(
        description="where this mapping came from — a BIM execution plan, a "
                    "family naming standard, an email. Required: a mapping with "
                    "no stated origin cannot be audited later.")
    rules: list[ElementRule]

    @field_validator("source_document")
    @classmethod
    def _needs_origin(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(
                "source_document is required — every mapping must say where it "
                "came from")
        return v

    @field_validator("rules")
    @classmethod
    def _not_empty(cls, v: list[ElementRule]) -> list[ElementRule]:
        if not v:
            raise ValueError("an element map with no rules would map nothing")
        return v

    def resolve(self, described: dict) -> ElementRule | None:
        """First matching rule wins, so order expresses precedence."""
        for rule in self.rules:
            if rule.matches(described):
                return rule
        return None

    @classmethod
    def load(cls, raw: str | bytes | dict) -> "ElementMap":
        if isinstance(raw, (str, bytes)):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError as e:
                raise InvalidInput(f"Element map is not valid JSON: {e}") from e
        return cls.model_validate(raw)


DEFAULT_MAP_PATH = Path(__file__).with_name("default_elements.json")


def default_map() -> ElementMap:
    """The generic map shipped with the engine.

    It contains only what the IFC schema itself defines: a class plus a standard
    predefined type. It interprets no family name, so every proxy and every
    USERDEFINED element surfaces as a gap for a person to map from the project's
    family naming standard.
    """
    return ElementMap.load(DEFAULT_MAP_PATH.read_text(encoding="utf-8"))
