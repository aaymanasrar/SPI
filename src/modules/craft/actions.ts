"use server";

import { z } from "zod";
import { revalidatePath } from "next/cache";
import { sql, transaction } from "@/lib/db";
import { requirePermission } from "@/lib/rbac";
import { recordAudit } from "@/lib/audit";
import { runAction, type ActionState } from "@/lib/action";
import * as repo from "./repository";
import { policyFor } from "./tools";
import { runTool, type CraftResult } from "./client";

/**
 * Craft tool invocation.
 *
 * Ordering matters and is deliberate: the HTTP call happens OUTSIDE the
 * transaction. transaction() holds one of ten pooled connections, and a CAD
 * parse can take seconds — holding a connection for that would starve the pool
 * under any real load. The transaction opens only once the result is in hand,
 * so the operation row and its audit entry still commit together.
 */

const runToolSchema = z.object({
  tool: z.string().min(1),
  mode: z.enum(["preview", "commit"]),
  projectId: z.string().uuid().nullable(),
  input: z.record(z.string(), z.unknown()),
});

const MIME_CLASSIFICATION: Record<string, string> = {
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "boq",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "compliance",
  "application/pdf": "compliance",
  "image/vnd.dxf": "drawing",
  "application/dxf": "drawing",
  "application/x-step": "drawing",
};

export async function runCraftToolAction(
  _prev: ActionState,
  formData: FormData
): Promise<ActionState> {
  return runAction(async () => {
    const parsed = runToolSchema.parse({
      tool: formData.get("tool") ?? "",
      mode: formData.get("mode") ?? "preview",
      projectId: (formData.get("projectId") as string) || null,
      input: JSON.parse((formData.get("input") as string) || "{}"),
    });

    const policy = policyFor(parsed.tool);
    if (parsed.mode === "commit" && policy.commitPermission === null) {
      return { ok: false, error: `${parsed.tool} has no commit mode. Its output is a proposal.` };
    }

    const session = await requirePermission(
      parsed.mode === "commit" ? policy.commitPermission! : policy.previewPermission
    );

    // Nested ids arrive from a form and are attacker-controlled.
    if (parsed.projectId && !(await repo.assertProjectInOrg(sql, session.organizationId, parsed.projectId))) {
      return { ok: false, error: "Project not found." };
    }

    // --- outside the transaction, deliberately ---
    const result: CraftResult = await runTool(parsed.tool, {
      mode: parsed.mode,
      input: parsed.input,
    });

    const operation = await transaction(async (tx) => {
      const op = await repo.recordOperation(tx, {
        organizationId: session.organizationId,
        projectId: parsed.projectId,
        engine: policy.engine,
        tool: parsed.tool,
        actorType: "user",
        actorId: session.userId,
        mode: parsed.mode,
        input: parsed.input,
        output: result.outputs,
        inputDocumentIds: [],
        outputDocumentIds: [],
        provenance: result.provenance,
        missing: result.missing,
        warnings: result.warnings,
        assumptions: result.assumptions ?? [],
        findings: result.findings ?? [],
        status: result.status,
        // Prefer the engine's own message: ToolUnavailable sets `error` and no
        // warnings, and it is the one that names the missing program.
        error:
          result.status === "error"
            ? result.error || result.warnings.join("; ") || "Engine error"
            : null,
        durationMs: result.duration_ms,
        engineVersion: result.engine_version,
      });

      // Each produced file becomes a NEW document row pointing back at this run.
      const documentIds: string[] = [];
      for (const f of result.files) {
        if (!f.storage_key) continue;
        const doc = await repo.recordOutputDocument(tx, {
          organizationId: session.organizationId,
          projectId: parsed.projectId,
          filename: f.name,
          contentType: f.mime,
          byteSize: f.byte_size,
          checksumSha256: f.sha256,
          storageKey: f.storage_key,
          classification: MIME_CLASSIFICATION[f.mime] ?? "other",
          uploadedBy: session.userId,
          sourceOperationId: op.id,
        });
        documentIds.push(doc.id);
      }

      // Same transaction: an audit entry for a write that rolled back would be a
      // record of something that never happened.
      await recordAudit(
        session,
        {
          action: `craft.${parsed.mode}`,
          subjectType: "craft_operation",
          subjectId: op.id,
          after: {
            tool: parsed.tool,
            status: result.status,
            files: result.files.map((f) => f.name),
            documentIds,
          },
        },
        tx
      );
      return { ...op, documentIds };
    });

    if (parsed.projectId) revalidatePath(`/projects/${parsed.projectId}`);

    const fileNote = result.files.length
      ? ` Produced ${result.files.map((f) => f.name).join(", ")}.`
      : "";
    // The operation id is the provenance handle — it is how anyone later asks
    // "where did this file come from?", so it belongs in what the user sees.
    return {
      ok: true,
      message:
        `${parsed.tool} completed (${result.status}).${fileNote} ` +
        `Operation ${operation.id}.`,
    };
  });
}
