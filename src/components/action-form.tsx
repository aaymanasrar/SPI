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
        <p className="rounded-lg bg-danger/12 px-3 py-2 text-xs text-danger">
          {state.error}
        </p>
      )}

      {state.ok && state.message && (
        <p className="rounded-lg bg-leaf-soft px-3 py-2 text-xs text-leaf">
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
      className="rounded-full bg-accent px-4 py-1.5 text-sm font-medium text-accent-ink hover:brightness-110 disabled:opacity-50"
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
      className="rounded-full border border-line-strong px-2.5 py-1 text-xs font-medium text-foreground hover:bg-white/5 disabled:opacity-50"
    >
      {pending ? "…" : label}
    </button>
  );
}
