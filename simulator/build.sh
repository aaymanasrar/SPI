#!/usr/bin/env bash
# Build the ELV building simulator page from an IFC model.
#
#   simulator/build.sh                         # the Revit-style fixture office
#   simulator/build.sh model.ifc [map.json]    # any IFC; with no map, only IFC's
#                                              # standard device types are counted
#   simulator/build.sh plan-L0.dxf plan-L1.pdf # floor plans, lowest level first:
#                                              # a 3D prototype of the building
#   simulator/build.sh --demo-plans            # the fixture office's floor plans
#
# Runs the real bim.scene_3d tool over the model, pulls the rules it applies
# out of the rules library migration, and assembles one HTML file in out/
# (gitignored: everything there can be rebuilt from here).
set -euo pipefail
cd "$(dirname "$0")/.."
PY=engines/.venv/bin/python
OUT="${SPI_OUT:-out/simulator}"
mkdir -p "$OUT"
abspath() { (cd "$(dirname "$1")" && printf '%s/%s\n' "$(pwd)" "$(basename "$1")"); }

FIXTURE=""
TOOL=scene
if [ "${1:-}" = "--demo-plans" ]; then
  "$PY" engines/fixtures/floor_plans.py "$OUT/demo-plans" >/dev/null
  set -- "$OUT/demo-plans/plan-L0.dxf" "$OUT/demo-plans/plan-L1.dxf"
  FIXTURE="Fixture drawings (engines/fixtures/floor_plans.py), not a project."
fi
case "${1:-}" in
  *.dxf|*.DXF|*.pdf|*.PDF|*.png|*.PNG|*.jpg|*.JPG|*.jpeg|*.JPEG|*.tif|*.tiff|*.TIF|*.TIFF) TOOL=prototype ;;
esac
if [ "$TOOL" = prototype ]; then
  PLANS=()
  for f in "$@"; do [ -f "$f" ] || { echo "No such file: $f" >&2; exit 2; }; PLANS+=("$(abspath "$f")"); done
  IFC="${PLANS[0]}"
  MAP=""
elif [ $# -ge 1 ]; then
  [ -f "$1" ] || { echo "No such file: $1" >&2; exit 2; }
  IFC="$(abspath "$1")"
  MAP="${2:+$(abspath "$2")}"
else
  IFC="$(abspath "$OUT/SPT-Demo-Office.ifc")"
  MAP="$(abspath engines/fixtures/spt_element_map.json)"
  "$PY" engines/fixtures/revit_elv_office.py IFC4 > "$IFC"
  FIXTURE="Fixture model, written the way Revit exports one (engines/fixtures/revit_elv_office.py). It is not a project: no client Revit model has been supplied."
fi
NAME="$(basename "${IFC%.*}")"
SCENE="$(abspath "$OUT/$NAME.scene.json")"
PAGE="$OUT/$NAME-simulator.html"

if [ "$TOOL" = prototype ]; then
  echo "  prototype from ${#PLANS[@]} plan(s), devices proposed from the rules library"
  "$PY" simulator/rules.py --device-rules > "$OUT/device-rules.json"
  DEVRULES="$(abspath "$OUT/device-rules.json")"
  (cd engines && PYTHONPATH="$PWD" ./.venv/bin/python -m craft.bim prototype "${PLANS[@]}" --device-rules "$DEVRULES" --out "$SCENE")
else
  echo "  scene  $(basename "$IFC")${MAP:+ with $(basename "$MAP")}"
  (cd engines && PYTHONPATH="$PWD" ./.venv/bin/python -m craft.bim scene "$IFC" ${MAP:+--map "$MAP"} --out "$SCENE")
fi
"$PY" simulator/rules.py > "$OUT/rules.json"

# JSON goes inside a <script>; "</" must not end it early.
embed() { "$PY" -c 'import sys; sys.stdout.write(open(sys.argv[1], encoding="utf-8").read().replace("</", "<\\/"))' "$1"; }
META="$("$PY" -c 'import json, sys; print(json.dumps({"fixture": sys.argv[1] or None, "source_file": sys.argv[2]}).replace("</", "<\\/"))' "$FIXTURE" "$(basename "$IFC")")"

{
  cat simulator/head.html simulator/body.html
  printf '<script>window.__SCENE__='; embed "$SCENE"
  printf ';\nwindow.__RULES__='; embed "$OUT/rules.json"
  printf ';\nwindow.__META__=%s;</script>\n' "$META"
  printf '<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>\n'
  printf '<script>\n(function () {\n"use strict";\n'
  cat simulator/sim/*.js
  printf '})();\n</script>\n</body>\n</html>\n'
} > "$PAGE"

# A page that does not parse is not a page. Check before anyone opens it.
node -e '
const fs = require("fs");
const h = fs.readFileSync(process.argv[1], "utf8");
const blocks = [...h.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
blocks.forEach((b, i) => { try { new Function(b); }
  catch (e) { console.error("SYNTAX ERROR in inline block " + i + ": " + e.message); process.exit(1); } });
const ids = new Set([...h.matchAll(/id="([a-zA-Z0-9_-]+)"/g)].map(m => m[1]));
const used = [...new Set([...h.matchAll(/(?:getElementById|\$)\("([a-zA-Z0-9_-]+)"\)/g)].map(m => m[1]))];
const missing = used.filter(u => !ids.has(u));
if (missing.length) { console.error("script references missing ids: " + missing.join(", ")); process.exit(1); }
console.log("  " + blocks.length + " inline blocks parse, " + used.length + " element ids all present");
' "$PAGE"

echo "  built  $PAGE ($(wc -c < "$PAGE" | tr -d " ") bytes)"
