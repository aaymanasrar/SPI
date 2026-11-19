import "server-only";
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

/**
 * Supabase Auth client, server side.
 *
 * Supabase owns credentials, sessions and JWTs only. It does not own
 * authorization — what a user may do is decided entirely by our own
 * memberships/roles/permissions tables (see lib/rbac.ts). Keeping that split
 * means the permission model stays inspectable and auditable in the database
 * rather than spread across a vendor's dashboard.
 */
export async function createSupabaseServerClient() {
  const cookieStore = await cookies();

  return createServerClient(
    process.env.SUPABASE_URL!,
    process.env.SUPABASE_PUBLISHABLE_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          try {
            for (const { name, value, options } of cookiesToSet) {
              cookieStore.set(name, value, options);
            }
          } catch {
            // Called from a Server Component, where cookies are read-only.
            // Session refresh is handled in proxy.ts instead, so this is safe
            // to ignore rather than surface as an error.
          }
        },
      },
    }
  );
}
