import { redirect } from "next/navigation";
import { getSession } from "@/lib/auth";
import { signInAction } from "@/modules/identity/actions";
import { ActionForm } from "@/components/action-form";
import { Field } from "@/components/ui";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>;
}) {
  // searchParams is a Promise in Next.js 16.
  const { next } = await searchParams;

  if (await getSession()) redirect(next ?? "/projects");

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4 dark:bg-slate-950">
      <div className="w-full max-w-sm">
        <div className="mb-6">
          <h1 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            SmartPage Intelligence
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Sign in to continue
          </p>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <ActionForm action={signInAction} submitLabel="Sign in">
            <input type="hidden" name="next" value={next ?? "/projects"} />
            <Field
              label="Email"
              name="email"
              type="email"
              required
              placeholder="you@smartpage.example"
            />
            <Field label="Password" name="password" type="password" required />
          </ActionForm>
        </div>

        <p className="mt-4 text-center text-xs text-slate-500 dark:text-slate-400">
          Accounts are created by an administrator. Signing in requires an
          active membership in an organization.
        </p>
      </div>
    </main>
  );
}
