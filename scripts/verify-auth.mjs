#!/usr/bin/env node
// End-to-end check of the authentication and authorization chain:
// Supabase credentials -> our user -> organization -> role -> permissions.
//
// Also asserts the commercial visibility boundary: the Client role must hold
// no permission that exposes internal cost or margin (spec 13.3, 21.1, 29.1).
//
//   node scripts/verify-auth.mjs [email] [password]

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

const sql = postgres(env.DATABASE_URL || env.LOCAL_DATABASE_URL, {
  transform: postgres.camel,
  onnotice: () => {},
});

let failures = 0;
const check = (label, passed, detail = "") => {
  if (!passed) failures++;
  console.log(`  ${passed ? "pass" : "FAIL"}  ${label}${detail ? ` — ${detail}` : ""}`);
};

try {
  console.log("\nAuthentication chain\n");

  const res = await fetch(
    `${env.SUPABASE_URL}/auth/v1/token?grant_type=password`,
    {
      method: "POST",
      headers: {
        apikey: env.SUPABASE_PUBLISHABLE_KEY,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ email, password }),
    }
  );
  const auth = await res.json();
  check("Supabase accepts the credentials", Boolean(auth.user), auth.user?.id);

  if (auth.user) {
    const rows = await sql`
      select u.name, o.name as organization_name, r.name as role_name,
             coalesce(array_agg(p.code) filter (where p.code is not null),
                      array[]::text[]) as permissions
        from users u
        join memberships m   on m.user_id = u.id and m.status = 'active'
        join organizations o on o.id = m.organization_id and o.status = 'active'
        join roles r         on r.id = m.role_id
        left join role_permissions rp on rp.role_id = r.id
        left join permissions p       on p.id = rp.permission_id
       where u.auth_user_id = ${auth.user.id} and u.status = 'active'
       group by u.id, u.name, o.name, r.name
    `;
    const s = rows[0];
    check("Session resolves to a user, organization and role", Boolean(s),
      s ? `${s.name} · ${s.roleName} · ${s.organizationName}` : "no membership");

    if (s) {
      check("Permissions are attached", s.permissions.length > 0,
        `${s.permissions.length} permissions`);
      check("Holds project.create", s.permissions.includes("project.create"));
      check("Holds building_model.edit",
        s.permissions.includes("building_model.edit"));
    }
  }

  // A Supabase account with no membership must yield no session. Identity
  // alone grants nothing.
  const [orphan] = await sql`
    select count(*)::int as n
      from users u
      left join memberships m on m.user_id = u.id and m.status = 'active'
     where m.id is null and u.auth_user_id is not null
  `;
  console.log(`\n  (users with an auth identity but no active membership: ${orphan.n})`);

  console.log("\nCommercial visibility boundary\n");
  const [client] = await sql`
    select coalesce(array_agg(p.code) filter (where p.code is not null),
                    array[]::text[]) as perms
      from roles r
      left join role_permissions rp on rp.role_id = r.id
      left join permissions p       on p.id = rp.permission_id
     where r.code = 'client'
     group by r.id
  `;
  check("Client role cannot see internal cost or margin",
    !client.perms.includes("pricing.view_internal"),
    `holds: ${client.perms.join(", ") || "(none)"}`);
  check("Client role cannot edit the building model",
    !client.perms.includes("building_model.edit"));
  check("Client role cannot approve a quotation",
    !client.perms.includes("quotation.approve"));

  console.log(failures ? `\n${failures} FAILURE(S)\n` : "\nAll checks passed.\n");
  process.exitCode = failures ? 1 : 0;
} catch (error) {
  console.error("Error:", error.message);
  process.exitCode = 1;
} finally {
  await sql.end();
}
