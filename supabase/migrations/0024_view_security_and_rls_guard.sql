-- 0024_view_security_and_rls_guard
--
-- Closes a hole in my own 0020/0021 and adds a guard so it cannot reappear.
--
-- THE HOLE. 0011 enabled row-level security on every table with no policies, a
-- default-deny posture: PostgREST's anon and authenticated roles get nothing,
-- while the application's server-side connection (owner / service_role)
-- bypasses RLS. That is sound for tables.
--
-- It does nothing for views. In PostgreSQL 15+ a view executes with the
-- privileges of its OWNER unless created `with (security_invoker = true)`.
-- The owner here is the same role that owns the tables, and that role bypasses
-- RLS. Supabase's default privileges also grant select on new objects in
-- `public` to anon and authenticated. So `engine_readiness` and
-- `product_variant_traps` were readable by anyone holding the publishable key,
-- which is published to the browser by design, and they read straight through
-- the RLS that protects product_models, products and manufacturers.
--
-- Exposed: part numbers, model names, verification status, PoE budgets and
-- supply voltages for the whole authorized product catalogue. No price, rate or
-- margin column appears in either view, so the commercial visibility boundary
-- (ARCHITECTURE 6.3) was not breached. The catalogue is still SmartPage's and
-- was not meant to be public.
--
-- THE SECOND PROBLEM. Neither view selected organization_id or filtered on it,
-- so they were cross-tenant by construction. Even a legitimate server-side
-- caller could not scope them to one organization, because the column was not
-- there to filter on. Both now carry organization_id, reached through
-- manufacturers, so the repository layer can filter as it does elsewhere.
--
-- WHAT THIS MIGRATION DOES NOT DO. It does not add RLS policies. Default-deny
-- stays. Direct PostgREST access for a client role is a separate, deliberate
-- decision per table, as 0011 says.

-- ---------------------------------------------------------------------------
-- engine_readiness
-- ---------------------------------------------------------------------------
drop view if exists public.engine_readiness;

create view public.engine_readiness
  with (security_invoker = true) as
select
  m.organization_id,
  pm.part_number, pm.model, p.product_family as family, pm.verification_status,
  'fire_alarm_battery' as calculator_module,
  (pm.quiescent_current_ma is not null and pm.alarm_current_ma is not null) as ready,
  array_remove(array[
    case when pm.quiescent_current_ma is null then 'quiescent_current_ma' end,
    case when pm.alarm_current_ma     is null then 'alarm_current_ma'     end
  ], null) as missing_fields
from public.product_models pm
join public.products p      on p.id = pm.product_id
join public.manufacturers m on m.id = p.manufacturer_id
where p.product_family = 'Fire'
  and (p.category ilike '%detector%'
       or p.category ilike '%call point%'
       or p.category ilike '%panel%')
  and p.category not ilike '%base%'
union all
select
  m.organization_id,
  pm.part_number, pm.model, p.product_family, pm.verification_status,
  'poe_budget',
  (pm.poe_budget_w is not null and pm.poe_ports is not null
     and pm.poe_max_class is not null),
  array_remove(array[
    case when pm.poe_budget_w  is null then 'poe_budget_w'  end,
    case when pm.poe_ports     is null then 'poe_ports'     end,
    case when pm.poe_max_class is null then 'poe_max_class' end
  ], null)
from public.product_models pm
join public.products p      on p.id = pm.product_id
join public.manufacturers m on m.id = p.manufacturer_id
where p.category ilike '%PoE%';

comment on view public.engine_readiness is
  'Which catalogue items can feed which calc_engine module, and what is missing '
  'when they cannot. A null numeric means NOT CAPTURED, never zero. '
  'security_invoker: the caller''s RLS applies. Filter by organization_id.';

-- ---------------------------------------------------------------------------
-- product_variant_traps
-- ---------------------------------------------------------------------------
drop view if exists public.product_variant_traps;

create view public.product_variant_traps
  with (security_invoker = true) as
select ma.organization_id,
       btrim(regexp_replace(a.model, '\s*\([^)]*\)\s*$', '')) as base_model,
       a.part_number as part_a, b.part_number as part_b,
       a.poe_budget_w as budget_a_w, b.poe_budget_w as budget_b_w,
       a.supply_voltage as supply_a, b.supply_voltage as supply_b
from public.product_models a
join public.products  pa on pa.id = a.product_id
join public.manufacturers ma on ma.id = pa.manufacturer_id
join public.product_models b
  on btrim(regexp_replace(a.model, '\s*\([^)]*\)\s*$', '')) =
     btrim(regexp_replace(b.model, '\s*\([^)]*\)\s*$', ''))
 and a.part_number < b.part_number
join public.products  pb on pb.id = b.product_id
-- Same tenant on both sides: a "trap" is only a trap within one catalogue.
join public.manufacturers mb on mb.id = pb.manufacturer_id
                            and mb.organization_id = ma.organization_id
where a.poe_budget_w is distinct from b.poe_budget_w
   or a.power_w      is distinct from b.power_w;

comment on view public.product_variant_traps is
  'Catalogue items sharing a model name but differing in PoE budget. Specify by '
  'part number, never by model name alone. security_invoker: the caller''s RLS '
  'applies. Filter by organization_id.';

-- ---------------------------------------------------------------------------
-- Defence in depth: PostgREST should not see these at all.
-- security_invoker already denies the rows; this denies the object.
-- ---------------------------------------------------------------------------
do $$
begin
  if exists (select 1 from pg_roles where rolname = 'anon') then
    execute 'revoke all on public.engine_readiness      from anon';
    execute 'revoke all on public.product_variant_traps from anon';
  end if;
  if exists (select 1 from pg_roles where rolname = 'authenticated') then
    execute 'revoke all on public.engine_readiness      from authenticated';
    execute 'revoke all on public.product_variant_traps from authenticated';
  end if;
end $$;

-- ---------------------------------------------------------------------------
-- The guard.
--
-- 0011's loop was one-shot: it enabled RLS on what existed when it ran, and
-- 0017 then created two tables that went unprotected until 0023. The lesson is
-- that a posture applied once is not a posture maintained. This block asserts
-- the whole public schema and RAISES, failing the migration, if anything is
-- wrong -- so the next table or view created without protection breaks the
-- build rather than quietly exposing data.
--
-- Run the same assertions against a live database any time with
-- scripts/check-rls.
-- ---------------------------------------------------------------------------
do $$
declare
  unprotected text[];
  leaky       text[];
begin
  select coalesce(array_agg(c.relname order by c.relname), '{}')
    into unprotected
  from pg_class c
  join pg_namespace n on n.oid = c.relnamespace
  where n.nspname = 'public'
    and c.relkind = 'r'
    and not c.relrowsecurity;

  if array_length(unprotected, 1) > 0 then
    raise exception
      'Tables in public without row level security: %. Every table must enable '
      'RLS in the migration that creates it; 0011''s loop only covered what '
      'existed when it ran.', array_to_string(unprotected, ', ');
  end if;

  select coalesce(array_agg(c.relname order by c.relname), '{}')
    into leaky
  from pg_class c
  join pg_namespace n on n.oid = c.relnamespace
  where n.nspname = 'public'
    and c.relkind = 'v'
    and coalesce((select option_value
                  from pg_options_to_table(c.reloptions)
                  where option_name = 'security_invoker'), 'false') <> 'true';

  if array_length(leaky, 1) > 0 then
    raise exception
      'Views in public without security_invoker: %. Such a view runs as its '
      'owner and reads through the RLS protecting its base tables.',
      array_to_string(leaky, ', ');
  end if;

  raise notice 'RLS posture verified: every public table has RLS, every public view is security_invoker.';
end $$;
