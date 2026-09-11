"use server";

import { z } from "zod";
import { revalidatePath } from "next/cache";
import { transaction } from "@/lib/db";
import { requirePermission } from "@/lib/rbac";
import { recordAudit } from "@/lib/audit";
import {
  runAction,
  optionalText,
  optionalNumber,
  optionalInt,
  type ActionState,
} from "@/lib/action";
import * as repo from "./repository";

/**
 * Building model mutations (spec §9).
 *
 * All of these write to the one canonical model shared by every system. Each
 * verifies the project belongs to the caller's organization before writing —
 * a nested id supplied in a form is attacker-controlled, so ownership is never
 * inferred from the fact that a valid-looking uuid arrived.
 */

const buildingSchema = z.object({
  projectId: z.string().uuid(),
  name: z.string().trim().min(1, "Building name is required").max(200),
  description: optionalText,
});

export async function createBuildingAction(
  _prev: ActionState,
  formData: FormData
): Promise<ActionState> {
  return runAction(async () => {
    const session = await requirePermission("building_model.edit");
    const input = buildingSchema.parse({
      projectId: formData.get("projectId"),
      name: formData.get("name") ?? "",
      description: formData.get("description") ?? "",
    });

    if (!(await repo.assertProjectInOrg(session.organizationId, input.projectId))) {
      return { ok: false, error: "Project not found." };
    }

    await transaction(async (tx) => {
      const created = await repo.createBuilding(tx, {
        projectId: input.projectId,
        name: input.name,
        description: input.description,
      });
      await recordAudit(
        session,
        {
          action: "building.create",
          subjectType: "building",
          subjectId: created.id,
          after: created,
        },
        tx
      );
    });

    revalidatePath(`/projects/${input.projectId}/building`);
    return { ok: true, message: "Building added." };
  });
}

const floorSchema = z.object({
  projectId: z.string().uuid(),
  buildingId: z.string().uuid(),
  name: z.string().trim().min(1, "Floor name is required").max(200),
  level: z.coerce.number().int("Level must be a whole number"),
  elevationM: optionalNumber,
});

export async function createFloorAction(
  _prev: ActionState,
  formData: FormData
): Promise<ActionState> {
  return runAction(async () => {
    const session = await requirePermission("building_model.edit");
    const input = floorSchema.parse({
      projectId: formData.get("projectId"),
      buildingId: formData.get("buildingId"),
      name: formData.get("name") ?? "",
      level: formData.get("level") ?? "0",
      elevationM: formData.get("elevationM") ?? "",
    });

    if (!(await repo.assertProjectInOrg(session.organizationId, input.projectId))) {
      return { ok: false, error: "Project not found." };
    }

    await transaction(async (tx) => {
      const created = await repo.createFloor(tx, {
        buildingId: input.buildingId,
        name: input.name,
        level: input.level,
        elevationM: input.elevationM,
      });
      await recordAudit(
        session,
        {
          action: "floor.create",
          subjectType: "floor",
          subjectId: created.id,
          after: created,
        },
        tx
      );
    });

    revalidatePath(`/projects/${input.projectId}/building`);
    return { ok: true, message: "Floor added." };
  });
}

const roomSchema = z.object({
  projectId: z.string().uuid(),
  floorId: z.string().uuid(),
  name: z.string().trim().min(1, "Room name is required").max(200),
  code: optionalText,
  roomType: optionalText,
  areaSqm: optionalNumber,
  heightM: optionalNumber,
  occupancy: optionalInt,
});

export async function createRoomAction(
  _prev: ActionState,
  formData: FormData
): Promise<ActionState> {
  return runAction(async () => {
    const session = await requirePermission("building_model.edit");
    const input = roomSchema.parse({
      projectId: formData.get("projectId"),
      floorId: formData.get("floorId"),
      name: formData.get("name") ?? "",
      code: formData.get("code") ?? "",
      roomType: formData.get("roomType") ?? "",
      areaSqm: formData.get("areaSqm") ?? "",
      heightM: formData.get("heightM") ?? "",
      occupancy: formData.get("occupancy") ?? "",
    });

    if (!(await repo.assertProjectInOrg(session.organizationId, input.projectId))) {
      return { ok: false, error: "Project not found." };
    }

    await transaction(async (tx) => {
      const created = await repo.createRoom(tx, {
        floorId: input.floorId,
        name: input.name,
        code: input.code,
        roomType: input.roomType,
        areaSqm: input.areaSqm,
        heightM: input.heightM,
        occupancy: input.occupancy,
        createdBy: session.userId,
      });
      await recordAudit(
        session,
        {
          action: "room.create",
          subjectType: "room",
          subjectId: created.id,
          after: created,
        },
        tx
      );
    });

    revalidatePath(`/projects/${input.projectId}/building`);
    return { ok: true, message: "Room added." };
  });
}

const doorSchema = z.object({
  projectId: z.string().uuid(),
  floorId: z.string().uuid(),
  code: optionalText,
  doorType: optionalText,
  widthMm: optionalInt,
  heightMm: optionalInt,
  fireRating: optionalText,
  securityLevel: optionalText,
  isEscapeRoute: z
    .union([z.literal("on"), z.literal(""), z.null()])
    .transform((v) => v === "on"),
  roomAId: z.string().uuid().nullable().catch(null),
  roomBId: z.string().uuid().nullable().catch(null),
});

/**
 * Doors are where Access Control, Fire Alarm and life-safety requirements meet
 * on one physical object (spec §15.1), which is why they carry fire rating,
 * security level and escape-route status from the start rather than having ACS
 * keep its own separate door list.
 */
export async function createDoorAction(
  _prev: ActionState,
  formData: FormData
): Promise<ActionState> {
  return runAction(async () => {
    const session = await requirePermission("building_model.edit");
    const input = doorSchema.parse({
      projectId: formData.get("projectId"),
      floorId: formData.get("floorId"),
      code: formData.get("code") ?? "",
      doorType: formData.get("doorType") ?? "",
      widthMm: formData.get("widthMm") ?? "",
      heightMm: formData.get("heightMm") ?? "",
      fireRating: formData.get("fireRating") ?? "",
      securityLevel: formData.get("securityLevel") ?? "",
      isEscapeRoute: formData.get("isEscapeRoute"),
      roomAId: formData.get("roomAId") || null,
      roomBId: formData.get("roomBId") || null,
    });

    if (!(await repo.assertProjectInOrg(session.organizationId, input.projectId))) {
      return { ok: false, error: "Project not found." };
    }

    await transaction(async (tx) => {
      const created = await repo.createDoor(tx, {
        floorId: input.floorId,
        code: input.code,
        doorType: input.doorType,
        widthMm: input.widthMm,
        heightMm: input.heightMm,
        fireRating: input.fireRating,
        securityLevel: input.securityLevel,
        isEscapeRoute: input.isEscapeRoute,
        roomAId: input.roomAId,
        roomBId: input.roomBId,
        createdBy: session.userId,
      });
      await recordAudit(
        session,
        {
          action: "door.create",
          subjectType: "door",
          subjectId: created.id,
          after: { ...input, id: created.id },
        },
        tx
      );
    });

    revalidatePath(`/projects/${input.projectId}/building`);
    return { ok: true, message: "Door added." };
  });
}

const updateRoomSchema = roomSchema.extend({ roomId: z.string().uuid() });

export async function updateRoomAction(
  _prev: ActionState,
  formData: FormData
): Promise<ActionState> {
  return runAction(async () => {
    const session = await requirePermission("building_model.edit");
    const input = updateRoomSchema.parse({
      roomId: formData.get("roomId"),
      projectId: formData.get("projectId"),
      floorId: formData.get("floorId"),
      name: formData.get("name") ?? "",
      code: formData.get("code") ?? "",
      roomType: formData.get("roomType") ?? "",
      areaSqm: formData.get("areaSqm") ?? "",
      heightM: formData.get("heightM") ?? "",
      occupancy: formData.get("occupancy") ?? "",
    });

    await transaction(async (tx) => {
      const updated = await repo.updateRoom(
        tx,
        session.organizationId,
        input.roomId,
        {
          name: input.name,
          code: input.code,
          roomType: input.roomType,
          areaSqm: input.areaSqm,
          heightM: input.heightM,
          occupancy: input.occupancy,
          updatedBy: session.userId,
        }
      );
      if (!updated) throw new Error("Room not found in this organization");
      await recordAudit(
        session,
        {
          action: "room.update",
          subjectType: "room",
          subjectId: input.roomId,
          after: updated,
        },
        tx
      );
    });

    revalidatePath(`/projects/${input.projectId}/building`);
    return { ok: true, message: "Room updated." };
  });
}
