import Link from "next/link";
import { requireSession } from "@/lib/auth";
import { signOutAction } from "@/modules/identity/actions";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await requireSession();

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <header className="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-3">
          <div className="flex items-center gap-6">
            <Link
              href="/projects"
              className="text-sm font-semibold text-slate-900 dark:text-slate-100"
            >
              SmartPage Intelligence
            </Link>
            <nav className="flex gap-4 text-sm">
              <Link
                href="/projects"
                className="text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100"
              >
                Projects
              </Link>
              <Link
                href="/clients"
                className="text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100"
              >
                Clients
              </Link>
            </nav>
          </div>

          <div className="flex items-center gap-4">
            <div className="text-right">
              <div className="text-xs font-medium text-slate-900 dark:text-slate-100">
                {session.name}
              </div>
              {/* Role is shown deliberately: what a user can do here depends on
                  it, and a hidden action is confusing if you cannot see why. */}
              <div className="text-[11px] text-slate-500 dark:text-slate-400">
                {session.roleName} · {session.organizationName}
              </div>
            </div>
            <form action={signOutAction}>
              <button
                type="submit"
                className="rounded border border-slate-300 px-2 py-1 text-xs text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                Sign out
              </button>
            </form>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-5 py-6">{children}</main>
    </div>
  );
}
