-- 0023_craft_operations
--
-- The operation log for the craft engines (GridCraft, WordCraft, CADCraft,
-- PDFCraft) -- headless tools that read and write the files engineers actually
-- work in: .xlsx, .docx, .dxf, .pdf.
--
-- Every tool call records one row here. The row is the answer to "where did this
-- file come from?", the same question rule_executions answers for a quantity.
--
-- WHAT THIS MIGRATION DELIBERATELY DOES NOT DO:
--   * It does not add craft tables for rooms, devices or quantities. CAD output
--     lands in drawing_objects with source='imported' and review_status='pending',
--     reusing the review surface that already exists. Promotion to rooms /
--     design_devices stays with building_model.review.
--   * It does not touch extraction_proposals. A deterministic ezdxf parse is not
--     an inference, and extraction_runs.provider/model/prompt_version are NOT NULL
--     columns describing an LLM call. Proposals are reserved for genuinely
--     inferred values (phase 2, e.g. fuzzy symbol matching).
--   * It adds no RLS *policy*. Like 0011, it enables RLS with no policy, which
--     denies PostgREST and leaves the server-side connection untouched.
--
-- Two shapes worth naming:
--   * input_document_ids / output_document_ids are uuid[]. An array column cannot
--     carry a foreign key, so referential integrity there is by convention. That is
--     acceptable in an append-only log whose job is to record what happened, and
--     the alternative (a join table) buys nothing a log needs.
--   * missing_json is the ARCHITECTURE.md 4.2 `unknowns` channel under the name the
--     tool contract uses. A non-empty missing_json with status='missing_data' is a
--     NORMAL outcome, not a failure: it is the engine refusing to invent a value.

create type craft_engine     as enum ('grid','word','cad','pdf');
create type craft_actor_type as enum ('ai','user','system');
create type craft_mode       as enum ('preview','commit');
create type craft_status     as enum ('ok','missing_data','invalid_input','error');

comment on type craft_engine is
  'Which craft engine ran. grid=xlsx, word=docx/pdf, cad=dxf, pdf=pdf.';
comment on type craft_actor_type is
  'Who initiated. ai=the orchestrator (preview only), user=a person, system=a job.';
comment on type craft_mode is
  'preview reads and computes but writes no file and no authoritative row. '
  'commit writes. The AI may call preview; commit needs a user with craft.commit.';
comment on type craft_status is
  'ok | missing_data (a required value was not captured -- never guessed) | '
  'invalid_input (caller error) | error (the engine failed).';

create table craft_operations (
  id                  uuid primary key default gen_random_uuid(),
  organization_id     uuid not null references organizations(id) on delete cascade,
  -- Null for catalogue-only work (a datasheet pack with no project), mirroring
  -- documents.project_id, which is nullable for the same reason.
  project_id          uuid references projects(id) on delete cascade,
  engine              craft_engine not null,
  tool                text not null,
  actor_type          craft_actor_type not null,
  actor_id            uuid references users(id),
  mode                craft_mode not null,
  input_json          jsonb not null default '{}'::jsonb,
  output_json         jsonb,
  input_document_ids  uuid[] not null default '{}',
  output_document_ids uuid[] not null default '{}',
  provenance_json     jsonb not null default '[]'::jsonb,
  missing_json        jsonb not null default '[]'::jsonb,
  warnings_json       jsonb not null default '[]'::jsonb,
  status              craft_status not null,
  error               text,
  duration_ms         integer,
  engine_version      text not null,
  created_at          timestamptz not null default now(),
  constraint craft_operations_error_iff_failed
    check ((status = 'error') = (error is not null)),
  -- A preview that produced a file is a contradiction in terms.
  constraint craft_operations_preview_writes_nothing
    check (mode <> 'preview' or cardinality(output_document_ids) = 0),
  -- missing_data must say what was missing, or it is just a failure with a nicer name.
  constraint craft_operations_missing_is_itemised
    check (status <> 'missing_data' or jsonb_array_length(missing_json) > 0)
);

-- Append-only: no updated_at, no attach_updated_at. A tool run either happened or
-- it did not; it is never edited afterwards.
select attach_append_only('craft_operations');

create index idx_craft_operations_project on craft_operations(project_id);
create index idx_craft_operations_tool    on craft_operations(organization_id, tool);
create index idx_craft_operations_failed  on craft_operations(organization_id, created_at desc)
  where status <> 'ok';

comment on table craft_operations is
  'One row per craft engine tool call. Append-only. The provenance record for every '
  'file the system produces.';
comment on column craft_operations.missing_json is
  'Values the tool needed and could not find. Non-empty is a normal outcome.';
comment on column craft_operations.engine_version is
  'Version of the engines package that ran, so an old output can be reproduced.';

-- ---------------------------------------------------------------------------
-- Output files are new document versions that point back at the run
-- ---------------------------------------------------------------------------
-- An original upload is never modified (ARCHITECTURE.md 7). A craft output is a
-- new documents row; this column says which run produced it.
alter table documents
  add column if not exists source_operation_id uuid
    references craft_operations(id) on delete set null;

comment on column documents.source_operation_id is
  'The craft_operations run that generated this file. Null for human uploads.';

create index if not exists idx_documents_source_operation
  on documents(source_operation_id) where source_operation_id is not null;

-- ---------------------------------------------------------------------------
-- Permissions
-- ---------------------------------------------------------------------------
-- Two, not one. A preview is read-only and the AI orchestrator may call it; a
-- commit writes a file and an authoritative row and needs a person. Collapsing
-- them would make those two indistinguishable to RBAC.

insert into permissions (code, description) values
  ('craft.preview', 'Run a craft engine tool in preview mode (reads and computes, writes nothing)'),
  ('craft.commit',  'Run a craft engine tool that writes files and records')
on conflict (code) do nothing;

insert into role_permissions (role_id, permission_id)
select r.id, p.id from roles r join permissions p on p.code in ('craft.preview','craft.commit')
where r.code in ('engineering_manager','pre_sales_engineer')
on conflict do nothing;

-- Estimators preview (they read BOQ workbooks) but do not commit.
insert into role_permissions (role_id, permission_id)
select r.id, p.id from roles r join permissions p on p.code = 'craft.preview'
where r.code = 'estimator'
on conflict do nothing;

-- ---------------------------------------------------------------------------
-- RLS -- including a fix for two tables that predate this work
-- ---------------------------------------------------------------------------
-- 0011 enables RLS by looping over pg_tables ONCE, at migration time. It is not
-- an event trigger, so any table created afterwards is NOT covered. Two were:
-- rule_relationships and rule_precedence_policy, both added in 0017. Both have
-- been reachable with the publishable key since. Fixed here with the craft table.
--
-- The lesson generalises: every migration that creates a table must enable RLS
-- itself. There is no default.

alter table public.craft_operations       enable row level security;
alter table public.rule_relationships     enable row level security;
alter table public.rule_precedence_policy enable row level security;
