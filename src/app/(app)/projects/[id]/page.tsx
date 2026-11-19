import Link from "next/link";
import { notFound } from "next/navigation";
import { requireSession } from "@/lib/auth";
import { can } from "@/lib/rbac";
import {
  getProject,
  listClients,
  listSystems,
  listRequirements,
} from "@/modules/projects/repository";
import {
  updateProjectAction,
  setProjectSystemsAction,
} from "@/modules/projects/actions";
import { sql } from "@/lib/db";
import { ActionForm } from "@/components/action-form";
import { getProjectDashboard } from "@/modules/dashboard/repository";
import {
  ActivityList,
  BarChart,
  BuildingCanvas,
  Donut,
  FloatPill,
  Gauge,
  KpiTile,
  Panel,
  Sparkline,
} from "@/components/dashboard";
import {
  Card,
  Field,
  Select,
  Table,
  Pill,
  Empty,
  NoPermission,
} from "@/components/ui";

export default async function ProjectPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  // params is a Promise in Next.js 16.
  const { id } = await params;
  const session = await requireSession();

  const project = await getProject(session.organizationId, id);
  if (!project) notFound();

  const [clients, systems, requirements, maySelectSystems, mayUpdate] =
    await Promise.all([
      listClients(session.organizationId),
      listSystems(),
      listRequirements(session.organizationId, id),
      can("system.select"),
      can("project.update"),
    ]);

  const selected = await sql<{ systemId: string }[]>`
    select system_id from project_systems where project_id = ${id}
  `;
  const selectedIds = new Set(selected.map((s) => s.systemId));

  const dash = await getProjectDashboard(session.organizationId, id);
  const rooms = dash.floors.flatMap((f) => f.rooms);
  const totalRooms = rooms.length;
  const grossArea = rooms.reduce((s, r) => s + (r.areaSqm ?? 0), 0);
  const cleared = dash.review.approved + dash.review.not_required;
  const largest = rooms.reduce<(typeof rooms)[number] | null>(
    (best, r) => ((r.areaSqm ?? -1) > (best?.areaSqm ?? -1) ? r : best),
    null
  );
  const largestFloor = largest
    ? dash.floors.find((f) => f.rooms.includes(largest))
    : undefined;
  const floorBars = [...dash.floors]
    .reverse()
    .map((f) => ({
      label: f.name,
      value:
        grossArea > 0
          ? f.rooms.reduce((s, r) => s + (r.areaSqm ?? 0), 0)
          : f.rooms.length,
    }));
  const typeMix = Object.entries(
    rooms.reduce<Record<string, number>>((acc, r) => {
      const k = r.roomType?.trim() || "Unclassified";
      acc[k] = (acc[k] ?? 0) + 1;
      return acc;
    }, {})
  ).map(([label, value]) => ({ label, value }));
  const systemNames = systems.filter((s) => selectedIds.has(s.id)).map((s) => s.name);
  const area = new Intl.NumberFormat("en", { maximumFractionDigits: 0 });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.2em] text-muted">
            {project.code ?? "Project"}
          </p>
          <div className="mt-1 flex items-center gap-2.5">
            <h1 className="text-2xl font-light tracking-tight">{project.name}</h1>
            <Pill value={project.status} />
          </div>
          <p className="mt-0.5 text-sm text-muted">
            {project.clientName ?? "No client"}
            {project.jurisdiction ? ` · ${project.jurisdiction}` : ""}
          </p>
        </div>
        <Link
          href={`/projects/${id}/building`}
          className="rounded-full bg-accent px-4 py-2 text-sm font-medium text-accent-ink hover:brightness-110"
        >
          Building model →
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <Panel
          className="flex flex-col xl:col-span-8"
          title="Building"
          subtitle={`${project.buildingCount} building${project.buildingCount === 1 ? "" : "s"} · ${dash.floors.length} floors · rooms sized by area`}
        >
          {dash.floors.length === 0 ? (
            <div className="blueprint grid min-h-[420px] place-items-center rounded-xl border border-line p-6 text-center">
              <div>
                <p className="text-sm">No floors in the building model yet.</p>
                <Link href={`/projects/${id}/building`} className="mt-2 inline-block text-xs text-accent hover:underline">
                  Add buildings and floors →
                </Link>
              </div>
            </div>
          ) : (
            <BuildingCanvas
              floors={dash.floors}
              overlay={
                systemNames.length > 0 ? (
                  systemNames.map((n, i) => (
                    <FloatPill key={n} lit={i === 0}>{n}</FloatPill>
                  ))
                ) : (
                  <FloatPill>No systems in scope</FloatPill>
                )
              }
              callout={
                largest && largest.areaSqm ? (
                  <div className="glass rounded-xl p-3">
                    <div className="text-[10px] uppercase tracking-[0.18em] text-muted">Largest space</div>
                    <div className="mt-1 truncate text-sm font-medium">
                      {largest.code ? `${largest.code} · ` : ""}{largest.name}
                    </div>
                    <div className="mt-1 flex items-baseline gap-1">
                      <span className="text-xl font-light tabular-nums">{area.format(largest.areaSqm)}</span>
                      <span className="text-xs text-muted">m²</span>
                      <span className="ml-auto"><Pill value={largest.reviewStatus} /></span>
                    </div>
                    <div className="mt-0.5 text-[11px] text-faint">
                      {largestFloor?.name}{largest.roomType ? ` · ${largest.roomType}` : ""}
                    </div>
                  </div>
                ) : undefined
              }
            />
          )}
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted">
            <Legend className="border-accent/70 bg-accent/20">Approved</Legend>
            <Legend className="border-leaf/35 bg-leaf/12">Entered by hand</Legend>
            <Legend className="border-dashed border-warn/70 bg-warn/10">Pending review</Legend>
            <Legend className="border-danger/60 bg-danger/12">Rejected</Legend>
          </div>
        </Panel>

        <div className="space-y-4 xl:col-span-4">
          <Panel
            title="Project overview"
            actions={
              <Link
                href={`/projects/${id}/building`}
                aria-label="Open building model"
                className="grid h-8 w-8 place-items-center rounded-full border border-line-strong text-muted hover:text-foreground"
              >
                ↗
              </Link>
            }
          >
            <div className="grid grid-cols-2 gap-2.5">
              <KpiTile
                label="Rooms"
                value={totalRooms}
                badge={dash.review.pending ? `${dash.review.pending} to review` : totalRooms ? "Clear" : undefined}
                badgeTone={dash.review.pending ? "warn" : "leaf"}
              >
                <Sparkline values={dash.roomGrowth} />
              </KpiTile>
              <KpiTile
                label="Doors"
                value={dash.doors.total}
                badge={dash.doors.escape ? `${dash.doors.escape} escape` : undefined}
              >
                <DoorBars fire={dash.doors.fireRated} total={dash.doors.total} />
              </KpiTile>
              <KpiTile
                label="Gross area"
                value={grossArea > 0 ? area.format(grossArea) : "—"}
                unit={grossArea > 0 ? "m²" : undefined}
                badge={`${project.documentCount} docs`}
                badgeTone="leaf"
              >
                <div className="text-[11px] leading-relaxed text-faint">
                  {rooms.filter((r) => r.areaSqm == null).length} rooms without an area
                </div>
              </KpiTile>
              <KpiTile label="Model cleared" value="">
                <Gauge
                  value={totalRooms ? cleared / totalRooms : null}
                  caption={totalRooms ? `${cleared} of ${totalRooms}` : "no rooms"}
                />
              </KpiTile>
            </div>
          </Panel>

          <Panel title="Recent engine runs" subtitle="Grid, Word, CAD, PDF and BIM tools">
            <ActivityList operations={dash.operations} />
          </Panel>
        </div>

        <Panel className="xl:col-span-5" title="Room mix" subtitle="Rooms by type">
          {typeMix.length === 0 ? (
            <p className="py-8 text-center text-xs text-muted">No rooms recorded.</p>
          ) : (
            <Donut slices={typeMix} centerLabel="rooms" />
          )}
        </Panel>

        <Panel
          className="xl:col-span-7"
          title={grossArea > 0 ? "Area by floor" : "Rooms by floor"}
          subtitle={grossArea > 0 ? "Net room area, m², lowest floor first" : "Room count, lowest floor first"}
        >
          {floorBars.length === 0 ? (
            <p className="py-8 text-center text-xs text-muted">No floors recorded.</p>
          ) : (
            <BarChart bars={floorBars} unit={grossArea > 0 ? "m²" : "rooms"} />
          )}
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
      <Card
        title="Systems"
        description="Which systems this project covers. Selecting a system does not design anything — it records scope."
      >
        {maySelectSystems ? (
          <ActionForm action={setProjectSystemsAction} submitLabel="Save systems">
            <input type="hidden" name="projectId" value={id} />
            <div className="space-y-2">
              {systems.map((s) => (
                <label key={s.id} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    name="systemIds"
                    value={s.id}
                    defaultChecked={selectedIds.has(s.id)}
                    className="h-4 w-4 rounded border-slate-300 text-teal-700 focus:ring-teal-600"
                  />
                  <span className="text-slate-800 dark:text-slate-200">
                    {s.name}
                  </span>
                </label>
              ))}
            </div>
          </ActionForm>
        ) : (
          <NoPermission what="changing which systems a project covers" />
        )}
      </Card>

      <Card
        title="Requirements"
        description="What the client or scope asked for, and where it came from. These are inputs to engineering, never conclusions the system reached on its own."
      >
        {requirements.length === 0 ? (
          <Empty>No requirements recorded.</Empty>
        ) : (
          <Table head={["System", "Requirement", "Value", "Source"]}>
            {requirements.map((r) => (
              <tr key={r.id}>
                <td className="px-2 py-2 text-slate-600 dark:text-slate-400">
                  {r.systemName}
                </td>
                <td className="px-2 py-2 font-medium">{r.key}</td>
                <td className="px-2 py-2">{String(r.value)}</td>
                <td className="px-2 py-2 text-xs text-slate-500 dark:text-slate-400">
                  {r.sourceReference ?? r.source}
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      </div>

      <Card title="Project details">
        {mayUpdate ? (
          <ActionForm action={updateProjectAction} submitLabel="Save changes">
            <input type="hidden" name="projectId" value={id} />
            <div className="grid gap-3 sm:grid-cols-2">
              <Field
                label="Project name"
                name="name"
                required
                defaultValue={project.name}
              />
              <Field label="Project code" name="code" defaultValue={project.code} />
              <Select
                label="Client"
                name="clientId"
                includeBlank="No client"
                defaultValue={project.clientId}
                options={clients.map((c) => ({ value: c.id, label: c.name }))}
              />
              <Field
                label="Jurisdiction"
                name="jurisdiction"
                defaultValue={project.jurisdiction}
              />
              <Select
                label="Status"
                name="status"
                defaultValue={project.status}
                options={[
                  { value: "draft", label: "Draft" },
                  { value: "active", label: "Active" },
                  { value: "on_hold", label: "On hold" },
                  { value: "completed", label: "Completed" },
                ]}
                hint="Archiving is a separate action and cannot be undone here."
              />
            </div>
          </ActionForm>
        ) : (
          <NoPermission what="editing project details" />
        )}
      </Card>
    </div>
  );
}

function Legend({ className, children }: { className: string; children: React.ReactNode }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={`h-2.5 w-3.5 rounded-sm border ${className}`} />
      {children}
    </span>
  );
}

/** One stick per door, gold where the door carries a fire rating. */
function DoorBars({ fire, total }: { fire: number; total: number }) {
  if (total === 0) return <div className="h-12 border-b border-dashed border-line-strong" />;
  const n = Math.min(total, 14);
  const lit = Math.round((fire / total) * n);
  return (
    <div>
      <div className="flex h-10 items-end justify-between">
        {Array.from({ length: n }, (_, i) => (
          <span key={i} className="flex flex-col items-center">
            <span className={`h-1.5 w-1.5 rounded-full ${i < lit ? "bg-accent" : "bg-foreground/70"}`} />
            <span className={`w-px ${i < lit ? "h-7 bg-accent/60" : "h-5 bg-foreground/25"}`} />
          </span>
        ))}
      </div>
      <div className="mt-1 text-[10px] text-faint">{fire} fire-rated</div>
    </div>
  );
}
