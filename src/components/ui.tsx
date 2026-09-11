import type { ReactNode } from "react";

/* Shared presentational primitives. Dense and plain by intent — this is an
   engineering tool, so legibility of numbers and status matters more than
   decoration. */

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
    <section className="rounded-lg border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
      {(title || actions) && (
        <header className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-3.5 dark:border-slate-800">
          <div>
            {title && (
              <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                {title}
              </h2>
            )}
            {description && (
              <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                {description}
              </p>
            )}
          </div>
          {actions}
        </header>
      )}
      <div className="px-5 py-4">{children}</div>
    </section>
  );
}

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
      <span className="mb-1 block text-xs font-medium text-slate-700 dark:text-slate-300">
        {label}
        {required && <span className="ml-0.5 text-rose-600">*</span>}
      </span>
      {children ?? (
        <input
          name={name}
          type={type}
          required={required}
          placeholder={placeholder}
          defaultValue={defaultValue ?? undefined}
          step={step}
          className="w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
        />
      )}
      {hint && (
        <span className="mt-1 block text-xs text-slate-500 dark:text-slate-400">
          {hint}
        </span>
      )}
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
      <select
        name={name}
        defaultValue={defaultValue ?? ""}
        className="w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-900 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
      >
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
  draft: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  active: "bg-teal-100 text-teal-800 dark:bg-teal-900/50 dark:text-teal-300",
  on_hold: "bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-300",
  completed: "bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300",
  archived: "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-500",
  pending: "bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-300",
  approved: "bg-teal-100 text-teal-800 dark:bg-teal-900/50 dark:text-teal-300",
  rejected: "bg-rose-100 text-rose-800 dark:bg-rose-900/50 dark:text-rose-300",
  not_required: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400",
};

export function Pill({ value }: { value: string }) {
  return (
    <span
      className={`inline-block rounded px-1.5 py-0.5 text-[11px] font-medium ${
        statusTone[value] ?? statusTone.draft
      }`}
    >
      {value.replace(/_/g, " ")}
    </span>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <p className="py-6 text-center text-sm text-slate-500 dark:text-slate-400">
      {children}
    </p>
  );
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
          <tr className="border-b border-slate-200 text-left dark:border-slate-800">
            {head.map((h) => (
              <th
                key={h}
                className="px-2 py-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {children}
        </tbody>
      </table>
    </div>
  );
}

export function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="rounded-md border border-slate-200 px-3 py-2 dark:border-slate-800">
      <div className="text-[11px] uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {label}
      </div>
      <div className="mt-0.5 text-lg font-semibold tabular-nums text-slate-900 dark:text-slate-100">
        {value}
      </div>
    </div>
  );
}

/** Shown where a permission is missing, instead of silently hiding a feature. */
export function NoPermission({ what }: { what: string }) {
  return (
    <p className="rounded-md border border-dashed border-slate-300 px-3 py-2 text-xs text-slate-500 dark:border-slate-700 dark:text-slate-400">
      Your role does not allow {what}.
    </p>
  );
}
