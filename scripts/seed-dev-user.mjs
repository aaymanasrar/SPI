#!/usr/bin/env node
// Creates a development sign-in: a Supabase Auth user, plus the organization,
// user row and membership that grant it access.
//
// Both halves are required by design. A Supabase account with no active
// membership gets no session — identity alone grants nothing (lib/auth.ts).
//
//   node scripts/seed-dev-user.mjs [email] [password] [roleCode]
//
// Default role is super_admin so the first account can set everything else up.
// Idempotent: re-running updates the password and re-links the membership.

import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import postgres from "postgres";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

const env = {};
for (const line of readFileSync(join(root, ".env"), "utf8").split("\n")) {
  const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)$/);
  if (m) env[m[1]] = m[2].trim().replace(/^["']|["']$/g, "");
}

const email = process.argv[2] || "dev@smartpage.local";
const password = process.argv[3] || "smartpage-dev-password";
const roleCode = process.argv[4] || "super_admin";

const supabaseUrl = env.SUPABASE_URL;
const secretKey = env.SUPABASE_SECRET_KEY;
const dbUrl = env.DATABASE_URL || env.LOCAL_DATABASE_URL;

if (!supabaseUrl || !secretKey) {
  console.error("Need SUPABASE_URL and SUPABASE_SECRET_KEY in .env");
  process.exit(1);
}

// --- 1. Supabase Auth user -------------------------------------------------

const adminHeaders = {
  apikey: secretKey,
  Authorization: `Bearer ${secretKey}`,
  "Content-Type": "application/json",
};

async function findOrCreateAuthUser() {
  const search = await fetch(
    `${supabaseUrl}/auth/v1/admin/users?page=1&per_page=200`,
    { headers: adminHeaders }
  );
  if (!search.ok) {
    throw new Error(`Auth list failed: ${search.status} ${await search.text()}`);
  }
  const { users = [] } = await search.json();
  const existing = users.find(
    (u) => u.email?.toLowerCase() === email.toLowerCase()
  );

  if (existing) {
    const upd = await fetch(`${supabaseUrl}/auth/v1/admin/users/${existing.id}`, {
      method: "PUT",
      headers: adminHeaders,
      body: JSON.stringify({ password, email_confirm: true }),
    });
    if (!upd.ok) throw new Error(`Password update failed: ${await upd.text()}`);
    return { id: existing.id, created: false };
  }

  const res = await fetch(`${supabaseUrl}/auth/v1/admin/users`, {
    method: "POST",
    headers: adminHeaders,
    // Confirmed immediately: there is no mail delivery in development.
    body: JSON.stringify({ email, password, email_confirm: true }),
  });
  if (!res.ok) throw new Error(`Auth create failed: ${await res.text()}`);
  const created = await res.json();
  return { id: created.id, created: true };
}

// --- 2. Organization, user row and membership ------------------------------

const sql = postgres(dbUrl, { transform: postgres.camel, onnotice: () => {} });

try {
  const authUser = await findOrCreateAuthUser();

  await sql.begin(async (tx) => {
    const [org] = await tx`
      insert into organizations (name, slug)
      values ('SmartPage Technology Arabia', 'smartpage')
      on conflict (slug) do update set name = excluded.name
      returning id, name
    `;

    const [role] = await tx`select id, name from roles where code = ${roleCode}`;
    if (!role) throw new Error(`No such role: ${roleCode}`);

    const [user] = await tx`
      insert into users (email, name, auth_user_id, status)
      values (${email}, ${email.split("@")[0]}, ${authUser.id}, 'active')
      on conflict (email) do update
        set auth_user_id = excluded.auth_user_id,
            status = 'active'
      returning id, email
    `;

    await tx`
      insert into memberships (user_id, organization_id, role_id, status)
      values (${user.id}, ${org.id}, ${role.id}, 'active')
      on conflict (user_id, organization_id) do update
        set role_id = excluded.role_id, status = 'active'
    `;

    const target = new URL(dbUrl);
    console.log(`\nDevelopment sign-in ready.\n`);
    console.log(`  Email        ${email}`);
    console.log(`  Password     ${password}`);
    console.log(`  Role         ${role.name}`);
    console.log(`  Organization ${org.name}`);
    console.log(`  Auth user    ${authUser.id} (${authUser.created ? "created" : "existing"})`);
    console.log(`  Database     ${target.hostname}${target.pathname}\n`);
  });
} catch (error) {
  console.error("Failed:", error.message);
  process.exitCode = 1;
} finally {
  await sql.end();
}
