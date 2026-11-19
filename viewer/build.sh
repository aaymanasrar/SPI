#!/usr/bin/env bash
# Assemble the walkthrough page from its parts.
#
#   viewer/build.sh            # KG building (reads the scene from out/)
#
# The page is one HTML file because an Artifact is one HTML file. These parts
# are the source; the assembled page is generated and lives in out/, which is
# gitignored because it can always be rebuilt from here.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="${SPI_OUT:-out/walkthrough}"
SCENE="$OUT/kg.json"

if [ ! -f "$SCENE" ]; then
  echo "No scene at $SCENE. Build it first:" >&2
  echo "  cd engines && PYTHONPATH=\$PWD ./.venv/bin/python fixtures/build_kg_scene.py" >&2
  exit 1
fi

mkdir -p "$OUT"
{
  cat viewer/head.html
  cat viewer/body.html
  printf '<script>window.__KG__='
  cat "$SCENE"
  printf ';</script>\n'
  printf '<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>\n'
  printf '<script>\n(function(){\n'
  cat viewer/build1.js viewer/build2.js viewer/build3.js viewer/build4.js
  printf '})();\n</script>\n'
} > "$OUT/kg-walkthrough.html"

# A page that does not parse is not a page. Check before anyone publishes it.
node -e '
const fs=require("fs");
const h=fs.readFileSync(process.argv[1],"utf8");
const blocks=[...h.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
blocks.forEach((b,i)=>{ try{ new Function(b); }
  catch(e){ console.error("SYNTAX ERROR in inline block "+i+": "+e.message); process.exit(1); } });
const ids=new Set([...h.matchAll(/id="([a-zA-Z0-9_-]+)"/g)].map(m=>m[1]));
const used=[...new Set([...h.matchAll(/getElementById\("([a-zA-Z0-9_-]+)"\)/g)].map(m=>m[1]))];
const missing=used.filter(u=>!ids.has(u));
if(missing.length){ console.error("script references missing ids: "+missing.join(", ")); process.exit(1); }
console.log("  "+blocks.length+" inline blocks parse, "+used.length+" element ids all present");
' "$OUT/kg-walkthrough.html"

echo "  built $OUT/kg-walkthrough.html ($(wc -c < "$OUT/kg-walkthrough.html") bytes)"
