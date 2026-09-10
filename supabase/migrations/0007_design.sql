-- 0007_design
-- Design output: devices, connections, cable routes and cross-system interfaces.
--
-- Design modules do not compute quantities themselves. They assemble inputs,
-- call the rules engine, and record results with a rule_execution_id
-- (ARCHITECTURE.md 4.1). A device whose existence came from a rule carries that
-- reference; one placed by hand records the user instead.

create table design_devices (
  id                uuid primary key default gen_random_uuid(),
  project_id        uuid not null references projects(id) on delete cascade,
  system_id         uuid not null references systems(id),
  device_type       text not null,
  room_id           uuid references rooms(id) on delete set null,
  floor_id          uuid references floors(id) on delete set null,
  door_id           uuid references doors(id) on delete set null,
  zone_id           uuid references zones(id) on delete set null,
  location          jsonb,
  quantity          numeric(14,3) not null default 1,
  rule_execution_id uuid references rule_executions(id),
  product_model_id  uuid references product_models(id),
  source            source_type   not null default 'manual',
  source_reference  text,
  confidence        numeric(5,4) check (confidence is null or (confidence >= 0 and confidence <= 1)),
  review_status     review_status not null default 'not_required',
  created_by        uuid references users(id),
  updated_by        uuid references users(id),
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  constraint design_devices_quantity_positive check (quantity > 0)
);
select attach_updated_at('design_devices');
create index idx_design_devices_project on design_devices(project_id);
create index idx_design_devices_system  on design_devices(system_id);
create index idx_design_devices_room    on design_devices(room_id);
create index idx_design_devices_door    on design_devices(door_id);

create table device_connections (
  id              uuid primary key default gen_random_uuid(),
  from_device_id  uuid not null references design_devices(id) on delete cascade,
  to_device_id    uuid not null references design_devices(id) on delete cascade,
  connection_type text,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  constraint device_connections_not_self check (from_device_id <> to_device_id)
);
select attach_updated_at('device_connections');
create index idx_device_connections_from on device_connections(from_device_id);
create index idx_device_connections_to   on device_connections(to_device_id);

-- Spec 16.3 requires every cable/route to have a calculation or a manual
-- quantity. length_basis makes which one explicit, and 'unknown' is a
-- first-class state — a length is never silently inferred.
-- The engineering decision on how lengths are derived is still open
-- (docs/SCHEMA.md D-5).
create table cable_routes (
  id                    uuid primary key default gen_random_uuid(),
  project_id            uuid not null references projects(id) on delete cascade,
  system_id             uuid not null references systems(id),
  from_device_id        uuid references design_devices(id) on delete set null,
  to_device_id          uuid references design_devices(id) on delete set null,
  cable_type            text,
  length_basis          length_basis not null default 'unknown',
  length_m              numeric(14,3),
  calculation_reference text,
  rule_execution_id     uuid references rule_executions(id),
  created_by            uuid references users(id),
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now(),
  -- A length may only be present once its basis is stated.
  constraint cable_routes_length_requires_basis check (
    (length_basis = 'unknown' and length_m is null)
    or (length_basis <> 'unknown' and length_m is not null and length_m >= 0)
  )
);
select attach_updated_at('cable_routes');
create index idx_cable_routes_project on cable_routes(project_id);

-- Spec 15.2: the system must distinguish a proposed integration from an
-- approved one and from an implemented one.
create table system_interfaces (
  id          uuid primary key default gen_random_uuid(),
  project_id  uuid not null references projects(id) on delete cascade,
  system_a_id uuid not null references systems(id),
  system_b_id uuid not null references systems(id),
  event       text not null,
  action      text not null,
  status      interface_status not null default 'proposed',
  approved_by uuid references users(id),
  approved_at timestamptz,
  notes       text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  constraint system_interfaces_distinct check (system_a_id <> system_b_id)
);
select attach_updated_at('system_interfaces');
create index idx_system_interfaces_project on system_interfaces(project_id);
