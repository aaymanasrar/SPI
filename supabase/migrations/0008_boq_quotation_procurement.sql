-- 0008_boq_quotation_procurement
-- BOQ (spec 16), quotations (spec 17) and RFQ/procurement (spec 18).
--
-- RFQ is a later-phase module but is modelled now, as spec 18 instructs.

create table boqs (
  id           uuid primary key default gen_random_uuid(),
  project_id   uuid not null references projects(id) on delete cascade,
  revision     integer not null,
  status       boq_status not null default 'draft',
  generated_at timestamptz,
  generated_by uuid references users(id),
  approved_by  uuid references users(id),
  approved_at  timestamptz,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  unique (project_id, revision)
);
select attach_updated_at('boqs');
create index idx_boqs_project on boqs(project_id);

-- quantity_source has no 'ai_proposal' member (see 0001). Combined with the
-- check below, a quantity produced by a rule must name the execution that
-- produced it — so a number cannot arrive without provenance.
--
-- Every priced line must also carry a price_source (spec 13.2). A price with no
-- source is not representable.
create table boq_items (
  id                     uuid primary key default gen_random_uuid(),
  boq_id                 uuid not null references boqs(id) on delete cascade,
  system_id              uuid references systems(id),
  category               text,
  description            text not null,
  manufacturer_id        uuid references manufacturers(id),
  product_model_id       uuid references product_models(id),
  unit                   text not null,
  quantity               numeric(14,3) not null,
  quantity_source        quantity_source not null,
  rule_execution_id      uuid references rule_executions(id),
  price_source           price_source,
  vendor_price_id        uuid references vendor_prices(id),
  unit_cost_minor        bigint,
  installation_cost_minor bigint,
  tc_cost_minor          bigint,
  selling_price_minor    bigint,
  currency               char(3),
  notes                  text,
  ordinal                integer,
  created_at             timestamptz not null default now(),
  updated_at             timestamptz not null default now(),
  constraint boq_items_quantity_non_negative check (quantity >= 0),
  constraint boq_items_rule_quantity_needs_execution check (
    quantity_source <> 'rule_execution' or rule_execution_id is not null),
  constraint boq_items_price_needs_source check (
    unit_cost_minor is null or (price_source is not null and currency is not null))
);
select attach_updated_at('boq_items');
create index idx_boq_items_boq     on boq_items(boq_id);
create index idx_boq_items_product on boq_items(product_model_id);

create table boq_item_sources (
  id          uuid primary key default gen_random_uuid(),
  boq_item_id uuid not null references boq_items(id) on delete cascade,
  source_type text not null,
  source_id   uuid,
  note        text,
  created_at  timestamptz not null default now()
);
create index idx_boq_item_sources_item on boq_item_sources(boq_item_id);

-- ---------------------------------------------------------------------------
-- Quotations (spec 17)
-- ---------------------------------------------------------------------------

create table quotations (
  id              uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  project_id      uuid not null references projects(id) on delete cascade,
  boq_id          uuid references boqs(id),
  number          text not null,
  status          quotation_status not null default 'draft',
  created_by      uuid references users(id),
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  unique (organization_id, number)
);
select attach_updated_at('quotations');
create index idx_quotations_project on quotations(project_id);

-- Frozen at approved/issued (guard in 0010). A correction creates a new
-- revision referencing its predecessor; there is no in-place edit path.
create table quotation_revisions (
  id            uuid primary key default gen_random_uuid(),
  quotation_id  uuid not null references quotations(id) on delete cascade,
  revision      integer not null,
  supersedes_id uuid references quotation_revisions(id) on delete set null,
  content       jsonb not null default '{}'::jsonb,
  total_minor   bigint,
  currency      char(3),
  status        quotation_status not null default 'draft',
  approved_by   uuid references users(id),
  approved_at   timestamptz,
  issued_at     timestamptz,
  valid_until   date,
  created_by    uuid references users(id),
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  unique (quotation_id, revision)
);
select attach_updated_at('quotation_revisions');
create index idx_quotation_revisions_quotation on quotation_revisions(quotation_id);

create table quotation_items (
  id                    uuid primary key default gen_random_uuid(),
  quotation_revision_id uuid not null references quotation_revisions(id) on delete cascade,
  description           text not null,
  scope                 text,
  amount_minor          bigint,
  currency              char(3),
  ordinal               integer,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);
select attach_updated_at('quotation_items');
create index idx_quotation_items_revision on quotation_items(quotation_revision_id);

create table quotation_terms (
  id                    uuid primary key default gen_random_uuid(),
  quotation_revision_id uuid not null references quotation_revisions(id) on delete cascade,
  kind                  text not null,
  body                  text not null,
  ordinal               integer,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);
select attach_updated_at('quotation_terms');
create index idx_quotation_terms_revision on quotation_terms(quotation_revision_id);

-- ---------------------------------------------------------------------------
-- Procurement (spec 18)
-- ---------------------------------------------------------------------------

create table rfqs (
  id         uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  boq_id     uuid references boqs(id),
  status     rfq_status not null default 'draft',
  created_by uuid references users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
select attach_updated_at('rfqs');
create index idx_rfqs_project on rfqs(project_id);

create table rfq_suppliers (
  id           uuid primary key default gen_random_uuid(),
  rfq_id       uuid not null references rfqs(id) on delete cascade,
  supplier_id  uuid not null references suppliers(id),
  status       rfq_supplier_status not null default 'pending',
  sent_at      timestamptz,
  responded_at timestamptz,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  unique (rfq_id, supplier_id)
);
select attach_updated_at('rfq_suppliers');

create table supplier_responses (
  id               uuid primary key default gen_random_uuid(),
  rfq_supplier_id  uuid not null references rfq_suppliers(id) on delete cascade,
  document_id      uuid references documents(id),
  received_at      timestamptz not null default now(),
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);
select attach_updated_at('supplier_responses');

-- Spec 18.2: every matched item preserves the supplier document reference, the
-- extracted value, confidence, and who confirmed it.
create table supplier_response_items (
  id                   uuid primary key default gen_random_uuid(),
  supplier_response_id uuid not null references supplier_responses(id) on delete cascade,
  boq_item_id          uuid references boq_items(id) on delete set null,
  extracted_value      jsonb,
  unit_price_minor     bigint,
  currency             char(3),
  lead_time_days       integer,
  confidence           numeric(5,4) check (confidence is null or (confidence >= 0 and confidence <= 1)),
  confirmed_by         uuid references users(id),
  confirmed_at         timestamptz,
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now()
);
select attach_updated_at('supplier_response_items');
create index idx_supplier_response_items_response on supplier_response_items(supplier_response_id);
