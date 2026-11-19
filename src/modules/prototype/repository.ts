import "server-only";
import type postgres from "postgres";
import { sql } from "@/lib/db";

/** The tools whose output is a building the viewer can show. */
export const BUILDING_TOOLS = ["bim.prototype", "bim.scene_3d"] as const;

export type BuildingRun = {
  id: string;
  tool: string;
  status: string;
  createdAt: string;
  durationMs: number | null;
  name: string | null;
  levels: number;
  rooms: number;
  files: string[];
  error: string | null;
};

/** A submitted drawing: a new document row, an original that is never edited. */
export async function recordDrawing(
  tx: postgres.TransactionSql,
  input: {
    organizationId: string;
    projectId: string;
    filename: string;
    contentType: string;
    byteSize: number;
    checksumSha256: string;
    storageKey: string;
    uploadedBy: string;
  }
): Promise<{ id: string }> {
  const rows = await tx<{ id: string }[]>`
    insert into documents (
      organization_id, project_id, filename, content_type, byte_size,
      checksum_sha256, storage_key, classification, uploaded_by
    ) values (
      ${input.organizationId}, ${input.projectId}, ${input.filename},
      ${input.contentType}, ${input.byteSize}, ${input.checksumSha256},
      ${input.storageKey}, 'drawing'::doc_classification, ${input.uploadedBy}
    )
    returning id`;
  return rows[0];
}

export async function listBuildingRuns(
  organizationId: string,
  projectId: string
): Promise<BuildingRun[]> {
  const rows = await sql<
    {
      id: string;
      tool: string;
      status: string;
      createdAt: Date;
      durationMs: number | null;
      name: string | null;
      levels: number | null;
      rooms: number | null;
      files: string[] | null;
      error: string | null;
    }[]
  >`
    select o.id, o.tool, o.status, o.created_at, o.duration_ms, o.error,
           o.output_json -> 'model' ->> 'project'                       as name,
           jsonb_array_length(coalesce(o.output_json -> 'storeys', '[]'::jsonb)) as levels,
           jsonb_array_length(coalesce(o.output_json -> 'spaces', '[]'::jsonb))  as rooms,
           array(select d.filename from documents d
                  where d.id = any(o.input_document_ids) order by d.created_at) as files
      from craft_operations o
     where o.organization_id = ${organizationId}
       and o.project_id = ${projectId}
       and o.tool in ${sql(BUILDING_TOOLS as unknown as string[])}
     order by o.created_at desc
     limit 50`;
  return rows.map((r) => ({
    id: r.id,
    tool: r.tool,
    status: r.status,
    createdAt: r.createdAt.toISOString(),
    durationMs: r.durationMs,
    name: r.name,
    levels: r.levels ?? 0,
    rooms: r.rooms ?? 0,
    files: r.files ?? [],
    error: r.error,
  }));
}

/**
 * One run, in the shape the engine returned it — the viewer loads exactly what
 * the engine produced, with its assumptions and findings, not a summary of it.
 */
export async function getBuildingRun(
  organizationId: string,
  projectId: string,
  operationId: string
): Promise<Record<string, unknown> | null> {
  const rows = await sql<
    {
      tool: string;
      status: string;
      outputJson: unknown;
      provenanceJson: unknown;
      missingJson: unknown;
      warningsJson: unknown;
      assumptionsJson: unknown;
      findingsJson: unknown;
      error: string | null;
      engineVersion: string;
      durationMs: number | null;
    }[]
  >`
    select tool, status, output_json, provenance_json, missing_json, warnings_json,
           assumptions_json, findings_json, error, engine_version, duration_ms
      from craft_operations
     where id = ${operationId}
       and organization_id = ${organizationId}
       and project_id = ${projectId}
       and tool in ${sql(BUILDING_TOOLS as unknown as string[])}
     limit 1`;
  const r = rows[0];
  if (!r) return null;
  return {
    operation_id: operationId,
    tool: r.tool,
    status: r.status,
    outputs: r.outputJson ?? {},
    provenance: r.provenanceJson ?? [],
    missing: r.missingJson ?? [],
    warnings: r.warningsJson ?? [],
    assumptions: r.assumptionsJson ?? [],
    findings: r.findingsJson ?? [],
    error: r.error,
    engine_version: r.engineVersion,
    duration_ms: r.durationMs,
    files: [],
  };
}
