import type { ReactNode } from "react";
import type {
  DashboardFloor,
  DashboardOperation,
} from "@/modules/dashboard/repository";

/* Dashboard visuals. Plain SVG rendered on the server: no chart library, no
   client JS. Each one draws only the numbers it is given. */

const fmt = new Intl.NumberFormat("en", { maximumFractionDigits: 1 });

export function Panel({
  title,
  subtitle,
  actions,
  children,
  className = "",
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`glass rise rounded-2xl p-4 ${className}`}>
      {(title || actions) && (
        <header className="mb-3 flex items-start justify-between gap-3">
          <div>
            <h2 className="text-[15px] font-medium tracking-tight">{title}</h2>
            {subtitle && <p className="text-[11px] text-muted">{subtitle}</p>}
          </div>
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}

export function KpiTile({
  label,
  value,
  unit,
  badge,
  badgeTone = "accent",
  children,
}: {
  label: string;
  value: ReactNode;
  unit?: string;
  badge?: string;
  badgeTone?: "accent" | "leaf" | "warn";
  children?: ReactNode;
}) {
  const tone = {
    accent: "bg-accent-soft text-accent",
    leaf: "bg-leaf-soft text-leaf",
    warn: "bg-warn/15 text-warn",
  }[badgeTone];
  return (
    <div className="flex min-h-36 flex-col rounded-xl border border-line bg-surface-2 p-3">
      <div className="text-[11px] text-muted">{label}</div>
      <div className="mt-1 flex items-baseline gap-1.5">
        <span className="text-2xl font-light tabular-nums">{value}</span>
        {unit && <span className="text-xs text-muted">{unit}</span>}
        {badge && (
          <span className={`ml-auto whitespace-nowrap rounded-full px-2 py-0.5 text-[10px] font-medium ${tone}`}>
            {badge}
          </span>
        )}
      </div>
      <div className="mt-auto pt-2">{children}</div>
    </div>
  );
}

/** Filled line; needs at least two points to say anything. */
export function Sparkline({ values }: { values: number[] }) {
  if (values.length < 2) {
    return <div className="h-12 border-b border-dashed border-line-strong" />;
  }
  const w = 160;
  const h = 48;
  const max = Math.max(...values);
  const min = Math.min(...values);
  const span = max - min || 1;
  const pts = values.map((v, i) => [
    (i / (values.length - 1)) * w,
    h - 4 - ((v - min) / span) * (h - 8),
  ]);
  const line = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join("");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-12 w-full" preserveAspectRatio="none" aria-hidden>
      <defs>
        <linearGradient id="spark-fill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="var(--accent)" stopOpacity="0.35" />
          <stop offset="1" stopColor="var(--accent)" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={`${line}L${w},${h}L0,${h}Z`} fill="url(#spark-fill)" />
      <path d={line} fill="none" stroke="var(--accent)" strokeWidth="1.6" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

/** Half-ring gauge with tick marks, for a share between 0 and 1. */
export function Gauge({ value, caption }: { value: number | null; caption: string }) {
  const r = 52;
  const cx = 64;
  const cy = 64;
  const arc = Math.PI * r;
  const v = value ?? 0;
  const ticks = Array.from({ length: 25 }, (_, i) => {
    const a = Math.PI + (i / 24) * Math.PI;
    return [cx + Math.cos(a) * (r + 6), cy + Math.sin(a) * (r + 6), cx + Math.cos(a) * (r + 10), cy + Math.sin(a) * (r + 10)];
  });
  return (
    <div className="relative mx-auto w-full max-w-40">
      <svg viewBox="0 0 128 72" className="w-full" aria-hidden>
        {ticks.map(([x1, y1, x2, y2], i) => (
          <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--line-strong)" strokeWidth="1" />
        ))}
        <path d={`M${cx - r},${cy} A${r},${r} 0 0 1 ${cx + r},${cy}`} fill="none" stroke="rgb(255 255 255 / 0.07)" strokeWidth="9" strokeLinecap="round" />
        {value !== null && (
          <path
            d={`M${cx - r},${cy} A${r},${r} 0 0 1 ${cx + r},${cy}`}
            fill="none"
            stroke="var(--accent)"
            strokeWidth="9"
            strokeLinecap="round"
            strokeDasharray={`${arc * v} ${arc}`}
          />
        )}
      </svg>
      <div className="absolute inset-x-0 bottom-0 text-center">
        <div className="text-2xl font-light tabular-nums leading-none">
          {value === null ? "—" : `${Math.round(v * 100)}%`}
        </div>
        <div className="mt-1 text-[9px] uppercase tracking-[0.2em] text-muted">{caption}</div>
      </div>
    </div>
  );
}

/** Capsule bars; the largest is lit in gold and labelled. */
export function BarChart({
  bars,
  unit,
}: {
  bars: { label: string; value: number }[];
  unit: string;
}) {
  if (bars.length === 0) return null;
  const max = Math.max(...bars.map((b) => b.value), 1);
  const top = bars.reduce((best, b, i) => (b.value > bars[best].value ? i : best), 0);
  const step = niceStep(max);
  const ceiling = Math.ceil(max / step) * step;
  const gridLines = Array.from({ length: Math.round(ceiling / step) + 1 }, (_, i) => i * step).reverse();
  return (
    <div className="flex gap-3">
      <div className="flex h-56 flex-col justify-between pt-8 pb-6 text-right text-[10px] tabular-nums text-faint">
        {gridLines.map((g) => (
          <span key={g}>{fmt.format(g)}</span>
        ))}
      </div>
      <div className="flex h-56 flex-1 items-end gap-2 pt-8">
        {bars.map((b, i) => {
          const pct = (b.value / ceiling) * 100;
          const lit = i === top;
          return (
            <div key={`${b.label}-${i}`} className="flex h-full min-w-7 flex-1 flex-col items-center">
              <div className="relative flex w-full flex-1 items-end justify-center">
                {lit && (
                  <span
                    className="absolute z-10 -translate-y-full whitespace-nowrap rounded-full bg-accent px-2 py-0.5 text-[10px] font-medium text-accent-ink"
                    style={{ bottom: `calc(${pct}% + 6px)` }}
                  >
                    {b.label} · {fmt.format(b.value)} {unit}
                  </span>
                )}
                <div
                  title={`${b.label}: ${fmt.format(b.value)} ${unit}`}
                  className="w-3.5 rounded-full"
                  style={{
                    height: `${Math.max(pct, 3)}%`,
                    background: lit
                      ? "linear-gradient(180deg, #f3d488, var(--accent))"
                      : "linear-gradient(180deg, rgb(231 238 228 / 0.75), rgb(231 238 228 / 0.12))",
                  }}
                />
              </div>
              <span className="mt-2 h-4 max-w-full truncate text-[10px] text-faint">{b.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function niceStep(max: number) {
  const raw = max / 5;
  const pow = 10 ** Math.floor(Math.log10(raw || 1));
  const n = raw / pow;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * pow;
}

const donutColors = ["var(--accent)", "var(--leaf)", "#c9d4c4", "#5f7564", "#3c5243"];

/** Ring split by share, with a legend. Groups past the fourth into "Other". */
export function Donut({
  slices,
  centerLabel,
}: {
  slices: { label: string; value: number }[];
  centerLabel: string;
}) {
  const sorted = [...slices].sort((a, b) => b.value - a.value);
  const shown = sorted.slice(0, 4);
  const rest = sorted.slice(4).reduce((s, x) => s + x.value, 0);
  if (rest > 0) shown.push({ label: "Other", value: rest });
  const total = shown.reduce((s, x) => s + x.value, 0);
  const r = 40;
  const c = 2 * Math.PI * r;
  const offsets = shown.map((_, i) =>
    shown.slice(0, i).reduce((sum, x) => sum + (x.value / total) * c, 0)
  );
  return (
    <div className="flex items-center gap-5">
      <div className="relative h-32 w-32 shrink-0">
        <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90" aria-hidden>
          <circle cx="50" cy="50" r={r} fill="none" stroke="rgb(255 255 255 / 0.06)" strokeWidth="9" />
          {shown.map((s, i) => {
            const len = (s.value / total) * c;
            return (
              <circle
                key={s.label}
                cx="50"
                cy="50"
                r={r}
                fill="none"
                stroke={donutColors[i]}
                strokeWidth="9"
                strokeDasharray={`${Math.max(len - 2, 0.5)} ${c}`}
                strokeDashoffset={-offsets[i]}
              />
            );
          })}
        </svg>
        <div className="absolute inset-0 grid place-items-center text-center">
          <div>
            <div className="text-xl font-light tabular-nums">{total}</div>
            <div className="text-[9px] uppercase tracking-[0.18em] text-muted">{centerLabel}</div>
          </div>
        </div>
      </div>
      <ul className="min-w-0 flex-1 space-y-2">
        {shown.map((s, i) => (
          <li key={s.label} className="flex items-center gap-2 text-xs">
            <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: donutColors[i] }} />
            <span className="truncate text-muted">{s.label}</span>
            <span className="ml-auto tabular-nums">{Math.round((s.value / total) * 100)}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

const roomTone: Record<string, string> = {
  approved: "border-accent/70 bg-accent/20 text-accent",
  not_required: "border-leaf/35 bg-leaf/12 text-foreground/85",
  pending: "border-dashed border-warn/70 bg-warn/10 text-warn",
  rejected: "border-danger/60 bg-danger/12 text-danger",
};

/**
 * The building as stacked floors, each split into its rooms with width
 * proportional to area. A schematic, not a plan: no geometry is stored yet, so
 * position inside a floor means nothing beyond order by size.
 */
export function BuildingCanvas({
  floors,
  overlay,
  callout,
}: {
  floors: DashboardFloor[];
  overlay?: ReactNode;
  callout?: ReactNode;
}) {
  return (
    <div className="blueprint relative flex min-h-[300px] flex-1 sm:min-h-[420px] flex-col overflow-hidden rounded-xl border border-line">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_40%,rgb(8_16_11/0.75))]" />
      <div className="relative flex flex-1 flex-col justify-center gap-2.5 p-5 sm:pr-64">
        {floors.map((f) => {
          const known = f.rooms.map((r) => r.areaSqm ?? 0);
          const fallback = Math.max(...known, 0) / 3 || 1;
          const area = f.rooms.reduce((s, r) => s + (r.areaSqm ?? 0), 0);
          return (
            <div key={f.id} className="flex items-stretch gap-3">
              <div className="w-16 shrink-0 py-1 text-right sm:w-20">
                <div className="text-[11px] font-medium">{f.name}</div>
                <div className="text-[10px] tabular-nums text-faint">
                  L{f.level} · {area > 0 ? `${fmt.format(area)} m²` : `${f.rooms.length} rooms`}
                </div>
              </div>
              <div className="flex min-h-12 min-w-0 flex-1 gap-1 rounded-lg border border-line-strong bg-black/20 p-1">
                {f.rooms.length === 0 ? (
                  <span className="self-center px-2 text-[11px] text-faint">No rooms yet</span>
                ) : (
                  f.rooms.map((r) => (
                    <div
                      key={r.id}
                      title={`${r.name}${r.areaSqm ? ` · ${fmt.format(r.areaSqm)} m²` : ""} · ${r.reviewStatus.replace("_", " ")}`}
                      className={`flex min-w-0 items-end overflow-hidden rounded-md border px-1.5 py-1 text-[10px] transition hover:brightness-125 ${roomTone[r.reviewStatus]}`}
                      style={{ flex: `${r.areaSqm ?? fallback} 1 0` }}
                    >
                      <span className="truncate">{r.code ?? r.name}</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>
      {overlay && <div className="absolute right-3 top-3 hidden sm:flex flex-col items-end gap-2">{overlay}</div>}
      {callout && <div className="absolute bottom-3 right-3 hidden w-56 sm:block">{callout}</div>}
    </div>
  );
}

export function FloatPill({ children, lit }: { children: ReactNode; lit?: boolean }) {
  return (
    <span
      className={`rounded-full px-3 py-1 text-xs backdrop-blur-md ${
        lit ? "bg-accent font-medium text-accent-ink" : "border border-line-strong bg-black/45 text-foreground/90"
      }`}
    >
      {children}
    </span>
  );
}

const ago = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
function relative(d: Date) {
  const s = (new Date(d).getTime() - Date.now()) / 1000;
  const units: [Intl.RelativeTimeFormatUnit, number][] = [["day", 86400], ["hour", 3600], ["minute", 60]];
  for (const [u, n] of units) if (Math.abs(s) >= n) return ago.format(Math.round(s / n), u);
  return "just now";
}

const engineMark: Record<string, string> = { grid: "XL", word: "W", cad: "CAD", pdf: "PDF", bim: "BIM" };

export function ActivityList({ operations }: { operations: DashboardOperation[] }) {
  if (operations.length === 0) {
    return <p className="py-4 text-xs text-muted">No engine runs on this project yet.</p>;
  }
  return (
    <ul className="space-y-2.5">
      {operations.map((o) => (
        <li key={o.id} className="flex items-center gap-3">
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-surface-3 text-[9px] font-semibold tracking-wide text-accent">
            {engineMark[o.engine] ?? o.engine.slice(0, 3).toUpperCase()}
          </span>
          <div className="min-w-0 flex-1">
            <div className="truncate text-xs">{o.tool}</div>
            <div className="text-[10px] text-faint">
              {relative(o.createdAt)}
              {o.durationMs != null && ` · ${fmt.format(o.durationMs / 1000)} s`}
            </div>
          </div>
          <span
            className={`h-1.5 w-1.5 shrink-0 rounded-full ${
              o.status === "ok" ? "bg-leaf" : o.status === "missing_data" ? "bg-warn" : "bg-danger"
            }`}
            title={o.status.replace("_", " ")}
          />
        </li>
      ))}
    </ul>
  );
}
