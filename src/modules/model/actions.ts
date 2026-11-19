"use server";

import path from "node:path";
import { z } from "zod";
import { revalidatePath } from "next/cache";
import { sql, transaction } from "@/lib/db";
import { requirePermission } from "@/lib/rbac";
import { recordAudit } from "@/lib/audit";
import { runAction, optionalText, optionalNumber, type ActionState } from "@/lib/action";
import { getProject } from "@/modules/projects/repository";
import * as craftRepo from "@/modules/craft/repository";
import { recordDrawing } from "@/modules/prototype/repository";
import { saveUpload, MAX_FILE_BYTES, DRAWING_TYPES } from "@/modules/prototype/storage";
import { runAndRecord, failure, outputKey, renderPreview } from "./run";
import { getProjectDocuments, type StoredDocument } from "./repository";
import { DEVICE_RULES } from "./viewer-assets.generated";

/**
 * Upload a drawing, and make a 3D model or a shop drawing from it.
 *
 * Every engine call follows the craft actions' order (src/modules/craft/actions.ts):
 * the HTTP call runs outside any transaction, then the operation row, its output
 * documents and the audit entry commit together. Each step of a multi-step job is
 * its own operation, so every file can be traced to the run that made it.
 */

const PLAN_EXT = new Set([".dxf", ".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"]);
const ext = (name: string) => path.extname(name).toLowerCase();

// ---------------------------------------------------------------- upload

export async function uploadDrawingAction(
  _prev: ActionState,
  formData: FormData
): Promise<ActionState> {
  return runAction(async () => {
    const session = await requirePermission("document.upload");
    const projectId = z.string().uuid().parse(formData.get("projectId"));
    if (!(await craftRepo.assertProjectInOrg(sql, session.organizationId, projectId))) {
      return { ok: false, error: "Project not found." };
    }
    const files = formData.getAll("files").filter((f): f is File => f instanceof File && f.size > 0);
    if (files.length === 0) return { ok: false, error: "Choose at least one file." };
    const tooBig = files.find((f) => f.size > MAX_FILE_BYTES);
    if (tooBig) return { ok: false, error: `${tooBig.name} is larger than 150 MB.` };
    const unknown = files.find((f) => !DRAWING_TYPES[ext(f.name)]);
    if (unknown) {
      return { ok: false, error: `${unknown.name}: accepted are ${Object.keys(DRAWING_TYPES).join(", ")}.` };
    }
    const kind = z.enum(["auto", "drawing", "specification", "boq"]).parse(formData.get("kind") ?? "auto");
    // What a file is: said by the person, else read from its type. A PDF is a
    // drawing unless they say it is a specification.
    const classify = (name: string): "drawing" | "specification" | "boq" =>
      kind !== "auto" ? kind
        : ext(name) === ".xlsx" ? "boq"
        : ext(name) === ".docx" || ext(name) === ".txt" ? "specification"
        : "drawing";

    const saved: { id: string; storageKey: string; name: string }[] = [];
    for (const file of files) {
      const stored = await saveUpload(session.organizationId, projectId, file);
      const doc = await transaction(async (tx) => {
        const d = await recordDrawing(tx, {
          organizationId: session.organizationId,
          projectId,
          filename: stored.filename,
          contentType: stored.contentType,
          byteSize: stored.byteSize,
          checksumSha256: stored.sha256,
          storageKey: stored.storageKey,
          uploadedBy: session.userId,
          classification: classify(stored.filename),
        });
        await recordAudit(session, {
          action: "document.upload",
          subjectType: "document",
          subjectId: d.id,
          after: { filename: stored.filename, byteSize: stored.byteSize, sha256: stored.sha256,
                   classification: classify(stored.filename) },
        }, tx);
        return d;
      });
      saved.push({ id: doc.id, storageKey: stored.storageKey, name: stored.filename });
    }

    // A DXF gets a picture straight away, if this person may write files.
    const notes: string[] = [];
    if (session.permissions.has("craft.commit")) {
      for (const d of saved.filter((s) => ext(s.name) === ".dxf")) {
        const r = await renderPreview(session, projectId, d);
        if (r.result.status !== "ok") notes.push(`No preview for ${d.name}: ${failure("cad.render_svg", r.result)}`);
      }
    }
    revalidatePath(`/projects/${projectId}/model`);
    return {
      ok: true,
      message: `Uploaded ${saved.map((s) => s.name).join(", ")}.${notes.length ? " " + notes.join(" ") : ""}`,
    };
  });
}

// ---------------------------------------------------------------- 3D model

const modelSchema = z.object({
  projectId: z.string().uuid(),
  documentIds: z.array(z.string().uuid()).min(1, "Choose at least one drawing").max(40),
  storeyHeight: optionalNumber,
});

export async function makeModelAction(
  _prev: ActionState,
  formData: FormData
): Promise<ActionState> {
  return runAction(async () => {
    const parsed = modelSchema.parse({
      projectId: formData.get("projectId"),
      documentIds: formData.getAll("documentIds"),
      storeyHeight: (formData.get("storeyHeight") as string) ?? "",
    });
    const session = await requirePermission("craft.preview");
    const docs = await getProjectDocuments(session.organizationId, parsed.projectId, parsed.documentIds);
    if (docs.length !== parsed.documentIds.length) return { ok: false, error: "Drawing not found." };

    const ifc = docs.filter((d) => ext(d.filename) === ".ifc");
    let tool: string;
    let input: Record<string, unknown>;
    if (ifc.length > 0) {
      if (docs.length !== 1) {
        return { ok: false, error: "An IFC model is a whole building: choose it on its own." };
      }
      tool = "bim.scene_3d";
      input = { document_id: ifc[0].id, storage_key: ifc[0].storageKey };
    } else {
      const bad = docs.find((d) => !PLAN_EXT.has(ext(d.filename)));
      if (bad) return { ok: false, error: `${bad.filename} is not a floor plan (DXF, PDF or image).` };
      const project = await getProject(session.organizationId, parsed.projectId);
      tool = "bim.prototype";
      input = {
        document_id: docs[0].id,
        name: project?.name ?? null,
        levels: docs.map((d: StoredDocument) => ({ document_id: d.id, storage_key: d.storageKey })),
        storey_height_m: parsed.storeyHeight,
        device_rules: DEVICE_RULES,
      };
    }

    const r = await runAndRecord(session, parsed.projectId, tool, "preview", input,
      docs.map((d) => d.id), 180_000);
    revalidatePath(`/projects/${parsed.projectId}/model`);
    revalidatePath(`/projects/${parsed.projectId}`);
    if (r.result.status === "error" || r.result.status === "invalid_input") {
      return { ok: false, error: failure(tool, r.result) };
    }
    const gaps = r.result.missing.length
      ? ` ${r.result.missing.length} item(s) could not be read and are listed in the viewer.`
      : "";
    return { ok: true, message: `3D model ready.${gaps} Open it from the list below.` };
  });
}

// ---------------------------------------------------------------- shop drawing

const PAPERS = ["A0", "A1", "A2", "A3", "A4", "ANSI_B", "ANSI_C", "ANSI_D", "ANSI_E"] as const;

const sheetSchema = z.object({
  projectId: z.string().uuid(),
  documentId: z.string().uuid(),
  paper: z.enum(PAPERS),
  orientation: z.enum(["landscape", "portrait"]),
  scale: z.coerce.number().int().min(1).max(10000),
  roomLayer: optionalText,
  roomNameLayer: optionalText,
  deviceLayers: optionalText,
  northAngle: optionalNumber,
  title: optionalText,
  drawingNumber: optionalText,
  revision: optionalText,
  createdBy: optionalText,
  approvedBy: optionalText,
});

const list = (v: string | null) =>
  v ? v.split(",").map((s) => s.trim()).filter(Boolean) : null;

export async function makeShopDrawingAction(
  _prev: ActionState,
  formData: FormData
): Promise<ActionState> {
  return runAction(async () => {
    const f = (k: string) => (formData.get(k) as string | null) ?? "";
    const parsed = sheetSchema.parse({
      projectId: formData.get("projectId"),
      documentId: formData.get("documentId"),
      paper: formData.get("paper"),
      orientation: formData.get("orientation"),
      scale: formData.get("scale"),
      roomLayer: f("roomLayer"),
      roomNameLayer: f("roomNameLayer"),
      deviceLayers: f("deviceLayers"),
      northAngle: f("northAngle"),
      title: f("title"),
      drawingNumber: f("drawingNumber"),
      revision: f("revision"),
      createdBy: f("createdBy"),
      approvedBy: f("approvedBy"),
    });
    const session = await requirePermission("craft.commit");
    const project = await getProject(session.organizationId, parsed.projectId);
    if (!project) return { ok: false, error: "Project not found." };
    const [source] = await getProjectDocuments(session.organizationId, parsed.projectId, [parsed.documentId]);
    if (!source) return { ok: false, error: "Drawing not found." };
    if (ext(source.filename) !== ".dxf") {
      return { ok: false, error: "A shop drawing is made from a DXF. Export the plan as DXF first." };
    }
    const stem = path.basename(source.filename, ".dxf").replace(/[^\w.-]+/g, "_");

    // 1. Takeoff: devices tagged and scheduled on a copy of the drawing.
    const takeoffName = `${stem}_takeoff.dxf`;
    const takeoff = await runAndRecord(session, parsed.projectId, "cad.takeoff_sheet", "commit", {
      document_id: source.id,
      storage_key: source.storageKey,
      layers: list(parsed.deviceLayers),
      room_boundary_layers: list(parsed.roomLayer),
      room_label_layers: list(parsed.roomNameLayer),
      output_key: outputKey(session.organizationId, parsed.projectId, takeoffName),
      output_name: takeoffName,
    }, [source.id]);
    const takeoffDoc = takeoff.documents[0];
    if (!takeoffDoc) {
      revalidatePath(`/projects/${parsed.projectId}/model`);
      return { ok: false, error: failure("cad.takeoff_sheet", takeoff.result) };
    }

    // 2. Sheet: frame and ISO 7200 title block around the takeoff.
    const sheetName = `${stem}_${parsed.paper}_sheet.dxf`;
    const sheet = await runAndRecord(session, parsed.projectId, "cad.sheet_setup", "commit", {
      document_id: takeoffDoc.id,
      storage_key: takeoffDoc.storageKey,
      paper: parsed.paper,
      orientation: parsed.orientation,
      scale: parsed.scale,
      north_angle_deg: parsed.northAngle,
      title_block: {
        legal_owner: session.organizationName,
        title: parsed.title ?? `${project.name} — ELV device layout`,
        drawing_number: parsed.drawingNumber,
        revision: parsed.revision,
        date_of_issue: new Date().toISOString().slice(0, 10),
        document_type: "Shop drawing",
        created_by: parsed.createdBy ?? session.name,
        approved_by: parsed.approvedBy,
        project: project.name,
        client: project.clientName,
        sheet: "1/1",
      },
      output_key: outputKey(session.organizationId, parsed.projectId, sheetName),
      output_name: sheetName,
    }, [takeoffDoc.id]);
    const sheetDoc = sheet.documents[0];

    // 3. Pictures of what was made, so the page can show them.
    await renderPreview(session, parsed.projectId, takeoffDoc);
    if (sheetDoc) await renderPreview(session, parsed.projectId, sheetDoc);

    revalidatePath(`/projects/${parsed.projectId}/model`);
    revalidatePath(`/projects/${parsed.projectId}`);
    if (!sheetDoc) {
      return {
        ok: false,
        error: `The takeoff was made, but not the sheet. ${failure("cad.sheet_setup", sheet.result)}`,
      };
    }
    const open: string[] = [];
    if (takeoff.result.missing.length) open.push(`${takeoff.result.missing.length} block type(s) not counted`);
    if (sheet.result.missing.length) open.push(`${sheet.result.missing.length} title block field(s) marked MISSING`);
    return {
      ok: true,
      message: `Shop drawing ready: ${sheetName}.${open.length ? ` Still open: ${open.join("; ")}.` : ""}`,
    };
  });
}

// ---------------------------------------------------------------- preview

export async function makePreviewAction(
  _prev: ActionState,
  formData: FormData
): Promise<ActionState> {
  return runAction(async () => {
    const projectId = z.string().uuid().parse(formData.get("projectId"));
    const documentId = z.string().uuid().parse(formData.get("documentId"));
    const session = await requirePermission("craft.commit");
    const [doc] = await getProjectDocuments(session.organizationId, projectId, [documentId]);
    if (!doc) return { ok: false, error: "Drawing not found." };
    if (ext(doc.filename) !== ".dxf") return { ok: false, error: "Pictures are made from DXF drawings." };
    const r = await renderPreview(session, projectId, {
      id: doc.id, storageKey: doc.storageKey, name: doc.filename,
    });
    revalidatePath(`/projects/${projectId}/model`);
    return r.result.status === "ok"
      ? { ok: true, message: "Preview made." }
      : { ok: false, error: failure("cad.render_svg", r.result) };
  });
}
