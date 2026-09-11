"use server";

import { z } from "zod";
import { revalidatePath } from "next/cache";
import { transaction } from "@/lib/db";
import { requirePermission } from "@/lib/rbac";
import { recordAudit } from "@/lib/audit";
import { runAction, optionalText, type ActionState } from "@/lib/action";
import * as repo from "./repository";
import { assertProjectInOrg } from "@/modules/building/repository";

/**
 * Project and client mutations.
 *
 * Every action calls requirePermission() before touching anything. Server
 * Actions accept direct POST requests regardless of what the UI renders, so
 * the check has to live here — not in the component that decides whether to
 * show a button.
 */

const createProjectSchema = z.object({
  name: z.string().trim().min(1, "Project name is required").max(200),
  code: optionalText,
  jurisdiction: optionalText,
  clientId: z.string().uuid().nullable().catch(null),
});

export async function createProjectAction(
  _prev: ActionState,
  formData: FormData
): Promise<ActionState> {
  return runAction(async () => {
    const session = await requirePermission("project.create");

    const input = createProjectSchema.parse({
      name: formData.get("name") ?? "",
      code: formData.get("code") ?? "",
      jurisdiction: formData.get("jurisdiction") ?? "",
      clientId: formData.get("clientId") || null,
    });

    const project = await transaction(async (tx) => {
      const created = await repo.createProject(tx, {
        organizationId: session.organizationId,
        createdBy: session.userId,
        ...input,
      });
      // Same transaction: an audit entry for a write that rolled back would be
      // a record of something that never happened.
      await recordAudit(
        session,
        {
          action: "project.create",
          subjectType: "project",
          subjectId: created.id,
          after: created,
        },
        tx
      );
      return created;
    });

    revalidatePath("/projects");
    return { ok: true, message: `Project "${project.name}" created.` };
  });
}

const updateProjectSchema = z.object({
  projectId: z.string().uuid(),
  name: z.string().trim().min(1).max(200),
  code: optionalText,
  jurisdiction: optionalText,
  clientId: z.string().uuid().nullable().catch(null),
  status: z.enum(["draft", "active", "on_hold", "completed"]),
});

export async function updateProjectAction(
  _prev: ActionState,
  formData: FormData
): Promise<ActionState> {
  return runAction(async () => {
    const session = await requirePermission("project.update");

    const { projectId, ...patch } = updateProjectSchema.parse({
      projectId: formData.get("projectId"),
      name: formData.get("name") ?? "",
      code: formData.get("code") ?? "",
      jurisdiction: formData.get("jurisdiction") ?? "",
      clientId: formData.get("clientId") || null,
      status: formData.get("status") ?? "draft",
    });

    const before = await repo.getProject(session.organizationId, projectId);
    if (!before) return { ok: false, error: "Project not found." };

    await transaction(async (tx) => {
      const updated = await repo.updateProject(
        tx,
        session.organizationId,
        projectId,
        patch
      );
      await recordAudit(
        session,
        {
          action: "project.update",
          subjectType: "project",
          subjectId: projectId,
          before,
          after: updated,
        },
        tx
      );
    });

    revalidatePath(`/projects/${projectId}`);
    revalidatePath("/projects");
    return { ok: true, message: "Project updated." };
  });
}

export async function archiveProjectAction(
  _prev: ActionState,
  formData: FormData
): Promise<ActionState> {
  return runAction(async () => {
    const session = await requirePermission("project.archive");
    const projectId = z.string().uuid().parse(formData.get("projectId"));

    const before = await repo.getProject(session.organizationId, projectId);
    if (!before) return { ok: false, error: "Project not found." };

    // Archived, never deleted — spec §20.1. The project is the root that
    // approved BOQs and issued quotations hang from.
    await transaction(async (tx) => {
      await repo.archiveProject(tx, session.organizationId, projectId);
      await recordAudit(
        session,
        {
          action: "project.archive",
          subjectType: "project",
          subjectId: projectId,
          before,
        },
        tx
      );
    });

    revalidatePath("/projects");
    return { ok: true, message: "Project archived." };
  });
}

const createClientSchema = z.object({
  name: z.string().trim().min(1, "Client name is required").max(200),
  contactName: optionalText,
  contactEmail: z
    .string()
    .trim()
    .transform((v) => (v === "" ? null : v))
    .nullable()
    .refine(
      (v) => v === null || z.email().safeParse(v).success,
      "Must be a valid email"
    ),
  contactPhone: optionalText,
});

export async function createClientAction(
  _prev: ActionState,
  formData: FormData
): Promise<ActionState> {
  return runAction(async () => {
    // Clients are created while setting a project up, so this shares the
    // project.create permission rather than introducing a separate one.
    const session = await requirePermission("project.create");

    const input = createClientSchema.parse({
      name: formData.get("name") ?? "",
      contactName: formData.get("contactName") ?? "",
      contactEmail: formData.get("contactEmail") ?? "",
      contactPhone: formData.get("contactPhone") ?? "",
    });

    await transaction(async (tx) => {
      const created = await repo.createClient(tx, {
        organizationId: session.organizationId,
        ...input,
      });
      await recordAudit(
        session,
        {
          action: "client.create",
          subjectType: "client",
          subjectId: created.id,
          after: created,
        },
        tx
      );
    });

    revalidatePath("/clients");
    revalidatePath("/projects");
    return { ok: true, message: "Client created." };
  });
}

export async function setProjectSystemsAction(
  _prev: ActionState,
  formData: FormData
): Promise<ActionState> {
  return runAction(async () => {
    const session = await requirePermission("system.select");
    const projectId = z.string().uuid().parse(formData.get("projectId"));
    const systemIds = formData
      .getAll("systemIds")
      .map(String)
      .filter((v) => z.string().uuid().safeParse(v).success);

    if (!(await assertProjectInOrg(session.organizationId, projectId))) {
      return { ok: false, error: "Project not found." };
    }

    await transaction(async (tx) => {
      await repo.setProjectSystems(tx, projectId, systemIds);
      await recordAudit(
        session,
        {
          action: "project.systems.set",
          subjectType: "project",
          subjectId: projectId,
          after: { systemIds },
        },
        tx
      );
    });

    revalidatePath(`/projects/${projectId}`);
    return { ok: true, message: "Systems updated." };
  });
}

const requirementSchema = z.object({
  projectId: z.string().uuid(),
  projectSystemId: z.string().uuid(),
  key: z.string().trim().min(1, "Requirement name is required").max(120),
  value: z.string().trim().min(1, "Value is required"),
  sourceReference: optionalText,
});

/**
 * Records a project requirement — something the client or the scope asked
 * for, with where it came from. This is an input to engineering, never an
 * engineering conclusion, so source is always 'manual' here.
 */
export async function upsertRequirementAction(
  _prev: ActionState,
  formData: FormData
): Promise<ActionState> {
  return runAction(async () => {
    const session = await requirePermission("system.select");

    const input = requirementSchema.parse({
      projectId: formData.get("projectId"),
      projectSystemId: formData.get("projectSystemId"),
      key: formData.get("key") ?? "",
      value: formData.get("value") ?? "",
      sourceReference: formData.get("sourceReference") ?? "",
    });

    if (!(await assertProjectInOrg(session.organizationId, input.projectId))) {
      return { ok: false, error: "Project not found." };
    }

    await transaction(async (tx) => {
      await repo.upsertRequirement(tx, {
        projectSystemId: input.projectSystemId,
        key: input.key,
        value: input.value,
        sourceReference: input.sourceReference,
        createdBy: session.userId,
      });
      await recordAudit(
        session,
        {
          action: "requirement.upsert",
          subjectType: "system_requirement",
          subjectId: input.projectSystemId,
          after: { key: input.key, value: input.value },
        },
        tx
      );
    });

    revalidatePath(`/projects/${input.projectId}`);
    return { ok: true, message: "Requirement saved." };
  });
}
