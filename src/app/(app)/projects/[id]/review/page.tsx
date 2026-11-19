import Link from "next/link";
import { notFound } from "next/navigation";
import { requireSession } from "@/lib/auth";
import { getProject } from "@/modules/projects/repository";
import { listProjectFiles } from "@/modules/model/repository";
import { listReviews } from "@/modules/review/repository";
import { runReviewAction } from "@/modules/review/actions";
import { ActionForm } from "@/components/action-form";
import { Card, Field, Select, Pill, Empty, NoPermission } from "@/components/ui";

export default async function ReviewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const session = await requireSession();
  const project = await getProject(session.organizationId, id);
  if (!project) notFound();
  const mayRun = session.permissions.has("craft.commit");
  const [files, runs] = await Promise.all([
    listProjectFiles(session.organizationId, id),
    session.permissions.has("craft.preview") ? listReviews(session.organizationId, id) : Promise.resolve([]),
  ]);
  const uploads = files.filter((f) => f.kind === "uploaded");
  const dxfs = uploads.filter((f) => f.classification === "drawing" && /\.dxf$/i.test(f.filename));
  const specs = uploads.filter((f) => f.classification === "specification");
  const boqs = uploads.filter((f) => f.classification === "boq" && /\.xlsx$/i.test(f.filename));

  return (
    <div className="space-y-6">
      <div>
        <Link href={`/projects/${id}`} className="text-xs text-muted hover:text-foreground">
          ← {project.name}
        </Link>
        <h1 className="mt-1 text-2xl font-light tracking-tight text-foreground">Drawing, spec &amp; BOQ check</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted">
          Counts what is drawn, sets it against what SPI&apos;s rules recommend room by room, and checks the
          drawing, the specification and the client BOQ against each other. Every flag cites both sides —
          the room, the clause, the BOQ row, the rule. Which side is right is the engineer&apos;s call.
        </p>
      </div>

      <div className="grid gap-4 xl:grid-cols-5">
        <div className="xl:col-span-2">
          <Card title="New check" description="Pick any combination. Upload files on the 3D model & drawings page.">
            {!mayRun ? (
              <NoPermission what="running engine checks" />
            ) : dxfs.length + specs.length + boqs.length === 0 ? (
              <Empty>
                Nothing to check yet.{" "}
                <Link href={`/projects/${id}/model`} className="text-accent hover:underline">Upload a drawing, spec or BOQ</Link>.
              </Empty>
            ) : (
              <ActionForm action={runReviewAction} submitLabel="Run check">
                <input type="hidden" name="projectId" value={id} />
                <Select
                  label="Floor plan (DXF)"
                  name="drawingId"
                  includeBlank="— none —"
                  defaultValue={dxfs[0]?.id ?? null}
                  options={dxfs.map((d) => ({ value: d.id, label: d.filename }))}
                />
                <fieldset className="space-y-1.5">
                  <legend className="mb-1 text-xs font-medium text-muted">Specifications</legend>
                  {specs.length === 0 ? (
                    <p className="text-xs text-faint">None uploaded. Upload one as “Specifications”.</p>
                  ) : (
                    specs.map((s) => (
                      <label key={s.id} className="flex items-center gap-2 text-sm text-foreground">
                        <input type="checkbox" name="specIds" value={s.id} defaultChecked className="accent-[var(--accent)]" />
                        <span className="truncate">{s.filename}</span>
                      </label>
                    ))
                  )}
                </fieldset>
                <Select
                  label="Client BOQ (XLSX)"
                  name="boqId"
                  includeBlank="— none —"
                  defaultValue={boqs[0]?.id ?? null}
                  options={boqs.map((b) => ({ value: b.id, label: b.filename }))}
                />
                <label className="flex items-start gap-2 text-sm text-foreground">
                  <input type="checkbox" name="useRules" defaultChecked className="mt-1 accent-[var(--accent)]" />
                  <span>
                    Recommend quantities from SPI&apos;s rules
                    <span className="block text-xs text-faint">
                      Smoke detection, call points, sounder-strobes, access control and data outlets, each
                      citing its rule. Cameras and access points have no placement rule and are not recommended.
                    </span>
                  </span>
                </label>
                <details className="text-xs text-muted">
                  <summary className="cursor-pointer">More options</summary>
                  <div className="mt-2 space-y-2">
                    <Field label="Device layers" name="deviceLayers" hint="Comma-separated, e.g. E-FIRE, E-SEC. Empty counts every layer, so doors and windows show as not counted." />
                    <Field label="Floor-to-floor height (m)" name="storeyHeight" type="number" step="0.01" hint="Empty: the engine assumes one and says so." />
                  </div>
                </details>
              </ActionForm>
            )}
          </Card>
        </div>

        <div className="xl:col-span-3">
          <Card title={`Checks (${runs.length})`}>
            {runs.length === 0 ? (
              <Empty>No checks run yet.</Empty>
            ) : (
              <ul className="divide-y divide-line">
                {runs.map((r) => (
                  <li key={r.id}>
                    <Link href={`/projects/${id}/review/${r.id}`} className="flex items-center justify-between gap-3 py-3 hover:bg-white/[0.02]">
                      <div className="min-w-0">
                        <div className="truncate text-sm text-foreground">{r.inputs.join(" · ") || "—"}</div>
                        <div className="text-xs text-faint">{r.createdAt.toLocaleString()}</div>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        {r.summary && (
                          <>
                            <span className="rounded-full bg-warn/15 px-2 py-0.5 text-[11px] font-medium text-warn">
                              {r.summary.review} to review
                            </span>
                            <span className="rounded-full bg-white/8 px-2 py-0.5 text-[11px] text-muted">
                              {r.summary.info} notes
                            </span>
                          </>
                        )}
                        <Pill value={r.status} />
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
