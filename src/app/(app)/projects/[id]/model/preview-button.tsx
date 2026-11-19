"use client";

import { useActionState } from "react";
import { InlineSubmit } from "@/components/action-form";
import type { ActionState } from "@/lib/action";

/** One-button form that renders a missing picture of a drawing. */
export function PreviewButton({
  action,
  projectId,
  documentId,
}: {
  action: (prev: ActionState, formData: FormData) => Promise<ActionState>;
  projectId: string;
  documentId: string;
}) {
  const [state, formAction] = useActionState<ActionState, FormData>(action, { ok: true });
  return (
    <form action={formAction} className="flex items-center gap-2">
      <input type="hidden" name="projectId" value={projectId} />
      <input type="hidden" name="documentId" value={documentId} />
      <InlineSubmit label="Make preview" />
      {!state.ok && <span className="text-xs text-danger">{state.error}</span>}
    </form>
  );
}
