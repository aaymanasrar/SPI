"""CADCraft: inventory a DXF.

Reports what is actually in the file — layers, blocks, inserts, text, polylines,
units — so an engineer can see what a count would be based on before anyone
counts anything.
"""
from __future__ import annotations

import io
import time
from collections import Counter

import ezdxf
from ezdxf.lldxf.const import DXFError
from pydantic import BaseModel

from ..core import ENGINE_VERSION, InvalidInput, Storage, ToolResult, register
from .units import describe


class ReadDxfInput(BaseModel):
    document_id: str
    storage_key: str
    include_text: bool = True


def open_dxf(raw: bytes, storage_key: str):
    """Shared loader. ezdxf needs text, and DXF files are not always UTF-8."""
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return ezdxf.read(io.StringIO(raw.decode(encoding)))
        except UnicodeDecodeError:
            continue
        except DXFError as e:
            raise InvalidInput(
                f"{storage_key} is not a readable DXF: {e}. If this is a DWG, it "
                "must be converted first — no DWG reader is installed, because "
                "the usual one (ODA SDK) is not licence-compatible.") from e
    raise InvalidInput(
        f"{storage_key} could not be decoded as text. A binary DXF or a DWG must "
        "be converted to ASCII DXF first.")


@register("cad.read_dxf", "cad", ReadDxfInput,
          "Inventory a DXF: layers, blocks, inserts, text, polylines and units",
          modes=("preview",))
def read_dxf(data: ReadDxfInput, storage: Storage | None = None) -> ToolResult:
    started = time.perf_counter()
    res = ToolResult(tool="cad.read_dxf", engine_version=ENGINE_VERSION)
    if storage is None:
        raise InvalidInput("cad.read_dxf needs storage to fetch the document")

    doc = open_dxf(storage.read(data.storage_key), data.storage_key)
    msp = doc.modelspace()

    insunits = int(doc.header.get("$INSUNITS", 0))
    unit_name, metres_per_unit = describe(insunits)

    inserts: Counter[tuple[str, str]] = Counter()
    kinds: Counter[str] = Counter()
    entity_layers: set[str] = set()
    texts: list[dict] = []
    polylines: list[dict] = []

    for e in msp:
        kind = e.dxftype()
        kinds[kind] += 1
        layer = str(getattr(e.dxf, "layer", ""))
        entity_layers.add(layer)
        if kind == "INSERT":
            inserts[(str(e.dxf.name), layer)] += 1
        elif kind in ("TEXT", "MTEXT") and data.include_text:
            content = e.plain_text() if kind == "MTEXT" else str(e.dxf.text)
            pos = e.dxf.insert if kind == "MTEXT" else e.dxf.insert
            texts.append({"layer": layer, "text": content,
                          "x": round(float(pos[0]), 3), "y": round(float(pos[1]), 3)})
        elif kind in ("LWPOLYLINE", "POLYLINE"):
            try:
                pts = [(round(float(p[0]), 3), round(float(p[1]), 3))
                       for p in e.get_points("xy")] if kind == "LWPOLYLINE" else \
                      [(round(float(v.dxf.location[0]), 3),
                        round(float(v.dxf.location[1]), 3)) for v in e.vertices]
            except Exception:
                pts = []
            polylines.append({"layer": layer, "closed": bool(e.closed),
                              "point_count": len(pts), "points": pts})

    res.outputs = {
        "dxf_version": doc.dxfversion,
        "units": {"insunits": insunits, "name": unit_name,
                  "metres_per_unit": metres_per_unit},
        # Two different lists on purpose. A layer can be defined and unused, and
        # an entity can name a layer with no record in the layer table. A layer
        # filter matches on the name an entity carries, so both must be visible.
        "layers": sorted(l.dxf.name for l in doc.layers),
        "entity_layers": sorted(entity_layers),
        "block_definitions": sorted(b.name for b in doc.blocks
                                    if not b.name.startswith("*")),
        "entity_counts": dict(sorted(kinds.items())),
        "inserts": [{"block": b, "layer": l, "count": n}
                    for (b, l), n in sorted(inserts.items())],
        "insert_total": sum(inserts.values()),
        "text": texts,
        "polylines": polylines,
    }

    if metres_per_unit is None:
        res.warnings.append(
            f"Drawing declares no units ($INSUNITS={insunits}, {unit_name}). "
            "Counting is unaffected; any length, area or cable route from this "
            "file will refuse to produce a real-world figure.")
    undeclared = entity_layers - {l.dxf.name for l in doc.layers}
    if undeclared:
        res.warnings.append(
            "Entities sit on layer(s) with no record in the layer table: "
            + ", ".join(sorted(undeclared))
            + ". They are listed under entity_layers and can still be filtered "
              "on by name.")
    if not inserts:
        res.warnings.append(
            "No block inserts found. Devices drawn as loose lines and circles "
            "rather than blocks cannot be counted by block name.")

    res.duration_ms = int((time.perf_counter() - started) * 1000)
    return res
