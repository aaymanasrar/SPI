#!/usr/bin/env node
// Applies supabase/migrations/*.sql to a Supabase project using the
// Management API, which accepts a personal access token (sbp_...).
//
// Why this exists alongside scripts/migrate.sh:
//   migrate.sh needs DATABASE_URL, which means knowing the project's database
//   password. A personal access token is copied whole from the dashboard with
//   nothing to substitute, which is a good deal less error-prone.
//
//   .env needs:
//     SUPABASE_ACCESS_TOKEN=sbp_...          account -> Access Tokens
//     SUPABASE_PROJECT_REF=xxxxxxxxxxxx      the ref in your project URL
//
// Usage:  node scripts/migrate-supabase.mjs [--dry-run]

import { readFileSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

// Minimal .env reader — avoids a dependency for six lines of parsing.
function loadEnv() {
  const env = {};
  try {
    for (const line of readFileSync(join(root, ".env"), "utf8").split("\n")) {
      const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)$/);
      if (m) env[m[1]] = m[2].trim().replace(/^["']|["']$/g, "");
    }
  } catch {
    /* no .env */
  }
  return { ...env, ...process.env };
}

const env = loadEnv();
const token = env.SUPABASE_ACCESS_TOKEN;
const ref = env.SUPABASE_PROJECT_REF;
const dryRun = process.argv.includes("--dry-run");

const missing = [
  !token && "SUPABASE_ACCESS_TOKEN",
  !ref && "SUPABASE_PROJECT_REF",
].filter(Boolean);

if (missing.length) {
  console.error(`Missing in .env: ${missing.join(", ")}\n`);
  console.error("SUPABASE_ACCESS_TOKEN — https://supabase.com/dashboard/account/tokens");
  console.error("  Sign in as the account that owns the project, Generate new token,");
  console.error("  copy the whole sbp_... string. Shown once.\n");
  console.error("SUPABASE_PROJECT_REF — the id in your project URL,");
  console.error("  e.g. https://<ref>.supabase.co");
  process.exit(1);
}

async function runSql(query) {
  const res = await fetch(
    `https://api.supabase.com/v1/projects/${ref}/database/query`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ query }),
    }
  );
  const text = await res.text();
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${text.slice(0, 500)}`);
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

const files = readdirSync(join(root, "supabase/migrations"))
  .filter((f) => f.endsWith(".sql"))
  .sort();

console.log(`Target project: ${ref}`);
console.log(`Migrations:     ${files.length}${dryRun ? "  (dry run)" : ""}\n`);

if (dryRun) {
  // Verifies the token and ref reach the right database before writing anything.
  try {
    const who = await runSql(
      "select current_database() as db, current_user as role, version() as version"
    );
    console.log("Connection OK:", JSON.stringify(who));
    files.forEach((f) => console.log(`  would apply  ${f}`));
  } catch (err) {
    console.error("Connection FAILED:", err.message);
    process.exit(1);
  }
  process.exit(0);
}

for (const file of files) {
  process.stdout.write(`  ${file.padEnd(46)}`);
  try {
    await runSql(readFileSync(join(root, "supabase/migrations", file), "utf8"));
    console.log("ok");
  } catch (err) {
    console.log("FAILED");
    console.error(`\n${err.message}\n`);
    process.exit(1);
  }
}

console.log("\nAll migrations applied. Verifying…\n");

const check = await runSql(`
  select
    (select count(*) from pg_tables where schemaname='public')                       as tables,
    (select count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace
       where n.nspname='public' and c.relkind='r' and c.relrowsecurity)              as rls_enabled,
    (select count(*) from systems)      as systems,
    (select count(*) from roles)        as roles,
    (select count(*) from permissions)  as permissions,
    (select count(*) from manufacturers)+(select count(*) from products)
      +(select count(*) from engineering_rules)+(select count(*) from vendor_prices) as engineering_rows;
`);
console.log(JSON.stringify(check, null, 2));
