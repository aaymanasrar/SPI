-- 0025_assumptions_and_findings
--
-- craft_operations recorded provenance, missing values and warnings. Two things
-- it could not record, both of which the engineering workflow turns on.
--
-- ASSUMPTIONS. A ceiling height used because nobody supplied one is a different
-- object from one read off a section. Both produce the same number and only one
-- can be relied on. Without somewhere to put the difference it survives in a
-- warning string at best, and nowhere at all once the number is copied.
--
-- FINDINGS. `warnings_json` is prose. A finding carries a code, a severity, the
-- subject it is about and the action required, so an unresolved item can be
-- listed, counted and chased rather than read.
--
-- The constraint below is the point of the migration: an operation may not be
-- recorded as 'ok' while it carries a blocker. The engine enforces the same rule
-- in its result envelope; this is the half that survives a bad caller.

alter table craft_operations
  add column if not exists assumptions_json jsonb not null default '[]'::jsonb,
  add column if not exists findings_json    jsonb not null default '[]'::jsonb;

comment on column craft_operations.assumptions_json is
  'Values used because nothing authoritative supplied one. Each carries its '
  'basis, its status (assumed|verified) and the document that would settle it.';
comment on column craft_operations.findings_json is
  'Actionable items: {code, severity, subject, detail, action}. Severity '
  'blocker means the result must not be relied on.';

-- An operation carrying a blocker cannot also claim to be ok.
alter table craft_operations
  drop constraint if exists craft_operations_blocker_not_ok;
alter table craft_operations
  -- jsonb containment, not a subquery: CHECK constraints forbid subqueries,
  -- and @> is immutable so it is allowed here.
  add constraint craft_operations_blocker_not_ok check (
    status <> 'ok'
    or not (findings_json @> '[{"severity": "blocker"}]'::jsonb)
  ) not valid;

-- Existing rows predate the column and are all '[]', so the check holds for
-- them; validate separately so the ALTER does not take a long lock on a large
-- table in production.
alter table craft_operations validate constraint craft_operations_blocker_not_ok;

do $$
declare n integer;
begin
  select count(*) into n from information_schema.columns
   where table_name = 'craft_operations'
     and column_name in ('assumptions_json', 'findings_json');
  if n <> 2 then
    raise exception 'craft_operations is missing the new columns (found %)', n;
  end if;
  raise notice 'craft_operations now records assumptions and findings.';
end $$;
