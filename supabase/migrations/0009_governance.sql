-- 0009_governance
-- Validation results (spec 23), review tasks, approvals and audit log (spec 22).
--
-- approvals and audit_logs are append-only; the guards are added in 0010.

create table validation_results (
  id           uuid primary key default gen_random_uuid(),
  project_id   uuid not null references projects(id) on delete cascade,
  layer        validation_layer not null,
  severity     validation_severity not null,
  code         text not null,
  message      text not null,
  subject_type text,
  subject_id   uuid,
  detail       jsonb,
  resolved_at  timestamptz,
  resolved_by  uuid references users(id),
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);
select attach_updated_at('validation_results');
create index idx_validation_results_project on validation_results(project_id);

-- Open ERRORs are what block finalization, so they are indexed for the check
-- that runs on every transition toward approved/issued.
create index idx_validation_results_blocking on validation_results(project_id)
  where severity = 'error' and resolved_at is null;

create table review_tasks (
  id           uuid primary key default gen_random_uuid(),
  project_id   uuid not null references projects(id) on delete cascade,
  kind         text not null,
  subject_type text,
  subject_id   uuid,
  assigned_role_id uuid references roles(id),
  assigned_to  uuid references users(id),
  status       review_task_status not null default 'open',
  note         text,
  resolved_by  uuid references users(id),
  resolved_at  timestamptz,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);
select attach_updated_at('review_tasks');
create index idx_review_tasks_project on review_tasks(project_id);
create index idx_review_tasks_open    on review_tasks(project_id) where status = 'open';

-- Append-only. Every approval-state transition writes one of these.
create table approvals (
  id              uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  subject_type    text not null,
  subject_id      uuid not null,
  from_status     text,
  to_status       text not null,
  role_id         uuid references roles(id),
  approved_by     uuid not null references users(id),
  approved_at     timestamptz not null default now(),
  signature_note  text
);
create index idx_approvals_subject on approvals(subject_type, subject_id);
create index idx_approvals_org     on approvals(organization_id);

-- Append-only. Actor, action, subject and before/after for every significant
-- mutation (spec 22).
create table audit_logs (
  id              uuid primary key default gen_random_uuid(),
  organization_id uuid references organizations(id) on delete set null,
  actor_id        uuid references users(id),
  action          text not null,
  subject_type    text,
  subject_id      uuid,
  before          jsonb,
  after           jsonb,
  ip              inet,
  at              timestamptz not null default now()
);
create index idx_audit_logs_org     on audit_logs(organization_id);
create index idx_audit_logs_subject on audit_logs(subject_type, subject_id);
create index idx_audit_logs_at      on audit_logs(at desc);
