-- 0022_bind_new_calculators
--
-- Binds the two calc_engine modules added alongside it:
--
--   lock_psu            -> SPT-AC-09 (lock power supply sizing)
--   bms_station_select  -> NOTHING. See below.
--
-- WHY bms_station_select IS NOT BOUND. The Siemens catalogue (0020-0021) carries
-- three Desigo PXC7 automation stations, and not one of the 181 encoded rules
-- covers building management. There is no rule to bind the module to. The module
-- is in the REGISTRY and works; it is simply invisible to anyone reading a rule
-- pack until BMS rules are supplied. Recorded here rather than silently skipped,
-- because an unbound calculator looks identical to a missing one.
--
-- lock_psu extends AC-09 with a simultaneous-release surge check that AC-09 as
-- written does not have. On a realistic door schedule the surge governs: 8 maglocks
-- plus 4 electric strikes plus 12 readers needs 8.05 A by the AC-09 steady rule but
-- 9.04 A once four strikes release together. Sizing to AC-09 alone picks the
-- smaller supply. The rule text is unchanged; the extension lives in the module and
-- is reported as a separate pass/fail.
--
-- Idempotent.

create or replace function bind_new_calculators(p_organization_id uuid)
returns integer
language plpgsql
set search_path = ''
as $fn$
declare v_bound integer;
begin
  update public.engineering_rules er
     set calculator_module = 'lock_psu'
   where er.organization_id = p_organization_id
     and er.rule_code = 'SPT-AC-09'
     and er.calculator_module is distinct from 'lock_psu';
  get diagnostics v_bound = row_count;
  return v_bound;
end $fn$;

comment on function bind_new_calculators(uuid) is
  'Binds SPT-AC-09 to calc_engine.lock_psu. bms_station_select stays unbound: no '
  'encoded rule covers BMS.';

do $$
declare o record; n integer;
begin
  for o in select id, name from organizations loop
    select bind_new_calculators(o.id) into n;
    raise notice 'Bound % further rule(s) to calc_engine for %', n, o.name;
  end loop;
end $$;
