"use server";

import path from "node:path";
import { z } from "zod";
import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { requirePermission } from "@/lib/rbac";
import { runAction, optionalText, optionalNumber, type ActionState } from "@/lib/action";
import { getProject } from "@/modules/projects/repository";
import { getProjectDocuments } from "@/modules/model/repository";
import { DEVICE_RULES } from "@/modules/model/viewer-assets.generated";
import { runAndRecord, failure, outputKey, renderPreview } from "@/modules/model/run";

/**
 * Check a project's drawing, specifications and client BOQ against each other
 * and SPI's rules (engines/craft/review/check.py), and keep the result: a
 * workbook, a drawing with the recommended positions, and its picture.
 */

const schema = z.object({
  projectId: z.string().uuid(),
  drawingId: z.string().uuid().nullable(),
  specIds: z.array(z.string().uuid()).max(20),
  boqId: z.string().uuid().nullable(),
  deviceLayers: optionalText,
  storeyHeight: optionalNumber,
  useRules: z.boolean(),
});

const ext = (name: string) => path.extname(name).toLowerCase();
const blankToNull = (v: FormDataEntryValue | null) => (v ? String(v) : null) || null;

export async function runReviewAction(
  _prev: ActionState,
  formData: FormData
): Promise<ActionState> {
  let runId: string | null = null;
  const state = await runAction(async () => {
    const parsed = schema.parse({
      projectId: formData.get("projectId"),
      drawingId: blankToNull(formData.get("drawingId")),
      specIds: formData.getAll("specIds").map(String),
      boqId: blankToNull(formData.get("boqId")),
      deviceLayers: (formData.get("deviceLayers") as string) ?? "",
      storeyHeight: (formData.get("storeyHeight") as string) ?? "",
      useRules: formData.get("useRules") === "on",
    });
    if (!parsed.drawingId && parsed.specIds.length === 0 && !parsed.boqId) {
      return { ok: false, error: "Choose at least a drawing, a specification or a BOQ." };
    }
    // A spec alone is still checked against itself and the code; a BOQ alone
    // has nothing to be checked against.
    if (parsed.boqId && !parsed.drawingId && parsed.specIds.length === 0) {
      return { ok: false, error: "A BOQ needs a drawing or a specification to be checked against." };
    }
    const session = await requirePermission("craft.commit");
    const project = await getProject(session.organizationId, parsed.projectId);
    if (!project) return { ok: false, error: "Project not found." };

    const ids = [parsed.drawingId, ...parsed.specIds, parsed.boqId].filter((x): x is string => !!x);
    const docs = await getProjectDocuments(session.organizationId, parsed.projectId, ids);
    if (docs.length !== ids.length) return { ok: false, error: "A chosen file was not found." };
    const byId = new Map(docs.map((d) => [d.id, d]));
    const drawing = parsed.drawingId ? byId.get(parsed.drawingId)! : null;
    const boq = parsed.boqId ? byId.get(parsed.boqId)! : null;
    if (drawing && ext(drawing.filename) !== ".dxf") {
      return { ok: false, error: "The drawing must be a DXF: devices are counted from its blocks." };
    }
    if (boq && ext(boq.filename) !== ".xlsx") return { ok: false, error: "The BOQ must be an .xlsx workbook." };
    const specs = parsed.specIds.map((sid) => byId.get(sid)!);
    const bad = specs.find((s) => ![".pdf", ".docx", ".txt"].includes(ext(s.filename)));
    if (bad) return { ok: false, error: `${bad.filename}: a specification must be PDF, DOCX or TXT.` };

    const stamp = new Date().toISOString().slice(0, 16).replace(/[-:T]/g, "");
    const name = `Review_${(project.code || "project").replace(/[^\w-]+/g, "_")}_${stamp}`;
    const ref = (d: { id: string; storageKey: string; filename: string }) => ({
      document_id: d.id, storage_key: d.storageKey, filename: d.filename,
    });
    const run = await runAndRecord(session, parsed.projectId, "review.check", "commit", {
      document_id: parsed.projectId,
      project_name: project.name,
      drawing: drawing ? ref(drawing) : null,
      specs: specs.map(ref),
      boq: boq ? { ...ref(boq), sheet: null } : null,
      layers: parsed.deviceLayers ? parsed.deviceLayers.split(",").map((s) => s.trim()).filter(Boolean) : null,
      device_rules: parsed.useRules ? DEVICE_RULES : null,
      storey_height_m: parsed.storeyHeight,
      output_key: outputKey(session.organizationId, parsed.projectId, `${name}.xlsx`),
      output_name: `${name}.xlsx`,
      markup_key: outputKey(session.organizationId, parsed.projectId, `${name}_recommended.dxf`),
      markup_name: `${name}_recommended.dxf`,
    }, ids, 180_000);

    if (run.result.status === "error" || run.result.status === "invalid_input") {
      return { ok: false, error: failure("review.check", run.result) };
    }
    const dxf = run.documents.find((d) => d.name.endsWith(".dxf"));
    if (dxf) await renderPreview(session, parsed.projectId, dxf);
    revalidatePath(`/projects/${parsed.projectId}/review`);
    runId = run.operationId;
    return { ok: true, message: "Review ready." };
  });
  if (state.ok && runId) {
    redirect(`/projects/${formData.get("projectId")}/review/${runId}`);
  }
  return state;
}
