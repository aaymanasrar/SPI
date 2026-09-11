"use client";

import { useActionState, type ReactNode } from "react";
import { useFormStatus } from "react-dom";
import type { ActionState } from "@/lib/action";

/**
 * Form wrapper that surfaces pending state and the result of a Server Action.
 *
 * Errors are shown rather than swallowed. In a system where a wrong number
 * reaches a customer quotation, a mutation that silently fails is worse than
 * one that fails loudly.
 */
export function ActionForm({
  action,
  children,
  submitLabel,
  resetOnSuccess,
}: {
  action: (prev: ActionState, formData: FormData) => Promise<ActionState>;
  children: ReactNode;
  submitLabel: string;
  resetOnSuccess?: boolean;
}) {
  const [state, formAction] = useActionState<ActionState, FormData>(action, {
    ok: true,
  });

  const fieldErrors = !state.ok ? state.fieldErrors : undefined;

  return (
    <form
      action={formAction}
      key={resetOnSuccess && state.ok && state.message ? state.message : "form"}
      className="space-y-3"
    >
      {children}

      {fieldErrors && (
        <ul className="space-y-0.5 text-xs text-rose-700 dark:text-rose-400">
          {Object.entries(fieldErrors).map(([field, messages]) => (
            <li key={field}>
              <span className="font-medium">{field}:</span> {messages.join(", ")}
            </li>
          ))}
        </ul>
      )}

      {!state.ok && (
        <p className="rounded-md bg-rose-50 px-3 py-2 text-xs text-rose-800 dark:bg-rose-950/50 dark:text-rose-300">
          {state.error}
        </p>
      )}

      {state.ok && state.message && (
        <p className="rounded-md bg-teal-50 px-3 py-2 text-xs text-teal-800 dark:bg-teal-950/50 dark:text-teal-300">
          {state.message}
        </p>
      )}

      <Submit label={submitLabel} />
    </form>
  );
}

function Submit({ label }: { label: string }) {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className="rounded-md bg-teal-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-800 disabled:opacity-50"
    >
      {pending ? "Working…" : label}
    </button>
  );
}

/** Small inline submit for one-button forms in table rows. */
export function InlineSubmit({ label }: { label: string }) {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className="rounded border border-slate-300 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
    >
      {pending ? "…" : label}
    </button>
  );
}
