-- 0002_identity
-- Organizations, users, roles, permissions, memberships.
-- Permissions are stored rather than hard-coded so the permission set is auditable.

create table organizations (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  slug        text not null unique,
  status      org_status not null default 'active',
  archived_at timestamptz,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
select attach_updated_at('organizations');

create table users (
  id            uuid primary key default gen_random_uuid(),
  email         text not null unique,
  name          text not null,
  -- Populated only if Supabase Auth is adopted; links this row to auth.users.
  -- Null when authentication is handled in-application. See docs/SCHEMA.md D-2.
  auth_user_id  uuid unique,
  status        user_status not null default 'invited',
  last_login_at timestamptz,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
select attach_updated_at('users');

create table roles (
  id          uuid primary key default gen_random_uuid(),
  code        text not null unique,
  name        text not null,
  description text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
select attach_updated_at('roles');

create table permissions (
  id          uuid primary key default gen_random_uuid(),
  code        text not null unique,
  description text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
select attach_updated_at('permissions');

create table role_permissions (
  role_id       uuid not null references roles(id) on delete cascade,
  permission_id uuid not null references permissions(id) on delete cascade,
  created_at    timestamptz not null default now(),
  primary key (role_id, permission_id)
);

create table memberships (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references users(id) on delete cascade,
  organization_id uuid not null references organizations(id) on delete cascade,
  role_id         uuid not null references roles(id),
  status          membership_status not null default 'active',
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  unique (user_id, organization_id)
);
select attach_updated_at('memberships');

create index idx_memberships_org  on memberships(organization_id);
create index idx_memberships_user on memberships(user_id);
