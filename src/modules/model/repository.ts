import "server-only";
import { sql } from "@/lib/db";

/**
 * Read model for a project's drawings and the files the engines made from them.
 *
 * Every query takes organizationId and projectId and filters on both: a
 * document id arrives from a URL and is attacker-controlled.
 */

export type DrawingKind = "uploaded" | "takeoff" | "sheet" | "preview" | "review" | "other";

export type ProjectFile = {
  id: string;
  filename: string;
  contentType: string | null;
  byteSize: number | null;
  createdAt: Date;
  /** What the file is: drawing, specification, boq, … */
  classification: string;
  kind: DrawingKind;
  /** The run that made this file; null for an upload. */
  operationId: string | null;
  tool: string | null;
  status: string | null;
  missingCount: number;
  findings: { code: string; severity: string; detail: string }[];
  /** The upload or earlier output this file was made from. */
  sourceDocumentId: string | null;
  /** Latest SVG picture of this file, when one was rendered. */
  previewId: string | null;
};

const KIND_BY_TOOL: Record<string, DrawingKind> = {
  "cad.takeoff_sheet": "takeoff",
  "cad.sheet_setup": "sheet",
  "cad.render_svg": "preview",
  "review.check": "review",
};

export async function listProjectFiles(
  organizationId: string,
  projectId: string
): Promise<ProjectFile[]> {
  const rows = await sql<
    {
      id: string;
      filename: string;
      contentType: string | null;
      byteSize: string | number | null;
      createdAt: Date;
      classification: string;
      operationId: string | null;
      tool: string | null;
      status: string | null;
      missingCount: number | null;
      findings: string | null;
      sourceDocumentId: string | null;
      previewId: string | null;
    }[]
  >`
    select d.id, d.filename, d.content_type, d.byte_size, d.created_at,
           d.classification::text as classification,
           o.id as operation_id, o.tool, o.status::text as status,
           jsonb_array_length(coalesce(jsonb_unwrap(o.missing_json), '[]'::jsonb)) as missing_count,
           jsonb_unwrap(o.findings_json)::text as findings,
           o.input_document_ids[1] as source_document_id,
           (select p.id
              from documents p
              join craft_operations po on po.id = p.source_operation_id
             where po.tool = 'cad.render_svg'
               and po.organization_id = ${organizationId}
               and d.id = any(po.input_document_ids)
             order by p.created_at desc
             limit 1) as preview_id
      from documents d
      left join craft_operations o on o.id = d.source_operation_id
     where d.organization_id = ${organizationId}
       and d.project_id = ${projectId}
       and d.superseded_by_id is null
     order by d.created_at desc
     limit 200`;
  const files: ProjectFile[] = rows.map((r) => ({
    id: r.id,
    filename: r.filename,
    contentType: r.contentType,
    byteSize: r.byteSize === null ? null : Number(r.byteSize),
    createdAt: r.createdAt,
    classification: r.classification,
    kind: r.tool ? (KIND_BY_TOOL[r.tool] ?? "other") : "uploaded",
    operationId: r.operationId,
    tool: r.tool,
    status: r.status,
    missingCount: r.missingCount ?? 0,
    // ::text, then parsed: the pool camel-cases keys inside json values.
    findings: r.findings ? JSON.parse(r.findings) : [],
    sourceDocumentId: r.sourceDocumentId,
    previewId: r.previewId,
  }));
  // A sheet carries the open items of the takeoff it frames.
  const byId = new Map(files.map((f) => [f.id, f]));
  for (const f of files) {
    const src = f.kind === "sheet" && f.sourceDocumentId ? byId.get(f.sourceDocumentId) : undefined;
    if (src?.kind === "takeoff") f.missingCount += src.missingCount;
  }
  return files;
}

export type StoredDocument = {
  id: string;
  filename: string;
  contentType: string | null;
  storageKey: string;
};

export async function getProjectDocument(
  organizationId: string,
  projectId: string,
  documentId: string
): Promise<StoredDocument | null> {
  const rows = await sql<StoredDocument[]>`
    select id, filename, content_type, storage_key
      from documents
     where id = ${documentId}
       and organization_id = ${organizationId}
       and project_id = ${projectId}
     limit 1`;
  return rows[0] ?? null;
}

export async function getProjectDocuments(
  organizationId: string,
  projectId: string,
  documentIds: string[]
): Promise<StoredDocument[]> {
  if (documentIds.length === 0) return [];
  const rows = await sql<StoredDocument[]>`
    select id, filename, content_type, storage_key
      from documents
     where id in ${sql(documentIds)}
       and organization_id = ${organizationId}
       and project_id = ${projectId}`;
  // Keep the caller's order: for floor plans it is lowest level first.
  const byId = new Map(rows.map((r) => [r.id, r]));
  return documentIds.map((id) => byId.get(id)).filter((r): r is StoredDocument => !!r);
}

export type DrawingDetail = ProjectFile & {
  missing: { field: string; record: string; note: string | null }[];
  assumptions: { key: string; value: unknown; basis: string }[];
  outputs: Record<string, unknown> | null;
  schedule: { item?: string; system: string; device_type: string; quantity: number }[];
  sourceFilename: string | null;
};

export async function getDrawingDetail(
  organizationId: string,
  projectId: string,
  documentId: string
): Promise<DrawingDetail | null> {
  const files = await listProjectFiles(organizationId, projectId);
  const file = files.find((f) => f.id === documentId);
  if (!file) return null;
  let missing: DrawingDetail["missing"] = [];
  let assumptions: DrawingDetail["assumptions"] = [];
  let outputs: DrawingDetail["outputs"] = null;
  if (file.operationId) {
    const rows = await sql<{ missingJson: string | null; assumptionsJson: string | null; outputJson: string | null }[]>`
      select jsonb_unwrap(missing_json)::text as missing_json,
             jsonb_unwrap(assumptions_json)::text as assumptions_json,
             jsonb_unwrap(output_json)::text as output_json
        from craft_operations
       where id = ${file.operationId} and organization_id = ${organizationId}`;
    const r = rows[0];
    missing = r?.missingJson ? JSON.parse(r.missingJson) : [];
    assumptions = r?.assumptionsJson ? JSON.parse(r.assumptionsJson) : [];
    outputs = r?.outputJson ? JSON.parse(r.outputJson) : null;
  }
  const source = file.sourceDocumentId ? files.find((f) => f.id === file.sourceDocumentId) : undefined;
  // A sheet carries no schedule of its own: it frames the takeoff it was made
  // from, so show that takeoff's schedule.
  // What is open on the takeoff is open on the sheet too: a framed sheet must
  // not look complete when the count inside it is not.
  let schedule: unknown = outputs?.schedule ?? null;
  if (source?.operationId && source.kind === "takeoff") {
    const rows = await sql<{ out: string | null; missing: string | null }[]>`
      select jsonb_unwrap(output_json -> 'schedule')::text as out,
             jsonb_unwrap(missing_json)::text as missing
        from craft_operations
       where id = ${source.operationId} and organization_id = ${organizationId}`;
    if (!schedule) schedule = rows[0]?.out ? JSON.parse(rows[0].out) : null;
    const inherited: DrawingDetail["missing"] = rows[0]?.missing ? JSON.parse(rows[0].missing) : [];
    missing = [
      ...missing,
      ...inherited.map((m) => ({ ...m, note: `On the takeoff: ${m.note ?? m.field}` })),
    ];
  }
  return {
    ...file, missing, missingCount: missing.length, assumptions, outputs,
    schedule: Array.isArray(schedule) ? schedule : [],
    sourceFilename: source?.filename ?? null,
  };
}
