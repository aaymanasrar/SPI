-- 0004_documents
-- Document storage metadata, drawings, and the AI extraction staging area.
--
-- Originals are immutable (spec 14.2): re-uploading creates a new version and
-- links the old one via superseded_by_id. Nothing is overwritten.
--
-- extraction_proposals is the boundary enforced in ARCHITECTURE.md 4.1: AI
-- writes proposals, never authoritative rows. A human promotes a proposal.

create table documents (
  id               uuid primary key default gen_random_uuid(),
  organization_id  uuid not null references organizations(id) on delete cascade,
  -- Null for catalogue documents (datasheets, compliance certificates), which
  -- belong to a product model rather than a project.
  project_id       uuid references projects(id) on delete cascade,
  filename         text not null,
  content_type     text,
  byte_size        bigint,
  checksum_sha256  text,
  storage_key      text not null,
  classification   doc_classification not null default 'other',
  version          integer not null default 1,
  superseded_by_id uuid references documents(id) on delete set null,
  uploaded_by      uuid references users(id),
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);
select attach_updated_at('documents');
create index idx_documents_org     on documents(organization_id);
create index idx_documents_project on documents(project_id);
create index idx_documents_class   on documents(classification);

create table drawings (
  id           uuid primary key default gen_random_uuid(),
  document_id  uuid not null references documents(id) on delete cascade,
  discipline   text,
  sheet_number text,
  revision     text,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);
select attach_updated_at('drawings');
create index idx_drawings_document on drawings(document_id);

create table drawing_pages (
  id                 uuid primary key default gen_random_uuid(),
  drawing_id         uuid not null references drawings(id) on delete cascade,
  page_number        integer not null,
  render_storage_key text,
  width_px           integer,
  height_px          integer,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now(),
  unique (drawing_id, page_number)
);
select attach_updated_at('drawing_pages');
create index idx_drawing_pages_drawing on drawing_pages(drawing_id);

create table drawing_objects (
  id               uuid primary key default gen_random_uuid(),
  drawing_page_id  uuid not null references drawing_pages(id) on delete cascade,
  object_type      text not null,
  geometry         jsonb,
  extracted_value  jsonb,
  source           source_type   not null default 'ai_extracted',
  source_reference text,
  confidence       numeric(5,4) check (confidence is null or (confidence >= 0 and confidence <= 1)),
  review_status    review_status not null default 'pending',
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);
select attach_updated_at('drawing_objects');
create index idx_drawing_objects_page on drawing_objects(drawing_page_id);

-- Text chunks for retrieval. No embedding column yet — pgvector is added when
-- semantic search is actually needed (spec 8, "pgvector (when needed)").
create table document_chunks (
  id          uuid primary key default gen_random_uuid(),
  document_id uuid not null references documents(id) on delete cascade,
  page_number integer,
  ordinal     integer not null,
  text        text not null,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  unique (document_id, ordinal)
);
select attach_updated_at('document_chunks');
create index idx_document_chunks_document on document_chunks(document_id);

-- One row per AI call. Records provider, model and prompt version so any
-- extracted value can be traced to the exact run that produced it.
-- Append-only; the guard is added in 0010.
create table extraction_runs (
  id             uuid primary key default gen_random_uuid(),
  document_id    uuid references documents(id) on delete cascade,
  project_id     uuid references projects(id) on delete cascade,
  provider       text not null,
  model          text not null,
  prompt_version text not null,
  input_hash     text,
  status         extraction_status not null default 'queued',
  started_at     timestamptz,
  finished_at    timestamptz,
  raw_output     jsonb,
  error          text,
  cost_minor     bigint,
  currency       char(3),
  created_by     uuid references users(id),
  created_at     timestamptz not null default now()
);
create index idx_extraction_runs_document on extraction_runs(document_id);
create index idx_extraction_runs_project  on extraction_runs(project_id);

-- AI output lands here, never directly in an authoritative table.
-- target_table names the destination; target_id is null for a proposed insert
-- and set when proposing a change to an existing row.
create table extraction_proposals (
  id                uuid primary key default gen_random_uuid(),
  extraction_run_id uuid not null references extraction_runs(id) on delete cascade,
  target_table      text not null,
  target_id         uuid,
  proposed_data     jsonb not null,
  confidence        numeric(5,4) check (confidence is null or (confidence >= 0 and confidence <= 1)),
  status            proposal_status not null default 'pending',
  reviewed_by       uuid references users(id),
  reviewed_at       timestamptz,
  review_note       text,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);
select attach_updated_at('extraction_proposals');
create index idx_extraction_proposals_run    on extraction_proposals(extraction_run_id);
create index idx_extraction_proposals_status on extraction_proposals(status) where status = 'pending';
