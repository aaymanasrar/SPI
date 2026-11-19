"""Run a BIM tool on a local IFC file, without the HTTP service.

    python -m craft.bim read   model.ifc
    python -m craft.bim count  model.ifc [--map element_map.json] [--storey "Level 1"]
    python -m craft.bim spaces model.ifc
    python -m craft.bim scene  model.ifc [--map element_map.json] [--out scene.json]
    python -m craft.bim prototype ground.dxf first.pdf ... [--name NAME] [--out scene.json]
        one floor plan per level, lowest first: DXF, PDF (--page) or a scanned image

Prints the full result envelope as JSON — status, outputs, missing values,
findings — exactly as the service would return it.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from ..core import CraftError, LocalStorage
from . import (CountInput, ReadIfcInput, SceneInput, SpacesInput, count_devices,
               extract_spaces, read_ifc, scene_3d)
from .prototype import PrototypeInput, prototype


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m craft.bim", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("tool", choices=["read", "count", "spaces", "scene", "prototype"])
    p.add_argument("ifc", type=Path, nargs="+", help="an IFC model, or floor plans for prototype")
    p.add_argument("--name", help="building name (prototype)")
    p.add_argument("--page", type=int, action="append", help="PDF page per plan (prototype)")
    p.add_argument("--scale", help="drawing scale, e.g. 1:100 (prototype, scanned plans)")
    p.add_argument("--known-length", type=float, help="overall building length in m, to calibrate a scan")
    p.add_argument("--storey-height", type=float, help="floor-to-floor height in m (prototype)")
    p.add_argument("--device-rules", type=Path, help="placement rules JSON: propose an ELV layout (prototype)")
    p.add_argument("--map", type=Path, help="element map JSON (count, scene)")
    p.add_argument("--storey", action="append", help="restrict to a storey; repeatable")
    p.add_argument("--out", type=Path, help="write the JSON here instead of stdout")
    args = p.parse_args(argv)

    for f in args.ifc:
        if not f.is_file():
            print(f"No such file: {f}", file=sys.stderr)
            return 2
    if args.tool != "prototype" and len(args.ifc) != 1:
        print(f"{args.tool} takes one IFC file", file=sys.stderr)
        return 2
    files = [f.resolve() for f in args.ifc]
    common_root = Path(os.path.commonpath([str(f.parent) for f in files]))
    storage = LocalStorage(common_root)
    first = files[0]
    common = {"document_id": first.name, "storage_key": str(first.relative_to(common_root))}
    element_map = json.loads(args.map.read_text(encoding="utf-8")) if args.map else None

    try:
        if args.tool == "prototype":
            pages = args.page or []
            levels = []
            for i, f in enumerate(files):
                level = {"document_id": f.name, "storage_key": str(f.relative_to(common_root)),
                         "page": pages[i] if i < len(pages) else 1}
                if args.scale:
                    level["scale"] = args.scale
                if args.known_length:
                    level["known_length_m"] = args.known_length
                levels.append(level)
            rules = json.loads(args.device_rules.read_text(encoding="utf-8")) if args.device_rules else None
            res = prototype(PrototypeInput(document_id=first.name, name=args.name, levels=levels,
                                           storey_height_m=args.storey_height, device_rules=rules),
                            storage=storage)
        elif args.tool == "read":
            res = read_ifc(ReadIfcInput(**common), storage=storage)
        elif args.tool == "spaces":
            res = extract_spaces(SpacesInput(**common, storeys=args.storey), storage=storage)
        elif args.tool == "count":
            res = count_devices(CountInput(**common, element_map=element_map,
                                           storeys=args.storey), storage=storage)
        else:
            res = scene_3d(SceneInput(**common, element_map=element_map,
                                      storeys=args.storey), storage=storage)
    except CraftError as e:
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        return 1

    text = json.dumps(res.model_dump(), ensure_ascii=False, indent=1)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"{res.tool}: {res.status} → {args.out}", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
