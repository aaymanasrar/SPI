-- 0005_systems_and_rules
-- Systems reference data, project system selection, and the engineering rules
-- engine (spec 11).
--
-- Rules are versioned data with an approval lifecycle, not code and not prompts.
-- This migration creates the framework only. It contains no rules: rule content
-- is SmartPage engineering data (Appendix A) and must never be invented.
--
-- conditions / inputs / calculation / outputs / exceptions are opaque versioned
-- JSONB payloads evaluated by a pluggable evaluator. The expression language is
-- deliberately deferred until real SmartPage rules exist — see ARCHITECTURE.md 9.4.

create table systems (
  id         uuid primary key default gen_random_uuid(),
  code       text not null unique,
  name       text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
select attach_updated_at('systems');

alter table zones
  add constraint zones_system_id_fkey
  foreign key (system_id) references systems(id) on delete set null;

create table project_systems (
  id         uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  system_id  uuid not null references systems(id),
  status     project_system_status not null default 'selected',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (project_id, system_id)
);
select attach_updated_at('project_systems');
create index idx_project_systems_project on project_systems(project_id);

create table system_requirements (
  id                uuid primary key default gen_random_uuid(),
  project_system_id uuid not null references project_systems(id) on delete cascade,
  key               text not null,
  value             jsonb not null,
  source            source_type not null default 'manual',
  source_reference  text,
  created_by        uuid references users(id),
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  unique (project_system_id, key)
);
select attach_updated_at('system_requirements');

-- Rule identity and ownership. Content lives in rule_versions.
create table engineering_rules (
  id                 uuid primary key default gen_random_uuid(),
  organization_id    uuid not null references organizations(id) on delete cascade,
  system_id          uuid not null references systems(id),
  rule_code          text not null,
  name               text not null,
  jurisdiction       text,
  standard_reference text,
  priority           integer not null default 100,
  owner_user_id      uuid references users(id),
  archived_at        timestamptz,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now(),
  unique (organization_id, rule_code)
);
select attach_updated_at('engineering_rules');
create index idx_engineering_rules_system on engineering_rules(system_id);

-- Versioned rule content. Frozen once approved (see 0010): a change to an
-- approved rule requires a new version, never an edit in place.
create table rule_versions (
  id              uuid primary key default gen_random_uuid(),
  rule_id         uuid not null references engineering_rules(id) on delete cascade,
  version         integer not null,
  conditions      jsonb not null default '{}'::jsonb,
  inputs          jsonb not null default '{}'::jsonb,
  calculation     jsonb not null default '{}'::jsonb,
  outputs         jsonb not null default '{}'::jsonb,
  exceptions      jsonb not null default '{}'::jsonb,
  effective_from  date,
  effective_to    date,
  approval_status rule_approval_status not null default 'draft',
  approved_by     uuid references users(id),
  approved_at     timestamptz,
  created_by      uuid references users(id),
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  unique (rule_id, version),
  constraint rule_versions_effective_range check (
    effective_to is null or effective_from is null or effective_to >= effective_from)
);
select attach_updated_at('rule_versions');
create index idx_rule_versions_rule   on rule_versions(rule_id);
create index idx_rule_versions_active on rule_versions(approval_status)
  where approval_status = 'active';

-- Test cases (spec 11.1). A rule version must pass its own tests before it can
-- reach 'approved' — enforced in the rules service, recorded here.
create table rule_tests (
  id               uuid primary key default gen_random_uuid(),
  rule_version_id  uuid not null references rule_versions(id) on delete cascade,
  name             text not null,
  given_inputs     jsonb not null,
  expected_outputs jsonb not null,
  last_result      rule_test_result not null default 'not_run',
  last_run_at      timestamptz,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);
select attach_updated_at('rule_tests');
create index idx_rule_tests_version on rule_tests(rule_version_id);

-- The audit trail that makes a quantity traceable. Append-only (guard in 0010).
create table rule_executions (
  id              uuid primary key default gen_random_uuid(),
  project_id      uuid not null references projects(id) on delete cascade,
  rule_version_id uuid not null references rule_versions(id),
  inputs          jsonb not null,
  outputs         jsonb not null,
  evidence        jsonb,
  executed_by     uuid references users(id),
  executed_at     timestamptz not null default now()
);
create index idx_rule_executions_project on rule_executions(project_id);
create index idx_rule_executions_version on rule_executions(rule_version_id);
