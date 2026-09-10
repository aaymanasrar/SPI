-- 0003_projects_and_building_model
-- Clients, projects, and the canonical Building Intelligence Model (spec 9).
-- One building model per project, shared by every system.

create table clients (
  id              uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  name            text not null,
  contact_name    text,
  contact_email   text,
  contact_phone   text,
  archived_at     timestamptz,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);
select attach_updated_at('clients');
create index idx_clients_org on clients(organization_id);

create table projects (
  id              uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  client_id       uuid references clients(id) on delete set null,
  name            text not null,
  code            text,
  -- Flat text for now. A hierarchy can be introduced later without breaking
  -- existing rows; see docs/SCHEMA.md D-6.
  jurisdiction    text,
  status          project_status not null default 'draft',
  created_by      uuid references users(id),
  archived_at     timestamptz,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  unique (organization_id, code)
);
select attach_updated_at('projects');
create index idx_projects_org    on projects(organization_id);
create index idx_projects_client on projects(client_id);

create table buildings (
  id          uuid primary key default gen_random_uuid(),
  project_id  uuid not null references projects(id) on delete cascade,
  name        text not null,
  description text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
select attach_updated_at('buildings');
create index idx_buildings_project on buildings(project_id);

create table floors (
  id          uuid primary key default gen_random_uuid(),
  building_id uuid not null references buildings(id) on delete cascade,
  name        text not null,
  level       integer not null,
  elevation_m numeric(10,3),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  unique (building_id, level)
);
select attach_updated_at('floors');
create index idx_floors_building on floors(building_id);

-- ---------------------------------------------------------------------------
-- Building-model objects.
--
-- Each carries the spec 9.2 provenance block:
--   source / source_reference / confidence / review_status / created_by / updated_by
--
-- review_status is what gates authority. An object still 'pending' must not be
-- consumed by an approved BOQ. confidence is null for manually entered data —
-- only AI-derived values carry one.
-- ---------------------------------------------------------------------------

create table rooms (
  id               uuid primary key default gen_random_uuid(),
  floor_id         uuid not null references floors(id) on delete cascade,
  name             text not null,
  code             text,
  room_type        text,
  area_sqm         numeric(12,3),
  height_m         numeric(10,3),
  occupancy        integer,
  source           source_type   not null default 'manual',
  source_reference text,
  confidence       numeric(5,4) check (confidence is null or (confidence >= 0 and confidence <= 1)),
  review_status    review_status not null default 'not_required',
  created_by       uuid references users(id),
  updated_by       uuid references users(id),
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);
select attach_updated_at('rooms');
create index idx_rooms_floor  on rooms(floor_id);
create index idx_rooms_review on rooms(review_status) where review_status = 'pending';

create table areas (
  id               uuid primary key default gen_random_uuid(),
  floor_id         uuid not null references floors(id) on delete cascade,
  name             text not null,
  area_type        text,
  geometry         jsonb,
  source           source_type   not null default 'manual',
  source_reference text,
  confidence       numeric(5,4) check (confidence is null or (confidence >= 0 and confidence <= 1)),
  review_status    review_status not null default 'not_required',
  created_by       uuid references users(id),
  updated_by       uuid references users(id),
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);
select attach_updated_at('areas');
create index idx_areas_floor on areas(floor_id);

create table walls (
  id               uuid primary key default gen_random_uuid(),
  floor_id         uuid not null references floors(id) on delete cascade,
  wall_type        text,
  fire_rating      text,
  geometry         jsonb,
  source           source_type   not null default 'manual',
  source_reference text,
  confidence       numeric(5,4) check (confidence is null or (confidence >= 0 and confidence <= 1)),
  review_status    review_status not null default 'not_required',
  created_by       uuid references users(id),
  updated_by       uuid references users(id),
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);
select attach_updated_at('walls');
create index idx_walls_floor on walls(floor_id);

create table openings (
  id           uuid primary key default gen_random_uuid(),
  wall_id      uuid not null references walls(id) on delete cascade,
  opening_type text,
  geometry     jsonb,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);
select attach_updated_at('openings');
create index idx_openings_wall on openings(wall_id);

-- Both room references are nullable: an external door has only one side.
create table doors (
  id               uuid primary key default gen_random_uuid(),
  floor_id         uuid not null references floors(id) on delete cascade,
  room_a_id        uuid references rooms(id) on delete set null,
  room_b_id        uuid references rooms(id) on delete set null,
  code             text,
  door_type        text,
  width_mm         integer,
  height_mm        integer,
  fire_rating      text,
  security_level   text,
  is_escape_route  boolean,
  source           source_type   not null default 'manual',
  source_reference text,
  confidence       numeric(5,4) check (confidence is null or (confidence >= 0 and confidence <= 1)),
  review_status    review_status not null default 'not_required',
  created_by       uuid references users(id),
  updated_by       uuid references users(id),
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);
select attach_updated_at('doors');
create index idx_doors_floor  on doors(floor_id);
create index idx_doors_room_a on doors(room_a_id);
create index idx_doors_room_b on doors(room_b_id);

create table zones (
  id         uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  system_id  uuid,  -- FK added in 0005 once systems exists
  name       text not null,
  purpose    text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
select attach_updated_at('zones');
create index idx_zones_project on zones(project_id);
