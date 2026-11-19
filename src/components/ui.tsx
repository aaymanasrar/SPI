import type { ReactNode } from "react";

/* Shared presentational primitives. Dense by intent — this is an engineering
   tool, so legibility of numbers and status matters more than decoration. The
   look (glass panels, gold accent) lives in globals.css tokens. */

export function Card({
  title,
  description,
  actions,
  children,
}: {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <section className="glass rounded-2xl">
      {(title || actions) && (
        <header className="flex items-start justify-between gap-4 px-5 pt-4 pb-3">
          <div>
            {title && (
              <h2 className="text-[15px] font-medium tracking-tight text-foreground">
                {title}
              </h2>
            )}
            {description && (
              <p className="mt-0.5 text-xs text-muted">{description}</p>
            )}
          </div>
          {actions}
        </header>
      )}
      <div className="px-5 pb-5 pt-1">{children}</div>
    </section>
  );
}

const inputClass =
  "w-full rounded-lg border border-line-strong bg-black/25 px-3 py-2 text-sm text-foreground outline-none placeholder:text-faint focus:border-accent focus:ring-2 focus:ring-accent/25";

export function Field({
  label,
  name,
  type = "text",
  required,
  placeholder,
  defaultValue,
  hint,
  step,
  children,
}: {
  label: string;
  name?: string;
  type?: string;
  required?: boolean;
  placeholder?: string;
  defaultValue?: string | number | null;
  hint?: string;
  step?: string;
  children?: ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-muted">
        {label}
        {required && <span className="ml-0.5 text-danger">*</span>}
      </span>
      {children ?? (
        <input
          name={name}
          type={type}
          required={required}
          placeholder={placeholder}
          defaultValue={defaultValue ?? undefined}
          step={step}
          className={inputClass}
        />
      )}
      {hint && <span className="mt-1 block text-xs text-faint">{hint}</span>}
    </label>
  );
}

export function Select({
  label,
  name,
  options,
  defaultValue,
  includeBlank,
  hint,
}: {
  label: string;
  name: string;
  options: { value: string; label: string }[];
  defaultValue?: string | null;
  includeBlank?: string;
  hint?: string;
}) {
  return (
    <Field label={label} hint={hint}>
      <select name={name} defaultValue={defaultValue ?? ""} className={inputClass}>
        {includeBlank !== undefined && <option value="">{includeBlank}</option>}
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </Field>
  );
}

const statusTone: Record<string, string> = {
  draft: "bg-white/8 text-muted",
  active: "bg-leaf-soft text-leaf",
  on_hold: "bg-warn/15 text-warn",
  completed: "bg-accent-soft text-accent",
  archived: "bg-white/5 text-faint",
  pending: "bg-warn/15 text-warn",
  approved: "bg-leaf-soft text-leaf",
  rejected: "bg-danger/15 text-danger",
  not_required: "bg-white/8 text-muted",
  ok: "bg-leaf-soft text-leaf",
  missing_data: "bg-warn/15 text-warn",
  invalid_input: "bg-danger/15 text-danger",
  error: "bg-danger/15 text-danger",
};

export function Pill({ value }: { value: string }) {
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-[11px] font-medium ${
        statusTone[value] ?? statusTone.draft
      }`}
    >
      {value.replace(/_/g, " ")}
    </span>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="py-6 text-center text-sm text-muted">{children}</p>;
}

export function Table({
  head,
  children,
}: {
  head: string[];
  children: ReactNode;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line text-left">
            {head.map((h) => (
              <th
                key={h}
                className="px-2 py-2 text-[11px] font-medium uppercase tracking-wider text-faint"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">{children}</tbody>
      </table>
    </div>
  );
}

export function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="rounded-xl border border-line bg-surface-2 px-3 py-2.5">
      <div className="text-[11px] text-muted">{label}</div>
      <div className="mt-0.5 text-xl font-light tabular-nums text-foreground">
        {value}
      </div>
    </div>
  );
}

/** Shown where a permission is missing, instead of silently hiding a feature. */
export function NoPermission({ what }: { what: string }) {
  return (
    <p className="rounded-lg border border-dashed border-line-strong px-3 py-2 text-xs text-muted">
      Your role does not allow {what}.
    </p>
  );
}
