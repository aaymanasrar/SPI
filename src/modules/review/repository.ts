import "server-only";
import { sql } from "@/lib/db";

/**
 * Read model for review.check runs. jsonb is read as ::text and parsed: the
 * pool's camelCase transform rewrites keys inside json values (lib/db.ts).
 */

export type ReviewSource = { doc: "drawing" | "spec" | "boq" | "rules"; name: string | null; ref: string; text: string };
export type ReviewIssue = {
  code: string;
  severity: "review" | "info" | "blocker";
  title: string;
  detail: string;
  action: string;
  sources: ReviewSource[];
};
export type ReviewBoqLine = {
  system: string;
  device_type: string;
  description: string;
  unit: string;
  drawn: number | null;
  recommended: number | null;
  spec: number | null;
  client_boq: number | null;
  status: string | null;
  where_drawn: string;
  where_recommended: string;
  why: string;
};
export type ReviewRoomLine = {
  room: string;
  room_type: string | null;
  area_m2: number | null;
  system: string;
  device_type: string;
  drawn: number;
  recommended: number | null;
  difference: number | null;
  status: string;
  note: string | null;
};
export type ReviewOutputs = {
  summary: {
    issues: number; review: number; info: number; rooms: number; drawn_devices: number;
    recommended_devices: number; spec_requirements: number; boq_rows: number;
  };
  boq: ReviewBoqLine[];
  rooms: ReviewRoomLine[];
  issues: ReviewIssue[];
  not_checked: { what: string; why: string }[];
};

export type ReviewRun = {
  id: string;
  status: string;
  createdAt: Date;
  error: string | null;
  inputs: string[];
  summary: ReviewOutputs["summary"] | null;
};

export async function listReviews(organizationId: string, projectId: string): Promise<ReviewRun[]> {
  const rows = await sql<{ id: string; status: string; createdAt: Date; error: string | null;
    inputs: string[] | null; summary: string | null }[]>`
    select o.id, o.status::text as status, o.created_at, o.error,
           array(select d.filename from documents d where d.id = any(o.input_document_ids)
                  order by d.created_at) as inputs,
           (jsonb_unwrap(o.output_json) -> 'summary')::text as summary
      from craft_operations o
     where o.organization_id = ${organizationId}
       and o.project_id = ${projectId}
       and o.tool = 'review.check'
     order by o.created_at desc
     limit 50`;
  return rows.map((r) => ({ ...r, inputs: r.inputs ?? [], summary: r.summary ? JSON.parse(r.summary) : null }));
}

export type ReviewDetail = ReviewRun & {
  outputs: ReviewOutputs | null;
  missing: { field: string; record: string; note: string | null }[];
  files: { id: string; filename: string; contentType: string | null; previewId: string | null }[];
};

export async function getReview(organizationId: string, projectId: string, runId: string): Promise<ReviewDetail | null> {
  const rows = await sql<{ id: string; status: string; createdAt: Date; error: string | null;
    inputs: string[] | null; outputs: string | null; missing: string | null }[]>`
    select o.id, o.status::text as status, o.created_at, o.error,
           array(select d.filename from documents d where d.id = any(o.input_document_ids)
                  order by d.created_at) as inputs,
           jsonb_unwrap(o.output_json)::text as outputs,
           jsonb_unwrap(o.missing_json)::text as missing
      from craft_operations o
     where o.id = ${runId}
       and o.organization_id = ${organizationId}
       and o.project_id = ${projectId}
       and o.tool = 'review.check'`;
  const r = rows[0];
  if (!r) return null;
  const files = await sql<{ id: string; filename: string; contentType: string | null; previewId: string | null }[]>`
    select d.id, d.filename, d.content_type,
           (select p.id from documents p
              join craft_operations po on po.id = p.source_operation_id
             where po.tool = 'cad.render_svg' and d.id = any(po.input_document_ids)
               and po.organization_id = ${organizationId}
             order by p.created_at desc limit 1) as preview_id
      from documents d
     where d.source_operation_id = ${runId}
       and d.organization_id = ${organizationId}
     order by d.created_at`;
  const outputs = r.outputs ? (JSON.parse(r.outputs) as ReviewOutputs) : null;
  return {
    id: r.id, status: r.status, createdAt: r.createdAt, error: r.error, inputs: r.inputs ?? [],
    summary: outputs?.summary ?? null, outputs,
    missing: r.missing ? JSON.parse(r.missing) : [],
    files,
  };
}
