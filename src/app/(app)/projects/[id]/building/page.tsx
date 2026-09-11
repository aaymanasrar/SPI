import Link from "next/link";
import { notFound } from "next/navigation";
import { requireSession } from "@/lib/auth";
import { can } from "@/lib/rbac";
import { getProject } from "@/modules/projects/repository";
import {
  listBuildings,
  listFloors,
  listRooms,
  listDoors,
  floorOptions,
} from "@/modules/building/repository";
import {
  createBuildingAction,
  createFloorAction,
  createRoomAction,
  createDoorAction,
} from "@/modules/building/actions";
import { ActionForm } from "@/components/action-form";
import {
  Card,
  Field,
  Select,
  Table,
  Pill,
  Empty,
  NoPermission,
} from "@/components/ui";

export default async function BuildingModelPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const session = await requireSession();

  const project = await getProject(session.organizationId, id);
  if (!project) notFound();

  const [buildings, floors, rooms, doors, floorRows, mayEdit] =
    await Promise.all([
      listBuildings(session.organizationId, id),
      listFloors(session.organizationId, id),
      listRooms(session.organizationId, id),
      listDoors(session.organizationId, id),
      floorOptions(session.organizationId, id),
      can("building_model.edit"),
    ]);

  const floorOpts = floorRows.map((f) => ({ value: f.id, label: f.label }));
  const roomOpts = rooms.map((r) => ({ value: r.id, label: r.name }));

  return (
    <div className="space-y-6">
      <div>
        <Link
          href={`/projects/${id}`}
          className="text-xs text-slate-500 hover:underline dark:text-slate-400"
        >
          ← {project.name}
        </Link>
        <h1 className="mt-1 text-xl font-semibold text-slate-900 dark:text-slate-100">
          Building model
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          One canonical model per project. Fire Alarm, CCTV and Access Control
          all reference these same rooms and doors.
        </p>
      </div>

      {/* Buildings and floors */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title={`Buildings (${buildings.length})`}>
          {buildings.length === 0 ? (
            <Empty>No buildings yet. Add one to begin.</Empty>
          ) : (
            <Table head={["Name", "Description", "Floors"]}>
              {buildings.map((b) => (
                <tr key={b.id}>
                  <td className="px-2 py-2 font-medium">{b.name}</td>
                  <td className="px-2 py-2 text-slate-600 dark:text-slate-400">
                    {b.description ?? "—"}
                  </td>
                  <td className="px-2 py-2 tabular-nums">{b.floorCount}</td>
                </tr>
              ))}
            </Table>
          )}
          {mayEdit && (
            <div className="mt-4 border-t border-slate-200 pt-4 dark:border-slate-800">
              <ActionForm
                action={createBuildingAction}
                submitLabel="Add building"
                resetOnSuccess
              >
                <input type="hidden" name="projectId" value={id} />
                <Field label="Building name" name="name" required />
                <Field label="Description" name="description" />
              </ActionForm>
            </div>
          )}
        </Card>

        <Card title={`Floors (${floors.length})`}>
          {floors.length === 0 ? (
            <Empty>No floors yet.</Empty>
          ) : (
            <Table head={["Floor", "Level", "Rooms", "Doors"]}>
              {floors.map((f) => (
                <tr key={f.id}>
                  <td className="px-2 py-2 font-medium">{f.name}</td>
                  <td className="px-2 py-2 tabular-nums">{f.level}</td>
                  <td className="px-2 py-2 tabular-nums">{f.roomCount}</td>
                  <td className="px-2 py-2 tabular-nums">{f.doorCount}</td>
                </tr>
              ))}
            </Table>
          )}
          {mayEdit && buildings.length > 0 && (
            <div className="mt-4 border-t border-slate-200 pt-4 dark:border-slate-800">
              <ActionForm
                action={createFloorAction}
                submitLabel="Add floor"
                resetOnSuccess
              >
                <input type="hidden" name="projectId" value={id} />
                <Select
                  label="Building"
                  name="buildingId"
                  options={buildings.map((b) => ({
                    value: b.id,
                    label: b.name,
                  }))}
                />
                <div className="grid gap-3 sm:grid-cols-3">
                  <Field label="Floor name" name="name" required />
                  <Field
                    label="Level"
                    name="level"
                    type="number"
                    required
                    defaultValue={0}
                    hint="0 = ground"
                  />
                  <Field
                    label="Elevation (m)"
                    name="elevationM"
                    type="number"
                    step="0.001"
                  />
                </div>
              </ActionForm>
            </div>
          )}
        </Card>
      </div>

      {/* Rooms */}
      <Card
        title={`Rooms (${rooms.length})`}
        description="Area, height and occupancy are engineering inputs. Leave a field blank rather than estimating it — unknown is a supported state, a wrong number is not."
      >
        {rooms.length === 0 ? (
          <Empty>No rooms yet.</Empty>
        ) : (
          <Table
            head={[
              "Room",
              "Code",
              "Type",
              "Area m²",
              "Height m",
              "Occupancy",
              "Source",
              "Review",
            ]}
          >
            {rooms.map((r) => (
              <tr key={r.id}>
                <td className="px-2 py-2 font-medium">{r.name}</td>
                <td className="px-2 py-2 text-slate-500">{r.code ?? "—"}</td>
                <td className="px-2 py-2 text-slate-600 dark:text-slate-400">
                  {r.roomType ?? "—"}
                </td>
                <td className="px-2 py-2 tabular-nums">{r.areaSqm ?? "—"}</td>
                <td className="px-2 py-2 tabular-nums">{r.heightM ?? "—"}</td>
                <td className="px-2 py-2 tabular-nums">{r.occupancy ?? "—"}</td>
                <td className="px-2 py-2 text-xs text-slate-500">{r.source}</td>
                <td className="px-2 py-2">
                  <Pill value={r.reviewStatus} />
                </td>
              </tr>
            ))}
          </Table>
        )}

        {mayEdit ? (
          floorOpts.length > 0 && (
            <div className="mt-4 border-t border-slate-200 pt-4 dark:border-slate-800">
              <ActionForm
                action={createRoomAction}
                submitLabel="Add room"
                resetOnSuccess
              >
                <input type="hidden" name="projectId" value={id} />
                <Select label="Floor" name="floorId" options={floorOpts} />
                <div className="grid gap-3 sm:grid-cols-3">
                  <Field label="Room name" name="name" required />
                  <Field label="Room code" name="code" />
                  <Field
                    label="Room type"
                    name="roomType"
                    placeholder="e.g. office, corridor"
                  />
                  <Field label="Area (m²)" name="areaSqm" type="number" step="0.001" />
                  <Field label="Height (m)" name="heightM" type="number" step="0.001" />
                  <Field label="Occupancy" name="occupancy" type="number" />
                </div>
              </ActionForm>
            </div>
          )
        ) : (
          <div className="mt-4">
            <NoPermission what="editing the building model" />
          </div>
        )}
      </Card>

      {/* Doors */}
      <Card
        title={`Doors (${doors.length})`}
        description="Doors are where Access Control, Fire Alarm and life-safety requirements meet on one physical object, so they are modelled once and shared."
      >
        {doors.length === 0 ? (
          <Empty>No doors yet.</Empty>
        ) : (
          <Table
            head={[
              "Code",
              "Type",
              "Connects",
              "Width mm",
              "Fire rating",
              "Security",
              "Escape",
              "Review",
            ]}
          >
            {doors.map((d) => (
              <tr key={d.id}>
                <td className="px-2 py-2 font-medium">{d.code ?? "—"}</td>
                <td className="px-2 py-2 text-slate-600 dark:text-slate-400">
                  {d.doorType ?? "—"}
                </td>
                <td className="px-2 py-2 text-xs text-slate-600 dark:text-slate-400">
                  {d.roomAName ?? "external"} → {d.roomBName ?? "external"}
                </td>
                <td className="px-2 py-2 tabular-nums">{d.widthMm ?? "—"}</td>
                <td className="px-2 py-2">{d.fireRating ?? "—"}</td>
                <td className="px-2 py-2">{d.securityLevel ?? "—"}</td>
                <td className="px-2 py-2">{d.isEscapeRoute ? "yes" : "—"}</td>
                <td className="px-2 py-2">
                  <Pill value={d.reviewStatus} />
                </td>
              </tr>
            ))}
          </Table>
        )}

        {mayEdit && floorOpts.length > 0 && (
          <div className="mt-4 border-t border-slate-200 pt-4 dark:border-slate-800">
            <ActionForm
              action={createDoorAction}
              submitLabel="Add door"
              resetOnSuccess
            >
              <input type="hidden" name="projectId" value={id} />
              <Select label="Floor" name="floorId" options={floorOpts} />
              <div className="grid gap-3 sm:grid-cols-3">
                <Field label="Door code" name="code" placeholder="e.g. D-101" />
                <Field label="Door type" name="doorType" placeholder="e.g. single leaf" />
                <Field label="Width (mm)" name="widthMm" type="number" />
                <Select
                  label="Room A"
                  name="roomAId"
                  includeBlank="External"
                  options={roomOpts}
                />
                <Select
                  label="Room B"
                  name="roomBId"
                  includeBlank="External"
                  options={roomOpts}
                />
                <Field label="Fire rating" name="fireRating" placeholder="e.g. 60 min" />
                <Field label="Security level" name="securityLevel" />
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  name="isEscapeRoute"
                  className="h-4 w-4 rounded border-slate-300 text-teal-700 focus:ring-teal-600"
                />
                <span className="text-slate-800 dark:text-slate-200">
                  On an escape route
                </span>
              </label>
            </ActionForm>
          </div>
        )}
      </Card>
    </div>
  );
}
