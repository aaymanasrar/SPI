"use server";

import { z } from "zod";
import { redirect } from "next/navigation";
import { createSupabaseServerClient } from "@/lib/supabase";
import { sql } from "@/lib/db";
import { runAction, type ActionState } from "@/lib/action";

/**
 * Sign in and sign out.
 *
 * Supabase verifies the credentials. Whether the account may then do anything
 * is a separate question answered by memberships/roles/permissions — see
 * lib/auth.ts, which returns no session for a valid Supabase user with no
 * active membership.
 */

const signInSchema = z.object({
  email: z.email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
  next: z.string().startsWith("/").catch("/projects"),
});

export async function signInAction(
  _prev: ActionState,
  formData: FormData
): Promise<ActionState> {
  const result = await runAction(async () => {
    const input = signInSchema.parse({
      email: formData.get("email") ?? "",
      password: formData.get("password") ?? "",
      next: formData.get("next") ?? "/projects",
    });

    const supabase = await createSupabaseServerClient();
    const { data, error } = await supabase.auth.signInWithPassword({
      email: input.email,
      password: input.password,
    });

    if (error || !data.user) {
      // Deliberately uniform: distinguishing "no such account" from "wrong
      // password" tells an attacker which emails are registered.
      return { ok: false, error: "Incorrect email or password." };
    }

    const rows = await sql`
      select 1
        from users u
        join memberships m on m.user_id = u.id and m.status = 'active'
       where u.auth_user_id = ${data.user.id}
         and u.status = 'active'
       limit 1
    `;

    if (rows.length === 0) {
      await supabase.auth.signOut();
      return {
        ok: false,
        error:
          "This account has no active access. Ask an administrator to invite you to an organization.",
      };
    }

    return { ok: true, message: input.next };
  });

  // redirect() throws a control-flow exception, so it must happen outside
  // runAction's try/catch or it would be swallowed as an error.
  if (result.ok && result.message?.startsWith("/")) redirect(result.message);
  return result;
}

export async function signOutAction(): Promise<void> {
  const supabase = await createSupabaseServerClient();
  await supabase.auth.signOut();
  redirect("/login");
}
