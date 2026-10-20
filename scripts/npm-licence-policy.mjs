#!/usr/bin/env node
/**
 * Evaluates `license-checker --json` against the project's licence policy.
 *
 * A flat `grep GPL` cannot express the policy, which is not "no GPL" but "no
 * AGPL, and no GPL shipped to the browser". LGPL in a server-side native
 * binary that is dynamically linked is a different question from GPL compiled
 * into a client bundle, and the gate has to tell them apart or it will either
 * block Next.js itself or wave through something that matters.
 *
 * Exit 0 = within policy (exceptions, if any, are printed). Exit 1 = violation.
 */
import { readFileSync } from "node:fs";

const ALLOWED = [
  /^MIT/, /^BSD/, /^Apache-2\.0$/, /^ISC$/, /^0BSD$/, /^Unlicense$/,
  /^Python-2\.0$/, /^PSF/, /^MPL-2\.0$/, /^BlueOak-1\.0\.0$/,
  // Data, not code: browser-support tables and SPDX list fragments.
  /^CC0-1\.0$/, /^CC-BY-3\.0$/, /^CC-BY-4\.0$/,
];

/** Always forbidden, by name, however they are licensed. */
const DENIED_PACKAGES = [/^hyperformula/, /^@handsontable/, /^open-design/, /^teigha/];

/**
 * Recorded exceptions. Each one needs a reason that answers "why is this not a
 * problem?" — not "it was already there". Anything GPL-family not listed here
 * fails the gate.
 */
const EXCEPTIONS = [
  {
    match: /^@img\/sharp-libvips-/,
    licence: "LGPL-3.0-or-later",
    reason:
      "Server-side only. This is libvips, pulled in by next -> sharp for image " +
      "optimisation; it runs in the Node process as a dynamically linked native " +
      "binary and is never shipped to the browser. LGPL dynamic linking imposes " +
      "no obligation on our own source. Removing it means giving up Next image " +
      "optimisation.",
    signedOff: false,
  },
  {
    // Named exactly, not /^@img\/sharp-/: a future @img package that DID reach
    // the browser must fail this gate rather than inherit an excuse.
    match: /^@img\/sharp-wasm32$/,
    licence: "Apache-2.0 AND LGPL-3.0-or-later AND MIT",
    reason:
      "Server-side only, same libvips code compiled to WebAssembly. It is an " +
      "unconstrained optional dependency of sharp (no os/cpu field in the lock), " +
      "so npm ci installs it on every platform even though darwin-arm64 uses the " +
      "native build; it exists for webcontainers and FreeBSD. 'wasm' here does " +
      "not mean browser: Next runs sharp in the server runtime and does not " +
      "bundle it into client JS.",
    signedOff: false,
  },
];

const raw = JSON.parse(readFileSync(process.argv[2], "utf8"));
const selfName = JSON.parse(readFileSync("package.json", "utf8")).name;

const violations = [];
const exceptionsInForce = [];
const unknown = [];
let inspected = 0;

for (const [id, meta] of Object.entries(raw)) {
  const name = id.slice(0, id.lastIndexOf("@"));
  // The project's own package is not a dependency of itself. It is UNLICENSED
  // on purpose (private), and must not be graded by its own gate.
  if (name === selfName) continue;
  inspected++;

  const licence = String(meta.licenses ?? "").trim();
  if (DENIED_PACKAGES.some((re) => re.test(name))) {
    violations.push([name, licence, "package is on the forbidden list"]);
    continue;
  }
  if (!licence || /UNKNOWN/i.test(licence)) {
    unknown.push([name, licence || "(none)"]);
    continue;
  }
  if (/AGPL|Affero/i.test(licence)) {
    violations.push([name, licence, "AGPL is forbidden outright"]);
    continue;
  }

  // Split compound expressions; a package is fine if every term is allowed.
  const terms = licence.split(/\s+(?:AND|OR)\s+|,\s*/).map((t) => t.replace(/[()]/g, "").trim()).filter(Boolean);
  const unallowed = terms.filter((t) => !ALLOWED.some((re) => re.test(t)));
  if (unallowed.length === 0) continue;

  const ack = EXCEPTIONS.find((e) => e.match.test(name));
  if (ack) {
    exceptionsInForce.push([name, licence, ack]);
    continue;
  }
  violations.push([name, licence, `not in the allowed set (${unallowed.join(", ")})`]);
}

if (inspected < 2) {
  console.log("  ERROR: inspected only " + inspected + " packages; the report or parse is broken.");
  process.exit(1);
}
console.log(`  ${inspected} packages inspected`);

if (exceptionsInForce.length) {
  console.log("  RECORDED EXCEPTIONS (in force, awaiting sign-off):");
  for (const [name, licence, ack] of exceptionsInForce) {
    console.log(`    ${name}  ${licence}`);
    console.log(`      ${ack.reason.replace(/(.{76}) /g, "$1\n      ")}`);
    if (!ack.signedOff) console.log("      STATUS: not yet signed off by the licence owner.");
  }
}

let bad = false;
if (unknown.length) {
  console.log("  LICENCE COULD NOT BE DETERMINED (an unreadable licence is not a cleared licence):");
  for (const [n, l] of unknown) console.log(`    ${n}  ${l}`);
  bad = true;
}
if (violations.length) {
  console.log("  LICENCE POLICY VIOLATION:");
  for (const [n, l, why] of violations) console.log(`    ${n}  ${l}  -- ${why}`);
  bad = true;
}
if (!bad && !exceptionsInForce.length) console.log("  all within policy");
process.exit(bad ? 1 : 0);
