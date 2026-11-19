#!/usr/bin/env bash
# Tests scripts/npm-licence-policy.mjs against synthetic trees.
#
# Planting a real AGPL package proves the gate works once; this proves it for
# every case the policy names, including the two that bit me before: a gate that
# inspects nothing and passes, and an exception whose pattern is loose enough to
# excuse a package it was never meant to cover.
set -uo pipefail
cd "$(dirname "$0")/../.."
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
pass=0; fail=0

expect() { # description, want_exit, json
  printf '%s' "$3" > "$tmp/l.json"
  out=$(node scripts/npm-licence-policy.mjs "$tmp/l.json" 2>&1); got=$?
  if [ "$got" -eq "$2" ]; then
    pass=$((pass+1)); printf '  ok    %s\n' "$1"
  else
    fail=$((fail+1)); printf '  FAIL  %s (wanted exit %s, got %s)\n%s\n' "$1" "$2" "$got" "$out"
  fi
}

# Two allowed packages so the "inspected < 2" guard is not what fails the case.
P='"filler-a@1.0.0":{"licenses":"MIT"},"filler-b@1.0.0":{"licenses":"ISC"},'

expect "AGPL is refused"                 1 "{$P\"x@1.0.0\":{\"licenses\":\"AGPL-3.0\"}}"
expect "AGPL written as Affero"          1 "{$P\"x@1.0.0\":{\"licenses\":\"GNU Affero General Public License v3\"}}"
expect "GPL-3.0 is refused"              1 "{$P\"x@1.0.0\":{\"licenses\":\"GPL-3.0\"}}"
expect "LGPL without an exception"       1 "{$P\"x@1.0.0\":{\"licenses\":\"LGPL-3.0-or-later\"}}"
expect "SSPL is refused"                 1 "{$P\"x@1.0.0\":{\"licenses\":\"SSPL-1.0\"}}"
expect "forbidden by name despite MIT"   1 "{$P\"hyperformula@2.0.0\":{\"licenses\":\"MIT\"}}"
expect "UNKNOWN is not cleared"          1 "{$P\"x@1.0.0\":{\"licenses\":\"UNKNOWN\"}}"
expect "absent licence is not cleared"   1 "{$P\"x@1.0.0\":{}}"
expect "exception does not cover a near-miss name" \
                                         1 "{$P\"@img/sharp-wasm32-evil@1.0.0\":{\"licenses\":\"LGPL-3.0-or-later\"}}"
expect "an empty report is not a pass"   1 "{}"
expect "one package is not enough to pass" 1 "{\"only@1.0.0\":{\"licenses\":\"MIT\"}}"
expect "allowed licences pass"           0 "{$P\"x@1.0.0\":{\"licenses\":\"Apache-2.0\"}}"
expect "compound all-allowed passes"     0 "{$P\"x@1.0.0\":{\"licenses\":\"(MIT OR Apache-2.0)\"}}"
expect "recorded exception passes"       0 "{$P\"@img/sharp-wasm32@0.35.4\":{\"licenses\":\"Apache-2.0 AND LGPL-3.0-or-later AND MIT\"}}"

echo
echo "licence policy: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
