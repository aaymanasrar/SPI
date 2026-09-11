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
import {
  Card,
  Field,
  Select,
  Stat,
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

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
              {project.name}
            </h1>
            <Pill value={project.status} />
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {project.clientName ?? "No client"}
            {project.jurisdiction ? ` · ${project.jurisdiction}` : ""}
            {project.code ? ` · ${project.code}` : ""}
          </p>
        </div>
        <Link
          href={`/projects/${id}/building`}
          className="rounded-md bg-teal-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-800"
        >
          Building model →
        </Link>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Buildings" value={project.buildingCount} />
        <Stat label="Rooms" value={project.roomCount} />
        <Stat label="Doors" value={project.doorCount} />
        <Stat label="Documents" value={project.documentCount} />
      </div>

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
