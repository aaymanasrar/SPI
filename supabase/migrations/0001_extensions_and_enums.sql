-- 0001_extensions_and_enums
-- Extensions, shared helper functions, and every enum type used by the schema.
-- Contains no engineering rules, products, prices or catalogue data.

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------
-- Shared helpers
-- ---------------------------------------------------------------------------

create or replace function set_updated_at() returns trigger
language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

-- Attaches the updated_at trigger to a table. Keeps the per-table DDL below
-- readable instead of repeating an identical trigger definition 40 times.
create or replace function attach_updated_at(p_table text) returns void
language plpgsql as $$
begin
  execute format(
    'create trigger trg_%s_updated_at before update on %I
       for each row execute function set_updated_at()',
    p_table, p_table);
end $$;

-- ---------------------------------------------------------------------------
-- Identity
-- ---------------------------------------------------------------------------
create type org_status         as enum ('active','suspended','archived');
create type user_status        as enum ('invited','active','suspended');
create type membership_status  as enum ('active','suspended');

-- ---------------------------------------------------------------------------
-- Provenance (spec 9.2) — applied to every building-model and extracted object
-- ---------------------------------------------------------------------------
create type source_type   as enum ('manual','ai_extracted','imported');
create type review_status as enum ('not_required','pending','approved','rejected');

-- ---------------------------------------------------------------------------
-- Projects
-- ---------------------------------------------------------------------------
create type project_status        as enum ('draft','active','on_hold','completed','archived');
create type project_system_status as enum ('selected','in_design','designed','validated');

-- ---------------------------------------------------------------------------
-- Documents
-- ---------------------------------------------------------------------------
create type doc_classification as enum
  ('drawing','specification','scope_of_work','boq','datasheet',
   'compliance','quotation','correspondence','other');
create type extraction_status  as enum ('queued','running','succeeded','failed');
create type proposal_status    as enum ('pending','accepted','rejected','superseded');

-- ---------------------------------------------------------------------------
-- Rules (spec 11.2 lifecycle)
-- ---------------------------------------------------------------------------
create type rule_approval_status as enum
  ('draft','engineer_review','approved','active','superseded');
create type rule_test_result     as enum ('not_run','passed','failed');

-- ---------------------------------------------------------------------------
-- Catalogue (spec 12.2)
-- ---------------------------------------------------------------------------
create type product_approval_status as enum ('pending','approved','rejected');
create type authorized_status       as enum ('authorized','not_authorized','expired');
create type lifecycle_status        as enum ('active','superseded','withdrawn');

-- ---------------------------------------------------------------------------
-- Pricing (spec 13.2 price source hierarchy — there is no fifth option)
-- ---------------------------------------------------------------------------
create type price_source as enum
  ('vendor_approved','supplier_quotation','internal_price_list','manual_override');
create type price_list_status  as enum ('draft','approved','superseded');
create type pricing_rule_kind  as enum ('overhead','margin','logistics','engineering');
create type pricing_basis      as enum ('percentage','fixed','fixed_per_unit');

-- ---------------------------------------------------------------------------
-- Design
-- ---------------------------------------------------------------------------
create type length_basis     as enum ('manual','calculated','unknown');
create type interface_status as enum ('proposed','approved','implemented');

-- ---------------------------------------------------------------------------
-- BOQ and commercial
-- ---------------------------------------------------------------------------
-- Deliberately has no 'ai_proposal' member. An AI-inferred number cannot be a
-- BOQ quantity; this is the structural half of the spec 10.3 no-guess policy.
create type quantity_source as enum ('rule_execution','manual','imported');

create type boq_status as enum
  ('draft','generated','engineer_review','corrections','validated','approved','issued');
create type quotation_status as enum
  ('draft','engineer_review','commercial_revision','approved','issued');

-- ---------------------------------------------------------------------------
-- Procurement
-- ---------------------------------------------------------------------------
create type rfq_status          as enum ('draft','sent','responses_received','closed');
create type rfq_supplier_status as enum ('pending','sent','responded','declined');

-- ---------------------------------------------------------------------------
-- Governance (spec 23.1)
-- ---------------------------------------------------------------------------
create type validation_layer    as enum ('input','engineering','commercial','ai_anomaly');
create type validation_severity as enum ('error','critical_review','warning','info');
create type review_task_status  as enum ('open','in_progress','resolved','dismissed');
