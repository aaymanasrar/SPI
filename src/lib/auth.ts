import "server-only";
import { cache } from "react";
import { redirect } from "next/navigation";
import { sql } from "@/lib/db";
import { createSupabaseServerClient } from "@/lib/supabase";

/**
 * Session resolution: Supabase Auth identity -> our user, organization, role
 * and permission set.
 *
 * Supabase tells us *who* someone is. Everything about *what they may do*
 * comes from our own tables, so the permission model stays auditable in the
 * database (ARCHITECTURE.md §6.2).
 */

export type Session = {
  userId: string;
  authUserId: string;
  email: string;
  name: string;
  organizationId: string;
  organizationName: string;
  roleCode: string;
  roleName: string;
  permissions: ReadonlySet<string>;
};

type SessionRow = {
  userId: string;
  email: string;
  name: string;
  organizationId: string;
  organizationName: string;
  roleCode: string;
  roleName: string;
  permissions: string[];
};

/**
 * Cached per request: a page may check the session several times while
 * rendering, and this should not become several round trips.
 */
export const getSession = cache(async (): Promise<Session | null> => {
  const supabase = await createSupabaseServerClient();

  // getUser() revalidates the token with Supabase. getSession() would trust
  // the cookie, which is forgeable — never use it for authorization.
  const {
    data: { user },
    error,
  } = await supabase.auth.getUser();

  if (error || !user) return null;

  const rows = await sql<SessionRow[]>`
    select
      u.id                as user_id,
      u.email,
      u.name,
      o.id                as organization_id,
      o.name              as organization_name,
      r.code              as role_code,
      r.name              as role_name,
      coalesce(
        array_agg(p.code) filter (where p.code is not null),
        '{}'
      )                   as permissions
    from users u
    join memberships  m on m.user_id = u.id and m.status = 'active'
    join organizations o on o.id = m.organization_id and o.status = 'active'
    join roles        r on r.id = m.role_id
    left join role_permissions rp on rp.role_id = r.id
    left join permissions      p  on p.id = rp.permission_id
    where u.auth_user_id = ${user.id}
      and u.status = 'active'
    group by u.id, u.email, u.name, o.id, o.name, r.code, r.name
    limit 1
  `;

  const row = rows[0];

  // Authenticated with Supabase but with no active membership. Deliberately
  // treated as no session: identity alone grants nothing.
  if (!row) return null;

  return {
    userId: row.userId,
    authUserId: user.id,
    email: row.email,
    name: row.name,
    organizationId: row.organizationId,
    organizationName: row.organizationName,
    roleCode: row.roleCode,
    roleName: row.roleName,
    permissions: new Set(row.permissions),
  };
});

/** Session or redirect to login. For pages. */
export async function requireSession(): Promise<Session> {
  const session = await getSession();
  if (!session) redirect("/login");
  return session;
}

/**
 * Session or throw. For Server Actions and route handlers.
 *
 * Server Actions are reachable by direct POST, not only through the UI that
 * renders them, so every one must verify this itself. Hiding a button is not
 * an access control.
 */
export async function requireSessionOrThrow(): Promise<Session> {
  const session = await getSession();
  if (!session) throw new AuthError("Not authenticated");
  return session;
}

export class AuthError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AuthError";
  }
}

export class PermissionError extends Error {
  constructor(public readonly permission: string) {
    super(`Missing permission: ${permission}`);
    this.name = "PermissionError";
  }
}
