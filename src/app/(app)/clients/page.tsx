import { requireSession } from "@/lib/auth";
import { can } from "@/lib/rbac";
import { listClients } from "@/modules/projects/repository";
import { createClientAction } from "@/modules/projects/actions";
import { ActionForm } from "@/components/action-form";
import { Card, Field, Table, Empty, NoPermission } from "@/components/ui";

export default async function ClientsPage() {
  const session = await requireSession();
  const [clients, mayCreate] = await Promise.all([
    listClients(session.organizationId),
    can("project.create"),
  ]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
          Clients
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {clients.length} client{clients.length === 1 ? "" : "s"}
        </p>
      </div>

      <Card title="All clients">
        {clients.length === 0 ? (
          <Empty>No clients yet.</Empty>
        ) : (
          <Table head={["Name", "Contact", "Email", "Phone"]}>
            {clients.map((c) => (
              <tr key={c.id}>
                <td className="px-2 py-2 font-medium">{c.name}</td>
                <td className="px-2 py-2 text-slate-600 dark:text-slate-400">
                  {c.contactName ?? "—"}
                </td>
                <td className="px-2 py-2 text-slate-600 dark:text-slate-400">
                  {c.contactEmail ?? "—"}
                </td>
                <td className="px-2 py-2 text-slate-600 dark:text-slate-400">
                  {c.contactPhone ?? "—"}
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      <Card title="New client">
        {mayCreate ? (
          <ActionForm
            action={createClientAction}
            submitLabel="Create client"
            resetOnSuccess
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Client name" name="name" required />
              <Field label="Contact name" name="contactName" />
              <Field label="Contact email" name="contactEmail" type="email" />
              <Field label="Contact phone" name="contactPhone" />
            </div>
          </ActionForm>
        ) : (
          <NoPermission what="creating clients" />
        )}
      </Card>
    </div>
  );
}
