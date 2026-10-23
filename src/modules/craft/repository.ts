import "server-only";
import type postgres from "postgres";

/**
 * craft_operations is append-only (migration 0023). There is no update function
 * here and there cannot be one: the table rejects UPDATE at the database.
 */

export type CraftEngine = "grid" | "word" | "cad" | "pdf";
export type CraftMode = "preview" | "commit";
export type CraftStatus = "ok" | "missing_data" | "invalid_input" | "error";

export type RecordOperationInput = {
  organizationId: string;
  projectId: string | null;
  engine: CraftEngine;
  tool: string;
  actorType: "ai" | "user" | "system";
  actorId: string | null;
  mode: CraftMode;
  input: unknown;
  output: unknown;
  inputDocumentIds: string[];
  outputDocumentIds: string[];
  provenance: unknown;
  missing: unknown;
  warnings: unknown;
  status: CraftStatus;
  error: string | null;
  assumptions?: unknown[];
  findings?: unknown[];
  durationMs: number | null;
  engineVersion: string;
};

export type CraftOperation = { id: string; createdAt: string };

export async function recordOperation(
  tx: postgres.TransactionSql,
  input: RecordOperationInput
): Promise<CraftOperation> {
  const rows = await tx<CraftOperation[]>`
    insert into craft_operations (
      organization_id, project_id, engine, tool, actor_type, actor_id, mode,
      input_json, output_json, input_document_ids, output_document_ids,
      provenance_json, missing_json, warnings_json,
      assumptions_json, findings_json, status, error,
      duration_ms, engine_version
    ) values (
      ${input.organizationId}, ${input.projectId}, ${input.engine}, ${input.tool},
      ${input.actorType}, ${input.actorId}, ${input.mode},
      ${JSON.stringify(input.input ?? {})}, ${input.output === null ? null : JSON.stringify(input.output)},
      ${input.inputDocumentIds}, ${input.outputDocumentIds},
      ${JSON.stringify(input.provenance ?? [])}, ${JSON.stringify(input.missing ?? [])},
      ${JSON.stringify(input.warnings ?? [])},
      ${JSON.stringify(input.assumptions ?? [])},
      ${JSON.stringify(input.findings ?? [])},
      ${input.status}, ${input.error},
      ${input.durationMs}, ${input.engineVersion}
    )
    returning id, created_at`;
  return rows[0];
}

/** A craft output is a NEW document row, never an edit of the original (§7). */
export async function recordOutputDocument(
  tx: postgres.TransactionSql,
  input: {
    organizationId: string;
    projectId: string | null;
    filename: string;
    contentType: string;
    byteSize: number | null;
    checksumSha256: string | null;
    storageKey: string;
    classification: string;
    uploadedBy: string | null;
    sourceOperationId: string;
  }
): Promise<{ id: string }> {
  const rows = await tx<{ id: string }[]>`
    insert into documents (
      organization_id, project_id, filename, content_type, byte_size,
      checksum_sha256, storage_key, classification, uploaded_by, source_operation_id
    ) values (
      ${input.organizationId}, ${input.projectId}, ${input.filename},
      ${input.contentType}, ${input.byteSize}, ${input.checksumSha256},
      ${input.storageKey}, ${input.classification}::doc_classification,
      ${input.uploadedBy}, ${input.sourceOperationId}
    )
    returning id`;
  return rows[0];
}

export async function assertProjectInOrg(
  sql: postgres.Sql,
  organizationId: string,
  projectId: string
): Promise<boolean> {
  const rows = await sql<{ one: number }[]>`
    select 1 as one from projects
    where id = ${projectId} and organization_id = ${organizationId}
    limit 1`;
  return rows.length > 0;
}
