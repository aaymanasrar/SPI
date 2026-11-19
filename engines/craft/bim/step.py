"""ISO 10303-21 reader — the plain-text encoding an .ifc file is written in.

Written here rather than imported because the usual IFC toolkit (IfcOpenShell)
is LGPL-3.0, which the licence policy treats as forbidden, and because the tools
in this engine read attributes and relationships only. They never touch
geometry, which is the part of IFC that needs a toolkit.

A model is hundreds of thousands of instances and the tools want a few thousand
of them, so nothing is parsed up front: the file is cut into statements, each
instance's type is indexed, and an argument list is only decoded when asked for.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ..core import InvalidInput


class Ref(int):
    """A reference to another instance: `#123`."""
    __slots__ = ()

    def __repr__(self) -> str:
        return f"#{int(self)}"


class Enum(str):
    """An enumeration value: `.SMOKESENSOR.` Kept apart from a quoted string."""
    __slots__ = ()


@dataclass(frozen=True)
class Typed:
    """A value wrapped in its measure type: `IFCAREAMEASURE(12.5)`."""
    type: str
    value: Any


@dataclass(frozen=True)
class Entity:
    id: int
    type: str
    args: list

    def arg(self, index: int) -> Any:
        """An attribute by position, or None where the schema version in hand
        simply has fewer attributes than the caller allowed for."""
        return self.args[index] if index < len(self.args) else None


# A quoted string may contain ';' and '(' — statements are cut on the
# semicolons that sit outside strings and comments, never inside them.
_STATEMENT = re.compile(r"'(?:[^']|'')*'|/\*.*?\*/|;", re.S)
# A statement may open with comments; they are skipped, not part of the name.
_LEAD = r"(?:\s|/\*.*?\*/)*"
_INSTANCE = re.compile(_LEAD + r"#(\d+)\s*=\s*([A-Za-z0-9_]+)\s*(?=\()", re.S)
_HEADER = re.compile(_LEAD + r"([A-Za-z0-9_]+)\s*(?=\()", re.S)

# Tokens come back from findall as plain strings — no Match objects, which is
# where most of the time went — and are told apart by their first character.
# Whitespace matches nothing and is skipped; the final catch-all turns anything
# unrecognised into a token of its own so it cannot slip through unnoticed.
_TOKEN = re.compile(r"""
    '(?:[^']|'')*'
  | /\*.*?\*/
  | \#\d+
  | \.[A-Za-z0-9_]+\.
  | [+-]?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?
  | "[0-9A-Fa-f]*"
  | [A-Za-z_][A-Za-z0-9_]*
  | [(),$*]
  | \S
""", re.X | re.S)
_NUMERIC_START = frozenset("0123456789+-")
_NAME_START = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_")

_ESCAPE = re.compile(
    r"\\X2\\((?:[0-9A-Fa-f]{4})+)\\X0\\"
    r"|\\X4\\((?:[0-9A-Fa-f]{8})+)\\X0\\"
    r"|\\X\\([0-9A-Fa-f]{2})"
    r"|\\S\\(.)"
    r"|\\\\")


def _decode_string(token: str) -> str:
    """Undo the STEP escapes. Revit writes anything outside ASCII — Arabic room
    names included — as \\X2\\ hex runs."""
    def one(m: re.Match) -> str:
        if m.group(1):
            return bytes.fromhex(m.group(1)).decode("utf-16-be", "replace")
        if m.group(2):
            return bytes.fromhex(m.group(2)).decode("utf-32-be", "replace")
        if m.group(3):
            return chr(int(m.group(3), 16))
        if m.group(4):
            return chr(ord(m.group(4)) + 128)
        return "\\"
    return _ESCAPE.sub(one, token[1:-1].replace("''", "'"))


def parse_args(text: str) -> list:
    """Decode one parenthesised argument list into Python values."""
    stack: list[tuple[list, str | None]] = [([], None)]
    cur = stack[0][0]
    pending: str | None = None
    for tok in _TOKEN.findall(text):
        c = tok[0]
        if c == ",":
            continue
        if c == "#":
            cur.append(Ref(tok[1:]))
        elif c in _NUMERIC_START:
            if len(tok) == 1 and c in "+-":
                raise InvalidInput(f"Unreadable STEP syntax: stray {tok!r}")
            cur.append(float(tok) if ("." in tok or "e" in tok or "E" in tok) else int(tok))
        elif c == "(":
            stack.append(([], pending))
            cur = stack[-1][0]
            pending = None
        elif c == ")":
            if len(stack) == 1:
                raise InvalidInput("Unbalanced ')' in a STEP argument list")
            items, name = stack.pop()
            cur = stack[-1][0]
            cur.append(Typed(name.upper(), items[0] if len(items) == 1 else items)
                       if name else items)
        elif c == "$" or c == "*":
            cur.append(None)              # $ unset, * derived: no value either way
        elif c == "'":
            cur.append(_decode_string(tok) if ("\\" in tok or "''" in tok) else tok[1:-1])
        elif c == "." and len(tok) > 2 and tok[-1] == ".":
            cur.append(Enum(tok[1:-1].upper()))
        elif c in _NAME_START:
            pending = tok
        elif c == '"':
            cur.append(tok)
        elif c == "/" and tok.startswith("/*"):
            continue
        else:
            raise InvalidInput(f"Unreadable STEP syntax near {tok!r}")
    if len(stack) != 1 or len(stack[0][0]) != 1:
        raise InvalidInput("Unbalanced parentheses in a STEP argument list")
    return stack[0][0][0]


class StepFile:
    """An indexed STEP file. `of_type` and `get` are the whole interface."""

    def __init__(self, text: str):
        self._text = text
        self._span: dict[int, tuple[str, int, int]] = {}
        self._ids_by_type: dict[str, list[int]] = {}
        self._cache: dict[int, Entity] = {}
        self.header: dict[str, list] = {}

        start = 0
        in_data = False
        for m in _STATEMENT.finditer(text):
            if m.group() != ";":
                continue
            end = m.start()
            if in_data:
                inst = _INSTANCE.match(text, start, end)
                if inst:
                    etype = inst.group(2).upper()
                    self._span[int(inst.group(1))] = (etype, inst.end(), end)
                    self._ids_by_type.setdefault(etype, []).append(int(inst.group(1)))
            else:
                head = _HEADER.match(text, start, end)
                if head:
                    self.header[head.group(1).upper()] = parse_args(text[head.end():end])
                elif re.sub(r"/\*.*?\*/", "", text[start:end], flags=re.S).strip().upper() == "DATA":
                    in_data = True
            start = m.end()

        if not in_data:
            raise InvalidInput("Not a STEP file: no DATA section was found.")

    def __len__(self) -> int:
        return len(self._span)

    def types(self) -> dict[str, int]:
        return {t: len(ids) for t, ids in self._ids_by_type.items()}

    def type_of(self, ref: int) -> str | None:
        span = self._span.get(int(ref))
        return span[0] if span else None

    def get(self, ref: int | None) -> Entity | None:
        """The instance behind a reference. None for an unset attribute or a
        reference to an instance the file does not contain."""
        if ref is None or not isinstance(ref, int):
            return None
        ref = int(ref)
        hit = self._cache.get(ref)
        if hit is not None:
            return hit
        span = self._span.get(ref)
        if span is None:
            return None
        etype, a, b = span
        entity = Entity(ref, etype, parse_args(self._text[a:b]))
        self._cache[ref] = entity
        return entity

    def of_type(self, *types: str) -> list[Entity]:
        return [self.get(i) for t in types for i in self._ids_by_type.get(t.upper(), [])]
