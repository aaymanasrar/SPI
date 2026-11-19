#!/usr/bin/env bash
# The TypeScript TOOL_POLICY and the Python TOOL_REGISTRY are maintained by hand
# in two languages. Drift is silent and goes wrong both ways: a tool with no
# policy throws "Unknown craft tool" at the user, and a policy for a tool the
# engine does not implement advertises a phantom to the orchestrator.
set -uo pipefail
cd "$(dirname "$0")/../.."
fail=0

if [ ! -x engines/.venv/bin/python ]; then
  echo "  engines/.venv is not built; cannot compare against the registry."
  exit 1
fi

registry=$(cd engines && ./.venv/bin/python -c "
import craft
from craft.core import TOOL_REGISTRY
for n, s in sorted(TOOL_REGISTRY.items()):
    print(n, 'implemented' if s.implemented else 'stub')
")
# Digits are allowed in a tool name (cad.scene_3d); the first version of this
# pattern excluded them and reported a registered tool as missing.
policy=$(grep -oE '^  \"[a-z0-9]+\.[a-z0-9_]+\":' src/modules/craft/tools.ts | tr -d ' ":')

implemented=$(echo "$registry" | awk '$2=="implemented"{print $1}' | sort)
stubs=$(echo "$registry" | awk '$2=="stub"{print $1}' | sort)
have=$(echo "$policy" | sort)

missing=$(comm -23 <(echo "$implemented") <(echo "$have"))
if [ -n "$missing" ]; then
  echo "  FAIL implemented in the engine but absent from TOOL_POLICY:"
  echo "$missing" | sed 's/^/        /'
  fail=1
fi

phantom=$(comm -13 <(echo "$registry" | awk '{print $1}' | sort) <(echo "$have"))
if [ -n "$phantom" ]; then
  echo "  FAIL in TOOL_POLICY but not registered in the engine:"
  echo "$phantom" | sed 's/^/        /'
  fail=1
fi

advertised_stub=$(comm -12 <(echo "$stubs") <(echo "$have"))
if [ -n "$advertised_stub" ]; then
  echo "  FAIL TOOL_POLICY advertises a tool the engine has not implemented:"
  echo "$advertised_stub" | sed 's/^/        /'
  fail=1
fi

n_impl=$(echo "$implemented" | grep -c .)
if [ "$n_impl" -lt 2 ]; then
  echo "  FAIL only $n_impl implemented tools found; the registry probe is broken."
  fail=1
fi

if [ "$fail" -eq 0 ]; then
  echo "  ok    $n_impl implemented tools, all with a policy"
  echo "  ok    $(echo "$stubs" | grep -c .) stub(s) correctly not advertised"
fi
exit "$fail"
