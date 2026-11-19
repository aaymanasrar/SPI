import Link from "next/link";
import { requireSession } from "@/lib/auth";
import { signOutAction } from "@/modules/identity/actions";

const nav = [
  { href: "/projects", label: "Projects", icon: "M3 7h18M3 12h18M3 17h12" },
  { href: "/clients", label: "Clients", icon: "M16 19v-1a4 4 0 0 0-8 0v1M12 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" },
];

function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]!.toUpperCase())
    .join("");
}

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await requireSession();

  return (
    <div className="min-h-screen md:flex">
      <aside className="glass sticky top-0 z-20 flex items-center justify-between gap-3 border-0 border-b px-4 py-3 md:m-3 md:h-[calc(100vh-1.5rem)] md:w-56 md:shrink-0 md:flex-col md:items-stretch md:justify-start md:rounded-2xl md:border md:p-3">
        <Link href="/projects" className="flex items-center gap-2 px-2 md:py-2">
          <span className="grid h-7 w-7 place-items-center rounded-lg bg-accent text-[13px] font-bold text-accent-ink">
            S
          </span>
          <span className="text-[15px] font-medium tracking-tight">
            SmartPage<span className="text-muted">.</span>
          </span>
        </Link>

        <nav className="flex gap-1 md:mt-6 md:flex-col">
          {nav.map((n) => (
            <Link
              key={n.href}
              href={n.href}
              className="flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm text-muted transition hover:bg-white/5 hover:text-foreground"
            >
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" aria-hidden>
                <path d={n.icon} />
              </svg>
              <span className="hidden sm:inline">{n.label}</span>
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-2.5 md:mt-auto md:rounded-xl md:bg-surface-2 md:p-2.5">
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-accent text-xs font-semibold text-accent-ink">
            {initials(session.name)}
          </span>
          <div className="hidden min-w-0 flex-1 md:block">
            <div className="truncate text-xs font-medium">{session.name}</div>
            {/* Role is shown deliberately: what a user can do here depends on
                it, and a hidden action is confusing if you cannot see why. */}
            <div className="truncate text-[11px] text-muted">
              {session.roleName} · {session.organizationName}
            </div>
          </div>
          <form action={signOutAction}>
            <button
              type="submit"
              title="Sign out"
              className="rounded-full border border-line-strong px-2 py-1 text-[11px] text-muted hover:text-foreground"
            >
              Sign out
            </button>
          </form>
        </div>
      </aside>

      <main className="min-w-0 flex-1 px-4 py-5 md:px-6 md:py-6">{children}</main>
    </div>
  );
}
