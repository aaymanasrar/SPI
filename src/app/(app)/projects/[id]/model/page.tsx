import Link from "next/link";
import { notFound } from "next/navigation";
import { requireSession } from "@/lib/auth";
import { getProject } from "@/modules/projects/repository";
import { listProjectFiles, type ProjectFile } from "@/modules/model/repository";
import { listBuildingRuns } from "@/modules/prototype/repository";
import {
  uploadDrawingAction,
  makeModelAction,
  makeShopDrawingAction,
  makePreviewAction,
} from "@/modules/model/actions";
import { ActionForm } from "@/components/action-form";
import { PreviewButton } from "./preview-button";
import { Card, Field, Select, Pill, Empty, NoPermission } from "@/components/ui";

const KIND_LABEL: Record<ProjectFile["kind"], string> = {
  uploaded: "Uploaded",
  takeoff: "Takeoff",
  sheet: "Shop drawing",
  preview: "Preview",
  review: "Review",
  other: "Engine output",
};

const PLAN = /\.(dxf|pdf|png|jpe?g|tiff?)$/i;

function size(bytes: number | null): string {
  if (bytes === null) return "";
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default async function ModelPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const session = await requireSession();
  const project = await getProject(session.organizationId, id);
  if (!project) notFound();

  const mayPreview = session.permissions.has("craft.preview");
  const mayCommit = session.permissions.has("craft.commit");
  const mayUpload = session.permissions.has("document.upload");
  const [files, runs] = await Promise.all([
    listProjectFiles(session.organizationId, id),
    mayPreview ? listBuildingRuns(session.organizationId, id) : Promise.resolve([]),
  ]);

  // Pictures are shown on the file they depict, not listed on their own.
  const drawings = files.filter((f) => f.kind !== "preview" && f.classification === "drawing"
    && /\.(dxf|ifc|pdf|png|jpe?g|tiff?)$/i.test(f.filename));
  const uploads = files.filter((f) => f.kind === "uploaded" && f.classification === "drawing").reverse(); // oldest first
  const dxfs = drawings.filter((f) => /\.dxf$/i.test(f.filename) && f.kind === "uploaded");
  const today = new Date().toISOString().slice(0, 10);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Link href={`/projects/${id}`} className="text-xs text-muted hover:text-foreground">
            ← {project.name}
          </Link>
          <h1 className="mt-1 text-2xl font-light tracking-tight text-foreground">
            3D model &amp; drawings
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-muted">
            Upload a floor plan or a Revit model, then make a 3D model or a shop drawing from
            it. Everything made here is a proposal for an engineer to check: what the engine
            could not read is listed with it, never filled in.
          </p>
        </div>
      </div>

      {/* 3D models */}
      <Card
        title={`3D models (${runs.length})`}
        description="Walk the building, check device coverage and run a fire drill."
      >
        {!mayPreview ? (
          <NoPermission what="viewing engine results" />
        ) : runs.length === 0 ? (
          <Empty>No 3D model yet. Upload a drawing below and choose “Make 3D model”.</Empty>
        ) : (
          <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {runs.map((r) => (
              <li key={r.id} className="rounded-xl border border-line bg-surface-2 p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium text-foreground">
                      {r.name || r.files[0] || "Building"}
                    </div>
                    <div className="mt-0.5 truncate text-xs text-muted">
                      {r.tool === "bim.scene_3d" ? "From IFC model" : "From floor plans"} ·{" "}
                      {r.files.join(", ") || "—"}
                    </div>
                  </div>
                  <Pill value={r.status} />
                </div>
                <div className="mt-3 flex items-center justify-between gap-2">
                  <span className="text-xs tabular-nums text-faint">
                    {r.levels} level{r.levels === 1 ? "" : "s"} · {r.rooms} room{r.rooms === 1 ? "" : "s"} ·{" "}
                    {new Date(r.createdAt).toLocaleDateString()}
                  </span>
                  {r.status === "error" || r.status === "invalid_input" ? (
                    <span className="max-w-[60%] truncate text-xs text-danger" title={r.error ?? ""}>
                      {r.error ?? "Failed"}
                    </span>
                  ) : (
                    <Link
                      href={`/projects/${id}/model/${r.id}`}
                      className="rounded-full bg-accent px-3.5 py-1.5 text-xs font-medium text-accent-ink hover:brightness-110"
                    >
                      Open 3D →
                    </Link>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* Drawings */}
      <Card
        title={`Drawings (${drawings.length})`}
        description="Uploads, takeoffs and shop drawings. Click a picture to open it full size."
      >
        {drawings.length === 0 ? (
          <Empty>No drawings yet.</Empty>
        ) : (
          <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {drawings.map((d) => (
              <li key={d.id} className="overflow-hidden rounded-xl border border-line bg-surface-2">
                <Link href={`/projects/${id}/drawings/${d.id}`} className="block">
                  <div className="flex aspect-[4/3] items-center justify-center bg-white">
                    {d.previewId ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={`/projects/${id}/files/${d.previewId}`}
                        alt={`Preview of ${d.filename}`}
                        className="h-full w-full object-contain"
                        loading="lazy"
                      />
                    ) : (
                      <span className="px-6 text-center text-xs text-slate-500">
                        {/\.ifc$/i.test(d.filename)
                          ? "IFC model — open it as a 3D model"
                          : "No picture of this file yet"}
                      </span>
                    )}
                  </div>
                </Link>
                <div className="space-y-2 p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="truncate text-sm text-foreground" title={d.filename}>
                        {d.filename}
                      </div>
                      <div className="text-xs text-faint">
                        {KIND_LABEL[d.kind]} · {size(d.byteSize)} · {d.createdAt.toLocaleDateString()}
                      </div>
                    </div>
                    {d.status && <Pill value={d.missingCount > 0 && d.status === "ok" ? "missing_data" : d.status} />}
                  </div>
                  {d.missingCount > 0 && (
                    <p className="text-xs text-warn">
                      {d.missingCount} item{d.missingCount === 1 ? "" : "s"} still open — see details.
                    </p>
                  )}
                  <div className="flex flex-wrap gap-2">
                    {!d.previewId && mayCommit && /\.dxf$/i.test(d.filename) && (
                      <PreviewButton action={makePreviewAction} projectId={id} documentId={d.id} />
                    )}
                    <Link
                      href={`/projects/${id}/drawings/${d.id}`}
                      className="rounded-full border border-line-strong px-3 py-1 text-xs text-foreground hover:bg-white/5"
                    >
                      Preview
                    </Link>
                    <a
                      href={`/projects/${id}/files/${d.id}?download=1`}
                      className="rounded-full border border-line-strong px-3 py-1 text-xs text-foreground hover:bg-white/5"
                    >
                      Download
                    </a>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <div className="grid gap-4 xl:grid-cols-3">
        <Card title="Upload" description="Floor plans (DXF, PDF, image), an IFC model, specifications (PDF, DOCX, TXT) or a client BOQ (XLSX). Up to 150 MB each.">
          {!mayUpload ? (
            <NoPermission what="uploading documents" />
          ) : (
            <ActionForm action={uploadDrawingAction} submitLabel="Upload" resetOnSuccess>
              <input type="hidden" name="projectId" value={id} />
              <Select
                label="These files are"
                name="kind"
                options={[
                  { value: "auto", label: "Decide by file type (PDF = drawing)" },
                  { value: "drawing", label: "Drawings" },
                  { value: "specification", label: "Specifications" },
                  { value: "boq", label: "Client BOQ" },
                ]}
              />
              <Field label="Files">
                <input
                  type="file"
                  name="files"
                  multiple
                  required
                  accept=".dxf,.ifc,.pdf,.png,.jpg,.jpeg,.tif,.tiff,.docx,.xlsx,.txt"
                  className="block w-full text-sm text-muted file:mr-3 file:rounded-full file:border-0 file:bg-white/10 file:px-3 file:py-1.5 file:text-sm file:text-foreground"
                />
              </Field>
            </ActionForm>
          )}
        </Card>

        <Card title="Make 3D model" description="One IFC model, or one floor plan per level.">
          {!mayPreview ? (
            <NoPermission what="running engines" />
          ) : uploads.length === 0 ? (
            <Empty>Upload a drawing first.</Empty>
          ) : (
            <ActionForm action={makeModelAction} submitLabel="Make 3D model">
              <input type="hidden" name="projectId" value={id} />
              <fieldset className="space-y-1.5">
                <legend className="mb-1 text-xs font-medium text-muted">
                  Drawings — tick plans lowest level first, in this order
                </legend>
                {uploads
                  .filter((u) => PLAN.test(u.filename) || /\.ifc$/i.test(u.filename))
                  .map((u) => (
                    <label key={u.id} className="flex items-center gap-2 text-sm text-foreground">
                      <input type="checkbox" name="documentIds" value={u.id} className="accent-[var(--accent)]" />
                      <span className="truncate">{u.filename}</span>
                    </label>
                  ))}
              </fieldset>
              <Field
                label="Floor-to-floor height (m)"
                name="storeyHeight"
                type="number"
                step="0.01"
                hint="Floor plans only. Leave empty to have the engine assume one and say so."
              />
            </ActionForm>
          )}
        </Card>

        <Card title="Make shop drawing" description="Devices tagged and scheduled, on an ISO sheet with a title block.">
          {!mayCommit ? (
            <NoPermission what="writing engine outputs" />
          ) : dxfs.length === 0 ? (
            <Empty>Upload a DXF floor plan first.</Empty>
          ) : (
            <ActionForm action={makeShopDrawingAction} submitLabel="Make shop drawing">
              <input type="hidden" name="projectId" value={id} />
              <Select
                label="Floor plan (DXF)"
                name="documentId"
                options={dxfs.map((d) => ({ value: d.id, label: d.filename }))}
              />
              <div className="grid grid-cols-3 gap-2">
                <Select
                  label="Paper"
                  name="paper"
                  defaultValue="A1"
                  options={["A0", "A1", "A2", "A3", "A4", "ANSI_B", "ANSI_C", "ANSI_D", "ANSI_E"].map((p) => ({ value: p, label: p.replace("_", " ") }))}
                />
                <Select
                  label="Orientation"
                  name="orientation"
                  options={[{ value: "landscape", label: "Landscape" }, { value: "portrait", label: "Portrait" }]}
                />
                <Field label="Scale 1:" name="scale" type="number" defaultValue={50} required />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <Field label="Drawing number" name="drawingNumber" defaultValue={project.code ? `${project.code}-SD-01` : ""} />
                <Field label="Revision" name="revision" defaultValue="A" />
              </div>
              <Field label="Title" name="title" defaultValue={`${project.name} — ELV device layout`} />
              <div className="grid grid-cols-2 gap-2">
                <Field label="Drawn by" name="createdBy" defaultValue={session.name} />
                <Field label="Approved by" name="approvedBy" hint="Empty prints a red MISSING." />
              </div>
              <details className="text-xs text-muted">
                <summary className="cursor-pointer">More options</summary>
                <div className="mt-2 space-y-2">
                  <Field label="Room outline layer" name="roomLayer" hint="Closed outlines on this layer get their area written in m²." />
                  <Field label="Room name layer" name="roomNameLayer" hint="Where room names are written. Empty takes any text inside the room, device tags included." />
                  <Field label="Device layers" name="deviceLayers" hint="Comma-separated, e.g. E-FIRE, E-SEC. Empty counts every layer." />
                  <Field label="North bearing (°)" name="northAngle" type="number" step="0.1" hint="Empty means no north arrow." />
                </div>
              </details>
              <p className="text-[11px] text-faint">Issued date will be {today}.</p>
            </ActionForm>
          )}
        </Card>
      </div>
    </div>
  );
}
