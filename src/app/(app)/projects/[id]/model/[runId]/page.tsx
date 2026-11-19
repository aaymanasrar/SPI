import Link from "next/link";
import { notFound } from "next/navigation";
import { z } from "zod";
import { requireSession } from "@/lib/auth";
import { getProject } from "@/modules/projects/repository";
import { listBuildingRuns } from "@/modules/prototype/repository";
import { NoPermission, Pill } from "@/components/ui";

export default async function ModelViewerPage({
  params,
}: {
  params: Promise<{ id: string; runId: string }>;
}) {
  const { id, runId } = await params;
  if (!z.string().uuid().safeParse(runId).success) notFound();
  const session = await requireSession();
  const project = await getProject(session.organizationId, id);
  if (!project) notFound();
  if (!session.permissions.has("craft.preview")) {
    return <NoPermission what="viewing engine results" />;
  }
  const run = (await listBuildingRuns(session.organizationId, id)).find((r) => r.id === runId);
  if (!run) notFound();

  const viewer = `/projects/${id}/model/${runId}/viewer`;
  return (
    <div className="flex h-[calc(100dvh-3rem)] flex-col gap-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <Link href={`/projects/${id}/model`} className="text-xs text-muted hover:text-foreground">
            ← 3D model &amp; drawings
          </Link>
          <h1 className="mt-1 flex items-center gap-2 truncate text-xl font-light tracking-tight text-foreground">
            {run.name || project.name} <Pill value={run.status} />
          </h1>
          <p className="truncate text-xs text-muted">
            {run.tool === "bim.scene_3d" ? "From IFC model" : "Proposed from floor plans"} ·{" "}
            {run.files.join(", ")} · {run.levels} levels · {run.rooms} rooms
          </p>
        </div>
        <a
          href={viewer}
          target="_blank"
          rel="noopener"
          className="rounded-full border border-line-strong px-3.5 py-1.5 text-xs text-foreground hover:bg-white/5"
        >
          Open full screen ↗
        </a>
      </div>
      <iframe
        src={viewer}
        title={`3D model of ${project.name}`}
        className="min-h-[520px] w-full flex-1 rounded-2xl border border-line bg-black"
      />
    </div>
  );
}
