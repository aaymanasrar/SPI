import "server-only";
import { randomUUID } from "node:crypto";
import path from "node:path";
import { transaction } from "@/lib/db";
import { recordAudit } from "@/lib/audit";
import type { Session } from "@/lib/auth";
import * as craftRepo from "@/modules/craft/repository";
import { policyFor } from "@/modules/craft/tools";
import { runTool, type CraftResult } from "@/modules/craft/client";
import { storageRoot } from "@/modules/prototype/storage";

/**
 * Run one engine tool for a project and record it: the HTTP call outside any
 * transaction (craft/actions.ts explains why), then the operation row, its
 * output documents and the audit entry together. Server-only, not a Server
 * Action: exported from a "use server" file it would be callable by anyone.
 */

export const CLASSIFICATION: Record<string, string> = {
  "application/dxf": "drawing",
  "image/vnd.dxf": "drawing",
  "image/svg+xml": "drawing",
  // A review workbook is SPI's BOQ for the project. It is never offered as a
  // client BOQ to check: those are uploads (no source operation).
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "boq",
};


export function outputKey(organizationId: string, projectId: string, name: string): string {
  return path.posix.join("org", organizationId, "project", projectId, "outputs",
    `${randomUUID()}-${name}`);
}

export type Recorded = {
  operationId: string;
  result: CraftResult;
  documents: { id: string; storageKey: string; name: string }[];
};

export async function runAndRecord(
  session: Session,
  projectId: string,
  tool: string,
  mode: "preview" | "commit",
  input: Record<string, unknown>,
  inputDocumentIds: string[],
  timeoutMs?: number
): Promise<Recorded> {
  const policy = policyFor(tool);
  // --- outside the transaction, deliberately ---
  const result = await runTool(tool, {
    mode,
    input,
    storageRoot: storageRoot(),
    // A takeoff with unmapped blocks, or a model with uncounted elements, is
    // still worth showing: the gaps are listed with it, not hidden.
    acceptMissingData: true,
    timeoutMs,
  });
  return transaction(async (tx) => {
    const op = await craftRepo.recordOperation(tx, {
      organizationId: session.organizationId,
      projectId,
      engine: policy.engine,
      tool,
      actorType: "user",
      actorId: session.userId,
      mode,
      input,
      output: result.outputs,
      inputDocumentIds,
      outputDocumentIds: [],
      provenance: result.provenance,
      missing: result.missing,
      warnings: result.warnings,
      assumptions: result.assumptions ?? [],
      findings: result.findings ?? [],
      status: result.status,
      error:
        result.status === "error"
          ? result.error || result.warnings.join("; ") || "Engine error"
          : null,
      durationMs: result.duration_ms,
      engineVersion: result.engine_version,
    });
    const documents: Recorded["documents"] = [];
    for (const f of result.files) {
      if (!f.storage_key) continue;
      const doc = await craftRepo.recordOutputDocument(tx, {
        organizationId: session.organizationId,
        projectId,
        filename: f.name,
        contentType: f.mime,
        byteSize: f.byte_size,
        checksumSha256: f.sha256,
        storageKey: f.storage_key,
        classification: CLASSIFICATION[f.mime] ?? "other",
        uploadedBy: session.userId,
        sourceOperationId: op.id,
      });
      documents.push({ id: doc.id, storageKey: f.storage_key, name: f.name });
    }
    await recordAudit(
      session,
      {
        action: `craft.${mode}`,
        subjectType: "craft_operation",
        subjectId: op.id,
        after: { tool, status: result.status, documentIds: documents.map((d) => d.id) },
      },
      tx
    );
    return { operationId: op.id, result, documents };
  });
}

/** Why a run produced nothing usable, in words a person can act on. */
export function failure(tool: string, r: CraftResult): string {
  if (r.status === "error") return `${tool} failed: ${r.error ?? "engine error"}`;
  if (r.status === "invalid_input") return `${tool} could not read the input: ${r.warnings.join("; ")}`;
  const missing = r.missing.map((m) => m.note || `${m.record}.${m.field}`).join(" ");
  return `${tool} needs more information: ${missing}`;
}

export async function renderPreview(session: Session, projectId: string, doc: { id: string; storageKey: string; name: string }) {
  const name = `${path.basename(doc.name, path.extname(doc.name)).replace(/[^\w.-]+/g, "_")}.svg`;
  return runAndRecord(session, projectId, "cad.render_svg", "commit", {
    document_id: doc.id,
    storage_key: doc.storageKey,
    output_key: outputKey(session.organizationId, projectId, name),
    output_name: name,
  }, [doc.id]);
}

