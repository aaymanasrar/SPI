import "server-only";
import type postgres from "postgres";
import { sql } from "@/lib/db";

/**
 * The canonical Building Intelligence Model (spec §9).
 *
 * One model per project, shared by every system. Fire Alarm, CCTV and ACS all
 * reference the same rooms and doors rather than each keeping their own copy —
 * that shared model is what makes cross-system coordination possible at all.
 *
 * Every object carries the §9.2 provenance block. In Prompt C everything is
 * entered by hand, so source is 'manual' and confidence is null. When drawing
 * extraction arrives it populates these same tables through
 * extraction_proposals, with source 'ai_extracted' and review_status 'pending'
 * — no schema change, and no route by which unreviewed AI output becomes
 * authoritative.
 */

export type ReviewStatus =
  | "not_required"
  | "pending"
  | "approved"
  | "rejected";

export type Building = {
  id: string;
  name: string;
  description: string | null;
  floorCount: number;
};

export type Floor = {
  id: string;
  buildingId: string;
  name: string;
  level: number;
  elevationM: string | null;
  roomCount: number;
  doorCount: number;
};

export type Room = {
  id: string;
  floorId: string;
  name: string;
  code: string | null;
  roomType: string | null;
  areaSqm: string | null;
  heightM: string | null;
  occupancy: number | null;
  source: string;
  sourceReference: string | null;
  confidence: string | null;
  reviewStatus: ReviewStatus;
};

export type Door = {
  id: string;
  floorId: string;
  code: string | null;
  doorType: string | null;
  widthMm: number | null;
  heightMm: number | null;
  fireRating: string | null;
  securityLevel: string | null;
  isEscapeRoute: boolean | null;
  roomAId: string | null;
  roomBId: string | null;
  roomAName: string | null;
  roomBName: string | null;
  source: string;
  reviewStatus: ReviewStatus;
};

/** Confirms a project belongs to the caller's organization. */
export async function assertProjectInOrg(
  organizationId: string,
  projectId: string,
  db: postgres.Sql | postgres.TransactionSql = sql
): Promise<boolean> {
  const rows = await db`
    select 1 from projects
     where id = ${projectId} and organization_id = ${organizationId}
  `;
  return rows.length > 0;
}

export async function listBuildings(
  organizationId: string,
  projectId: string
): Promise<Building[]> {
  return sql<Building[]>`
    select b.id, b.name, b.description,
           (select count(*) from floors f where f.building_id = b.id)::int as floor_count
      from buildings b
      join projects p on p.id = b.project_id
     where p.organization_id = ${organizationId}
       and b.project_id = ${projectId}
     order by b.name
  `;
}

export async function createBuilding(
  tx: postgres.TransactionSql,
  input: { projectId: string; name: string; description: string | null }
): Promise<Building> {
  const rows = await tx<Building[]>`
    insert into buildings (project_id, name, description)
    values (${input.projectId}, ${input.name}, ${input.description})
    returning id, name, description, 0::int as floor_count
  `;
  return rows[0];
}

export async function listFloors(
  organizationId: string,
  projectId: string
): Promise<Floor[]> {
  return sql<Floor[]>`
    select f.id, f.building_id, f.name, f.level, f.elevation_m,
           (select count(*) from rooms r where r.floor_id = f.id)::int as room_count,
           (select count(*) from doors d where d.floor_id = f.id)::int as door_count
      from floors f
      join buildings b on b.id = f.building_id
      join projects  p on p.id = b.project_id
     where p.organization_id = ${organizationId}
       and b.project_id = ${projectId}
     order by f.level
  `;
}

export async function createFloor(
  tx: postgres.TransactionSql,
  input: {
    buildingId: string;
    name: string;
    level: number;
    elevationM: number | null;
  }
): Promise<Floor> {
  const rows = await tx<Floor[]>`
    insert into floors (building_id, name, level, elevation_m)
    values (${input.buildingId}, ${input.name}, ${input.level}, ${input.elevationM})
    returning id, building_id, name, level, elevation_m,
              0::int as room_count, 0::int as door_count
  `;
  return rows[0];
}

export async function listRooms(
  organizationId: string,
  projectId: string,
  floorId?: string
): Promise<Room[]> {
  return sql<Room[]>`
    select r.id, r.floor_id, r.name, r.code, r.room_type, r.area_sqm,
           r.height_m, r.occupancy, r.source, r.source_reference,
           r.confidence, r.review_status
      from rooms r
      join floors f    on f.id = r.floor_id
      join buildings b on b.id = f.building_id
      join projects  p on p.id = b.project_id
     where p.organization_id = ${organizationId}
       and b.project_id = ${projectId}
       ${floorId ? sql`and r.floor_id = ${floorId}` : sql``}
     order by f.level, r.name
  `;
}

export async function createRoom(
  tx: postgres.TransactionSql,
  input: {
    floorId: string;
    name: string;
    code: string | null;
    roomType: string | null;
    areaSqm: number | null;
    heightM: number | null;
    occupancy: number | null;
    createdBy: string;
  }
): Promise<Room> {
  // Manually entered, so review_status is 'not_required' and confidence stays
  // null. Only AI-derived objects carry a confidence score.
  const rows = await tx<Room[]>`
    insert into rooms
      (floor_id, name, code, room_type, area_sqm, height_m, occupancy,
       source, review_status, created_by, updated_by)
    values (
      ${input.floorId}, ${input.name}, ${input.code}, ${input.roomType},
      ${input.areaSqm}, ${input.heightM}, ${input.occupancy},
      'manual', 'not_required', ${input.createdBy}, ${input.createdBy}
    )
    returning id, floor_id, name, code, room_type, area_sqm, height_m,
              occupancy, source, source_reference, confidence, review_status
  `;
  return rows[0];
}

export async function updateRoom(
  tx: postgres.TransactionSql,
  organizationId: string,
  roomId: string,
  patch: {
    name?: string;
    code?: string | null;
    roomType?: string | null;
    areaSqm?: number | null;
    heightM?: number | null;
    occupancy?: number | null;
    updatedBy: string;
  }
): Promise<Room | null> {
  const rows = await tx<Room[]>`
    update rooms r set
      name       = coalesce(${patch.name ?? null}, r.name),
      code       = ${patch.code !== undefined ? patch.code : sql`r.code`},
      room_type  = ${patch.roomType !== undefined ? patch.roomType : sql`r.room_type`},
      area_sqm   = ${patch.areaSqm !== undefined ? patch.areaSqm : sql`r.area_sqm`},
      height_m   = ${patch.heightM !== undefined ? patch.heightM : sql`r.height_m`},
      occupancy  = ${patch.occupancy !== undefined ? patch.occupancy : sql`r.occupancy`},
      updated_by = ${patch.updatedBy}
    from floors f
    join buildings b on b.id = f.building_id
    join projects  p on p.id = b.project_id
    where r.floor_id = f.id
      and r.id = ${roomId}
      and p.organization_id = ${organizationId}
    returning r.id, r.floor_id, r.name, r.code, r.room_type, r.area_sqm,
              r.height_m, r.occupancy, r.source, r.source_reference,
              r.confidence, r.review_status
  `;
  return rows[0] ?? null;
}

export async function listDoors(
  organizationId: string,
  projectId: string,
  floorId?: string
): Promise<Door[]> {
  return sql<Door[]>`
    select d.id, d.floor_id, d.code, d.door_type, d.width_mm, d.height_mm,
           d.fire_rating, d.security_level, d.is_escape_route,
           d.room_a_id, d.room_b_id,
           ra.name as room_a_name, rb.name as room_b_name,
           d.source, d.review_status
      from doors d
      join floors f    on f.id = d.floor_id
      join buildings b on b.id = f.building_id
      join projects  p on p.id = b.project_id
      left join rooms ra on ra.id = d.room_a_id
      left join rooms rb on rb.id = d.room_b_id
     where p.organization_id = ${organizationId}
       and b.project_id = ${projectId}
       ${floorId ? sql`and d.floor_id = ${floorId}` : sql``}
     order by f.level, d.code nulls last
  `;
}

/**
 * Doors matter disproportionately: they are where Access Control, Fire Alarm
 * and life-safety requirements meet on the same physical object (spec §15.1).
 * Both room references are nullable because an external door has one side.
 */
export async function createDoor(
  tx: postgres.TransactionSql,
  input: {
    floorId: string;
    code: string | null;
    doorType: string | null;
    widthMm: number | null;
    heightMm: number | null;
    fireRating: string | null;
    securityLevel: string | null;
    isEscapeRoute: boolean | null;
    roomAId: string | null;
    roomBId: string | null;
    createdBy: string;
  }
): Promise<{ id: string }> {
  const rows = await tx<{ id: string }[]>`
    insert into doors
      (floor_id, code, door_type, width_mm, height_mm, fire_rating,
       security_level, is_escape_route, room_a_id, room_b_id,
       source, review_status, created_by, updated_by)
    values (
      ${input.floorId}, ${input.code}, ${input.doorType}, ${input.widthMm},
      ${input.heightMm}, ${input.fireRating}, ${input.securityLevel},
      ${input.isEscapeRoute}, ${input.roomAId}, ${input.roomBId},
      'manual', 'not_required', ${input.createdBy}, ${input.createdBy}
    )
    returning id
  `;
  return rows[0];
}

/** Floors belonging to a project, for populating selects. */
export async function floorOptions(
  organizationId: string,
  projectId: string
): Promise<{ id: string; label: string }[]> {
  return sql<{ id: string; label: string }[]>`
    select f.id, b.name || ' — ' || f.name as label
      from floors f
      join buildings b on b.id = f.building_id
      join projects  p on p.id = b.project_id
     where p.organization_id = ${organizationId}
       and b.project_id = ${projectId}
     order by b.name, f.level
  `;
}
