import "server-only";
import type postgres from "postgres";
import { sql } from "@/lib/db";

/**
 * Project and client data access.
 *
 * Every query here takes organizationId and filters on it. Tenant scoping
 * lives in this layer rather than at call sites, because a single forgotten
 * WHERE clause at a call site is a cross-tenant data leak
 * (ARCHITECTURE.md §6.1).
 */

export type ProjectStatus =
  | "draft"
  | "active"
  | "on_hold"
  | "completed"
  | "archived";

export type Client = {
  id: string;
  name: string;
  contactName: string | null;
  contactEmail: string | null;
  contactPhone: string | null;
  createdAt: Date;
};

export type Project = {
  id: string;
  name: string;
  code: string | null;
  jurisdiction: string | null;
  status: ProjectStatus;
  clientId: string | null;
  clientName: string | null;
  createdAt: Date;
  updatedAt: Date;
};

export type ProjectSummary = Project & {
  buildingCount: number;
  roomCount: number;
  doorCount: number;
  documentCount: number;
  systemCodes: string[];
};

export async function listProjects(
  organizationId: string,
  opts: { includeArchived?: boolean } = {}
): Promise<ProjectSummary[]> {
  return sql<ProjectSummary[]>`
    select
      p.id, p.name, p.code, p.jurisdiction, p.status,
      p.client_id, c.name as client_name,
      p.created_at, p.updated_at,
      (select count(*) from buildings b where b.project_id = p.id)::int as building_count,
      (select count(*) from rooms r
         join floors f   on f.id = r.floor_id
         join buildings b on b.id = f.building_id
        where b.project_id = p.id)::int as room_count,
      (select count(*) from doors d
         join floors f   on f.id = d.floor_id
         join buildings b on b.id = f.building_id
        where b.project_id = p.id)::int as door_count,
      (select count(*) from documents dc where dc.project_id = p.id)::int as document_count,
      coalesce((
        select array_agg(s.code order by s.code)
        from project_systems ps
        join systems s on s.id = ps.system_id
        where ps.project_id = p.id
      ), '{}') as system_codes
    from projects p
    left join clients c on c.id = p.client_id
    where p.organization_id = ${organizationId}
      ${opts.includeArchived ? sql`` : sql`and p.archived_at is null`}
    order by p.updated_at desc
  `;
}

export async function getProject(
  organizationId: string,
  projectId: string
): Promise<ProjectSummary | null> {
  const rows = await sql<ProjectSummary[]>`
    select
      p.id, p.name, p.code, p.jurisdiction, p.status,
      p.client_id, c.name as client_name,
      p.created_at, p.updated_at,
      (select count(*) from buildings b where b.project_id = p.id)::int as building_count,
      (select count(*) from rooms r
         join floors f   on f.id = r.floor_id
         join buildings b on b.id = f.building_id
        where b.project_id = p.id)::int as room_count,
      (select count(*) from doors d
         join floors f   on f.id = d.floor_id
         join buildings b on b.id = f.building_id
        where b.project_id = p.id)::int as door_count,
      (select count(*) from documents dc where dc.project_id = p.id)::int as document_count,
      coalesce((
        select array_agg(s.code order by s.code)
        from project_systems ps
        join systems s on s.id = ps.system_id
        where ps.project_id = p.id
      ), '{}') as system_codes
    from projects p
    left join clients c on c.id = p.client_id
    where p.organization_id = ${organizationId}
      and p.id = ${projectId}
  `;
  return rows[0] ?? null;
}

export async function createProject(
  tx: postgres.TransactionSql,
  input: {
    organizationId: string;
    createdBy: string;
    name: string;
    code: string | null;
    jurisdiction: string | null;
    clientId: string | null;
  }
): Promise<Project> {
  const rows = await tx<Project[]>`
    insert into projects
      (organization_id, created_by, name, code, jurisdiction, client_id, status)
    values (
      ${input.organizationId}, ${input.createdBy}, ${input.name},
      ${input.code}, ${input.jurisdiction}, ${input.clientId}, 'draft'
    )
    returning id, name, code, jurisdiction, status, client_id,
              null::text as client_name, created_at, updated_at
  `;
  return rows[0];
}

export async function updateProject(
  tx: postgres.TransactionSql,
  organizationId: string,
  projectId: string,
  patch: {
    name?: string;
    code?: string | null;
    jurisdiction?: string | null;
    clientId?: string | null;
    status?: ProjectStatus;
  }
): Promise<Project | null> {
  const rows = await tx<Project[]>`
    update projects set
      name         = coalesce(${patch.name ?? null}, name),
      code         = ${patch.code !== undefined ? patch.code : sql`code`},
      jurisdiction = ${patch.jurisdiction !== undefined ? patch.jurisdiction : sql`jurisdiction`},
      client_id    = ${patch.clientId !== undefined ? patch.clientId : sql`client_id`},
      status       = coalesce(${patch.status ?? null}, status)
    where organization_id = ${organizationId}
      and id = ${projectId}
    returning id, name, code, jurisdiction, status, client_id,
              null::text as client_name, created_at, updated_at
  `;
  return rows[0] ?? null;
}

/**
 * Archive rather than delete. Spec §20.1: approved engineering and commercial
 * records are never destroyed, and a project is the root they hang from.
 */
export async function archiveProject(
  tx: postgres.TransactionSql,
  organizationId: string,
  projectId: string
): Promise<boolean> {
  const rows = await tx`
    update projects
       set archived_at = now(), status = 'archived'
     where organization_id = ${organizationId}
       and id = ${projectId}
       and archived_at is null
    returning id
  `;
  return rows.length > 0;
}

export async function listClients(organizationId: string): Promise<Client[]> {
  return sql<Client[]>`
    select id, name, contact_name, contact_email, contact_phone, created_at
      from clients
     where organization_id = ${organizationId}
       and archived_at is null
     order by name
  `;
}

export async function createClient(
  tx: postgres.TransactionSql,
  input: {
    organizationId: string;
    name: string;
    contactName: string | null;
    contactEmail: string | null;
    contactPhone: string | null;
  }
): Promise<Client> {
  const rows = await tx<Client[]>`
    insert into clients
      (organization_id, name, contact_name, contact_email, contact_phone)
    values (
      ${input.organizationId}, ${input.name}, ${input.contactName},
      ${input.contactEmail}, ${input.contactPhone}
    )
    returning id, name, contact_name, contact_email, contact_phone, created_at
  `;
  return rows[0];
}

/** Systems available to select. Reference data, not tenant-scoped. */
export async function listSystems(): Promise<
  { id: string; code: string; name: string }[]
> {
  return sql<{ id: string; code: string; name: string }[]>`
    select id, code, name from systems order by name
  `;
}

export async function setProjectSystems(
  tx: postgres.TransactionSql,
  projectId: string,
  systemIds: string[]
): Promise<void> {
  // Only removes selections that have not started design work. Removing a
  // system that already has devices would orphan engineering output.
  await tx`
    delete from project_systems
     where project_id = ${projectId}
       and status = 'selected'
       ${systemIds.length ? tx`and system_id <> all(${systemIds}::uuid[])` : tx``}
  `;

  for (const systemId of systemIds) {
    await tx`
      insert into project_systems (project_id, system_id, status)
      values (${projectId}, ${systemId}, 'selected')
      on conflict (project_id, system_id) do nothing
    `;
  }
}

export type SystemRequirement = {
  id: string;
  systemCode: string;
  systemName: string;
  key: string;
  value: unknown;
  source: string;
  sourceReference: string | null;
};

export async function listRequirements(
  organizationId: string,
  projectId: string
): Promise<SystemRequirement[]> {
  return sql<SystemRequirement[]>`
    select sr.id, s.code as system_code, s.name as system_name,
           sr.key, sr.value, sr.source, sr.source_reference
      from system_requirements sr
      join project_systems ps on ps.id = sr.project_system_id
      join systems s          on s.id = ps.system_id
      join projects p         on p.id = ps.project_id
     where p.organization_id = ${organizationId}
       and p.id = ${projectId}
     order by s.name, sr.key
  `;
}

/**
 * Requirements are project inputs, not engineering conclusions. They record
 * what was asked for, with where it came from — never a value the system
 * decided on its own.
 */
export async function upsertRequirement(
  tx: postgres.TransactionSql,
  input: {
    projectSystemId: string;
    key: string;
    value: unknown;
    sourceReference: string | null;
    createdBy: string;
  }
): Promise<void> {
  await tx`
    insert into system_requirements
      (project_system_id, key, value, source, source_reference, created_by)
    values (
      ${input.projectSystemId}, ${input.key}, ${JSON.stringify(input.value)},
      'manual', ${input.sourceReference}, ${input.createdBy}
    )
    on conflict (project_system_id, key) do update
      set value = excluded.value,
          source_reference = excluded.source_reference
  `;
}
