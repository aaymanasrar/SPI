import Link from "next/link";
import { requireSession } from "@/lib/auth";
import { can } from "@/lib/rbac";
import { listProjects, listClients } from "@/modules/projects/repository";
import { createProjectAction } from "@/modules/projects/actions";
import { ActionForm } from "@/components/action-form";
import { Card, Field, Select, Table, Pill, Empty, NoPermission } from "@/components/ui";

export default async function ProjectsPage() {
  const session = await requireSession();
  const [projects, clients, mayCreate] = await Promise.all([
    listProjects(session.organizationId),
    listClients(session.organizationId),
    can("project.create"),
  ]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
          Projects
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {projects.length} active project{projects.length === 1 ? "" : "s"}
        </p>
      </div>

      <Card title="All projects">
        {projects.length === 0 ? (
          <Empty>No projects yet.</Empty>
        ) : (
          <Table
            head={[
              "Project",
              "Client",
              "Jurisdiction",
              "Systems",
              "Buildings",
              "Rooms",
              "Doors",
              "Status",
            ]}
          >
            {projects.map((p) => (
              <tr key={p.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                <td className="px-2 py-2">
                  <Link
                    href={`/projects/${p.id}`}
                    className="font-medium text-teal-700 hover:underline dark:text-teal-400"
                  >
                    {p.name}
                  </Link>
                  {p.code && (
                    <span className="ml-2 text-xs text-slate-400">{p.code}</span>
                  )}
                </td>
                <td className="px-2 py-2 text-slate-600 dark:text-slate-400">
                  {p.clientName ?? "—"}
                </td>
                <td className="px-2 py-2 text-slate-600 dark:text-slate-400">
                  {p.jurisdiction ?? "—"}
                </td>
                <td className="px-2 py-2 text-xs text-slate-600 dark:text-slate-400">
                  {p.systemCodes.length
                    ? p.systemCodes.join(", ").replace(/_/g, " ")
                    : "—"}
                </td>
                <td className="px-2 py-2 tabular-nums">{p.buildingCount}</td>
                <td className="px-2 py-2 tabular-nums">{p.roomCount}</td>
                <td className="px-2 py-2 tabular-nums">{p.doorCount}</td>
                <td className="px-2 py-2">
                  <Pill value={p.status} />
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      <Card
        title="New project"
        description="A project holds one building model, shared by every system."
      >
        {mayCreate ? (
          <ActionForm
            action={createProjectAction}
            submitLabel="Create project"
            resetOnSuccess
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <Field
                label="Project name"
                name="name"
                required
                placeholder="e.g. Block 4 ELV Upgrade"
              />
              <Field
                label="Project code"
                name="code"
                placeholder="Optional internal reference"
              />
              <Select
                label="Client"
                name="clientId"
                includeBlank="No client yet"
                options={clients.map((c) => ({ value: c.id, label: c.name }))}
              />
              <Field
                label="Jurisdiction"
                name="jurisdiction"
                placeholder="e.g. Saudi Aramco"
                hint="Determines which engineering rules apply later."
              />
            </div>
          </ActionForm>
        ) : (
          <NoPermission what="creating projects" />
        )}
      </Card>
    </div>
  );
}
