-- 0019_bind_calculators
--
-- The evaluator ARCHITECTURE.md 9.4 deferred now exists: calc_engine/, ten
-- deterministic modules with a CalcResult audit trail (inputs, steps,
-- assumptions, warnings, references, pass/fail).
--
-- This migration does the one thing that turns 181 rules and 10 calculators
-- into a system: it says WHICH module computes WHICH rule. Without the binding
-- a model has to guess, and guessing between video_storage and
-- network_bandwidth is how a storage quote goes wrong.
--
-- What this does NOT do:
--   * It does not set rule_versions.calculation->>'evaluator'. Those payloads
--     still say "unassigned" because the binding is a pointer, not a compiled
--     expression. The module still needs its arguments gathered by the caller.
--   * It does not make any rule approvable. All 181 versions stay draft.
--
-- Division of labour, per calc_engine/__init__.py:
--   AI layer  decides a calculation is needed and gathers inputs
--   KB layer  supplies manufacturer data (quiescent current, PoE class, bitrate)
--   engine    does the maths, deterministically, and shows its working
--
-- Idempotent.

alter table engineering_rules
  add column if not exists calculator_module text;

comment on column engineering_rules.calculator_module is
  'Name of the calc_engine module that computes this rule, as keyed in '
  'calc_engine.REGISTRY. Null means the rule is a constraint or a checklist '
  'with no calculation, which is most of them.';

create index if not exists idx_engineering_rules_calculator
  on engineering_rules (organization_id, calculator_module)
  where calculator_module is not null;

create or replace function bind_calculators(p_organization_id uuid)
returns integer
language plpgsql
set search_path = ''
as $fn$
declare v_bound integer;
begin
  update public.engineering_rules er
     set calculator_module = b.module
  from (values
    -- Fire alarm
    ('SPT-FA-18', 'fire_alarm_battery'),
    ('SPT-FA-19', 'nac_end_of_line'),
    ('ELV-B-11',  'fire_alarm_battery'),
    -- CCTV: bandwidth feeds storage, so both are bound
    ('SPT-CC-04', 'video_storage'),
    ('SPT-CC-06', 'network_bandwidth'),
    ('SPT-CC-07', 'poe_budget'),
    ('ELV-C-02',  'poe_budget'),
    ('ELV-C-03',  'poe_budget'),
    -- The retention rules all size storage, and they disagree. Binding them to
    -- the same module is deliberate: it makes the disagreement computable
    -- instead of rhetorical. Same cameras, 30 / 60 / 90 days, three answers.
    ('KSA-CCTV-04', 'video_storage'),
    ('SPT-LP-07',   'video_storage'),
    ('SPT-LP-20',   'video_storage'),
    ('SPT-LP-21',   'video_storage'),
    -- Network
    ('SPT-NW-01', 'poe_budget'),
    ('SPT-NW-02', 'poe_budget'),
    ('SPT-LP-24', 'network_bandwidth'),
    -- UPS and battery
    ('SPT-UP-01', 'ups_sizing'),
    ('SPT-UP-02', 'dc_battery_bank'),
    ('SPT-LP-30', 'dc_battery_bank'),
    ('SPT-LP-31', 'dc_battery_bank'),
    ('SPT-LP-19', 'dc_battery_bank')
  ) as b(rule_code, module)
  where er.organization_id = p_organization_id
    and er.rule_code = b.rule_code
    and er.calculator_module is distinct from b.module;

  get diagnostics v_bound = row_count;
  return v_bound;
end $fn$;

comment on function bind_calculators(uuid) is
  'Maps rules to calc_engine modules. Three retention rules (KSA-CCTV-04, '
  'LP-07, LP-20) bind to video_storage on purpose: they disagree about the '
  'retention period, and running one module across all three turns that '
  'disagreement into a disk count.';

do $$
declare o record; n integer;
begin
  for o in select id, name from organizations loop
    select bind_calculators(o.id) into n;
    raise notice 'Bound % rule(s) to calc_engine modules for %', n, o.name;
  end loop;
end $$;
