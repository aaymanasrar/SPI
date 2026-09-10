-- 0006_catalogue_and_pricing
-- The SmartPage Authorized Product Catalogue (spec 12) and the pricing data
-- model (spec 13).
--
-- This migration creates empty containers. No manufacturer, product, model,
-- authorization, supplier, price or rate is inserted anywhere in it. That data
-- is SmartPage's (Appendix A) and must never be invented.
--
-- Money is stored as integer minor units with an explicit currency. No floats.

create table manufacturers (
  id              uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  name            text not null,
  status          lifecycle_status not null default 'active',
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  unique (organization_id, name)
);
select attach_updated_at('manufacturers');

create table suppliers (
  id              uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  name            text not null,
  contact_name    text,
  contact_email   text,
  contact_phone   text,
  status          lifecycle_status not null default 'active',
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  unique (organization_id, name)
);
select attach_updated_at('suppliers');

create table products (
  id              uuid primary key default gen_random_uuid(),
  manufacturer_id uuid not null references manufacturers(id) on delete cascade,
  product_family  text,
  category        text not null,
  description     text,
  status          lifecycle_status not null default 'active',
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);
select attach_updated_at('products');
create index idx_products_manufacturer on products(manufacturer_id);
create index idx_products_category     on products(category);

-- Automatic selection requires: authorized_status = 'authorized'
--                          AND  lifecycle_status <> 'withdrawn'
--                          AND  an in-date row in authorizations
-- (spec 12.2). Expired records stay readable for historical projects but are
-- not selectable.
create table product_models (
  id                       uuid primary key default gen_random_uuid(),
  product_id               uuid not null references products(id) on delete cascade,
  model                    text not null,
  technical_specifications jsonb not null default '{}'::jsonb,
  approval_status          product_approval_status not null default 'pending',
  authorized_status        authorized_status       not null default 'not_authorized',
  authorized_regions       text[],
  lifecycle_status         lifecycle_status        not null default 'active',
  revision                 integer not null default 1,
  superseded_by_id         uuid references product_models(id) on delete set null,
  created_at               timestamptz not null default now(),
  updated_at               timestamptz not null default now(),
  unique (product_id, model, revision)
);
select attach_updated_at('product_models');
create index idx_product_models_product    on product_models(product_id);
create index idx_product_models_selectable on product_models(authorized_status, lifecycle_status);

create table product_documents (
  id               uuid primary key default gen_random_uuid(),
  product_model_id uuid not null references product_models(id) on delete cascade,
  document_id      uuid not null references documents(id) on delete cascade,
  doc_type         text not null,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  unique (product_model_id, document_id, doc_type)
);
select attach_updated_at('product_documents');

create table authorizations (
  id                   uuid primary key default gen_random_uuid(),
  product_model_id     uuid not null references product_models(id) on delete cascade,
  authority            text not null,
  reference            text,
  valid_from           date,
  valid_to             date,
  evidence_document_id uuid references documents(id) on delete set null,
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now(),
  constraint authorizations_valid_range check (
    valid_to is null or valid_from is null or valid_to >= valid_from)
);
select attach_updated_at('authorizations');
create index idx_authorizations_model on authorizations(product_model_id);

-- Alternatives must be explicitly approved and mapped (spec 12.2).
create table alternatives (
  id                   uuid primary key default gen_random_uuid(),
  product_model_id     uuid not null references product_models(id) on delete cascade,
  alternative_model_id uuid not null references product_models(id) on delete cascade,
  approved_by          uuid references users(id),
  approved_at          timestamptz,
  notes                text,
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now(),
  unique (product_model_id, alternative_model_id),
  constraint alternatives_not_self check (product_model_id <> alternative_model_id)
);
select attach_updated_at('alternatives');

-- ---------------------------------------------------------------------------
-- Pricing (spec 13)
-- ---------------------------------------------------------------------------

create table price_lists (
  id              uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  name            text not null,
  currency        char(3) not null,
  effective_from  date not null,
  effective_to    date,
  status          price_list_status not null default 'draft',
  approved_by     uuid references users(id),
  approved_at     timestamptz,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  constraint price_lists_effective_range check (
    effective_to is null or effective_to >= effective_from)
);
select attach_updated_at('price_lists');
create index idx_price_lists_org on price_lists(organization_id);

-- Append-only (guard in 0010): a price change inserts a new row, which is how
-- "price changes must preserve historical values" (spec 12.2) is enforced.
create table vendor_prices (
  id               uuid primary key default gen_random_uuid(),
  price_list_id    uuid not null references price_lists(id) on delete cascade,
  product_model_id uuid not null references product_models(id),
  supplier_id      uuid references suppliers(id),
  unit_price_minor bigint not null,
  currency         char(3) not null,
  price_source     price_source not null,
  price_valid_from date not null,
  price_valid_to   date,
  lead_time_days   integer,
  created_by       uuid references users(id),
  created_at       timestamptz not null default now()
);
create index idx_vendor_prices_list  on vendor_prices(price_list_id);
create index idx_vendor_prices_model on vendor_prices(product_model_id);

create table labor_rates (
  id              uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  activity        text not null,
  unit            text not null,
  rate_minor      bigint not null,
  currency        char(3) not null,
  effective_from  date not null,
  effective_to    date,
  approved_by     uuid references users(id),
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);
select attach_updated_at('labor_rates');

create table installation_rates (
  id              uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  item_type       text not null,
  unit            text not null,
  rate_minor      bigint not null,
  currency        char(3) not null,
  effective_from  date not null,
  effective_to    date,
  approved_by     uuid references users(id),
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);
select attach_updated_at('installation_rates');

create table tc_rates (
  id              uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  activity        text not null,
  unit            text not null,
  rate_minor      bigint not null,
  currency        char(3) not null,
  effective_from  date not null,
  effective_to    date,
  approved_by     uuid references users(id),
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);
select attach_updated_at('tc_rates');

create table pricing_rules (
  id              uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  kind            pricing_rule_kind not null,
  basis           pricing_basis not null,
  value           numeric(14,4) not null,
  effective_from  date not null,
  effective_to    date,
  approved_by     uuid references users(id),
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);
select attach_updated_at('pricing_rules');
