import "server-only";
import { sql } from "@/lib/db";
import type { ReviewStatus } from "@/modules/building/repository";

/**
 * Read model for the project dashboard. Everything here is a count or a sum of
 * rows that already exist — the dashboard never estimates or fills gaps, so an
 * empty building model shows as empty rather than as plausible-looking numbers.
 *
 * Callers must have checked the project belongs to their organization
 * (getProject does this) before calling.
 */

export type DashboardRoom = {
  id: string;
  name: string;
  code: string | null;
  roomType: string | null;
  areaSqm: number | null;
  reviewStatus: ReviewStatus;
};

export type DashboardFloor = {
  id: string;
  buildingName: string;
  name: string;
  level: number;
  rooms: DashboardRoom[];
};

export type DashboardOperation = {
  id: string;
  engine: string;
  tool: string;
  status: string;
  createdAt: Date;
  durationMs: number | null;
};

export type ProjectDashboard = {
  floors: DashboardFloor[];
  doors: { total: number; fireRated: number; escape: number; pending: number };
  review: Record<ReviewStatus, number>;
  /** Cumulative room count per day the model was edited, oldest first. */
  roomGrowth: number[];
  operations: DashboardOperation[];
};

export async function getProjectDashboard(
  organizationId: string,
  projectId: string
): Promise<ProjectDashboard> {
  const [floorRows, doorRows, growthRows, operations] = await Promise.all([
    sql<
      {
        floorId: string;
        floorName: string;
        level: number;
        buildingName: string;
        roomId: string | null;
        roomName: string | null;
        code: string | null;
        roomType: string | null;
        areaSqm: number | null;
        reviewStatus: ReviewStatus | null;
      }[]
    >`
      select f.id as floor_id, f.name as floor_name, f.level,
             b.name as building_name,
             r.id as room_id, r.name as room_name, r.code, r.room_type,
             r.area_sqm::float8 as area_sqm, r.review_status::text as review_status
        from floors f
        join buildings b on b.id = f.building_id
        left join rooms r on r.floor_id = f.id
       where b.project_id = ${projectId}
       order by b.name, f.level desc, r.area_sqm desc nulls last, r.name`,
    sql<{ total: number; fireRated: number; escape: number; pending: number }[]>`
      select count(*)::int as total,
             count(*) filter (where nullif(trim(d.fire_rating), '') is not null)::int as fire_rated,
             count(*) filter (where d.is_escape_route)::int as escape,
             count(*) filter (where d.review_status = 'pending')::int as pending
        from doors d
        join floors f on f.id = d.floor_id
        join buildings b on b.id = f.building_id
       where b.project_id = ${projectId}`,
    sql<{ n: number }[]>`
      select count(*)::int as n
        from rooms r
        join floors f on f.id = r.floor_id
        join buildings b on b.id = f.building_id
       where b.project_id = ${projectId}
       group by date_trunc('day', r.created_at)
       order by date_trunc('day', r.created_at)`,
    sql<DashboardOperation[]>`
      select id, engine::text as engine, tool, status::text as status,
             created_at, duration_ms
        from craft_operations
       where organization_id = ${organizationId}
         and project_id = ${projectId}
       order by created_at desc
       limit 5`,
  ]);

  const floors: DashboardFloor[] = [];
  const review: Record<ReviewStatus, number> = {
    not_required: 0,
    pending: 0,
    approved: 0,
    rejected: 0,
  };
  for (const row of floorRows) {
    let floor = floors.at(-1);
    if (!floor || floor.id !== row.floorId) {
      floor = {
        id: row.floorId,
        buildingName: row.buildingName,
        name: row.floorName,
        level: row.level,
        rooms: [],
      };
      floors.push(floor);
    }
    if (row.roomId && row.roomName && row.reviewStatus) {
      floor.rooms.push({
        id: row.roomId,
        name: row.roomName,
        code: row.code,
        roomType: row.roomType,
        areaSqm: row.areaSqm,
        reviewStatus: row.reviewStatus,
      });
      review[row.reviewStatus] += 1;
    }
  }

  let running = 0;
  const roomGrowth = growthRows.map((r) => (running += r.n));

  return { floors, doors: doorRows[0], review, roomGrowth, operations };
}
