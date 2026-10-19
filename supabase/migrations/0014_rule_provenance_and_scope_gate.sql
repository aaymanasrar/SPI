-- 0014_rule_provenance_and_scope_gate
--
-- The first real SmartPage engineering rules (the ELV & Telecom Installation
-- Rule Guide Book, 21 Sep 2026) arrive in 0015. They carry two properties the
-- 0005 framework has no home for, and both are load-bearing rather than
-- descriptive:
--
--   1. A confidence tag. The guide tags every rule CODE, SPEC or LOCAL, and its
--      own rule X-06 makes that tag a control: "Every rule used in a BOQ, TBE or
--      method statement must carry its tag and cite the drawing or SOW clause
--      that makes it a scope item. SPEC and LOCAL rules are not scope by
--      themselves." A SPEC rule silently becoming a BOQ quantity is exactly the
--      failure knowledge/README.md warns about.
--
--   2. Source provenance and verification state. The guide is unusually candid
--      that several of its figures come from general knowledge rather than an
--      opened standard, and that no current edition of TIA-568.2-D, NFPA 72 or
--      BS 5839-1 was consulted. That distinction must survive into the database,
--      because "where did you come from?" is the question the platform exists to
--      answer.
--
-- This migration adds both, plus the enforcement for X-06. It adds no rules.

-- ---------------------------------------------------------------------------
-- Confidence tag
-- ---------------------------------------------------------------------------

create type rule_confidence as enum ('code','spec','local');

comment on type rule_confidence is
  'How far a rule can be relied on. code = stated in a published standard, may '
  'bind on its own. spec = project or client practice, binds only where the SOW '
  'or drawing calls it out. local = one jurisdiction or regulator, never carried '
  'across borders without checking the local authority.';

-- engineering_rules is empty by construction: 0012 seeds no rules and states
-- that none may be added by an agent. Adding a NOT NULL column with no default
-- is therefore safe, and is preferred over backfilling a guessed tag — a
-- fabricated 'spec' on a rule that is actually CODE would defeat the point of
-- the column. If this raises, stop and tag the existing rows by hand.
do $$
begin
  if exists (select 1 from engineering_rules) then
    raise exception
      'engineering_rules already holds % row(s); tag each one before applying 0014',
      (select count(*) from engineering_rules)
      using errcode = 'restrict_violation';
  end if;
end $$;

alter table engineering_rules
  add column confidence        rule_confidence not null,
  add column source_document   text,
  add column source_rule_id    text,
  add column source_verified   boolean not null default false,
  add column verification_note text;

comment on column engineering_rules.source_document is
  'Path, relative to knowledge/, of the reviewed source this rule was encoded from.';
comment on column engineering_rules.source_rule_id is
  'The rule identifier used by the source document, e.g. A-01, so a BOQ line can '
  'be argued back to a page of that document.';
comment on column engineering_rules.source_verified is
  'True only when the cited source was opened and confirms this rule content. '
  'False means the rule is believed correct but the naming standard or current '
  'edition has not been read.';

-- An unverified rule must say what is missing. This is the cheap half of the
-- discipline: the expensive half is someone reading the standard.
alter table engineering_rules
  add constraint engineering_rules_unverified_needs_note
  check (source_verified or verification_note is not null);

-- One encoding per source rule, so the same guide cannot be loaded twice under
-- two rule codes and quietly double-count.
create unique index uq_engineering_rules_source
  on engineering_rules (organization_id, source_document, source_rule_id)
  where source_document is not null and source_rule_id is not null;

create index idx_engineering_rules_confidence
  on engineering_rules (organization_id, confidence);

-- ---------------------------------------------------------------------------
-- Cross-discipline rules
-- ---------------------------------------------------------------------------
--
-- Part X of the guide (X-01..X-06) is genuinely not a property of one system:
-- the cause-and-effect matrix, the firestop log and the AHJ edition check sit at
-- the interfaces between trades. Forcing them onto an arbitrary system_id, or
-- inventing a fake "cross-discipline" row in `systems` that a client could then
-- select on a project, would both misrepresent them.
--
-- Null system_id therefore means: applies to every system in scope.

alter table engineering_rules alter column system_id drop not null;

comment on column engineering_rules.system_id is
  'The system this rule belongs to. Null means cross-discipline: the rule applies '
  'to every system selected on the project.';

create index idx_engineering_rules_cross_discipline
  on engineering_rules (organization_id)
  where system_id is null;

-- ---------------------------------------------------------------------------
-- X-06 enforcement: SPEC and LOCAL are not scope by themselves
-- ---------------------------------------------------------------------------
--
-- Checked at the transition into validated/approved/issued rather than at item
-- insert, because during drafting an engineer legitimately has a rule-derived
-- quantity before the SOW clause has been pinned to it. By the time a BOQ is
-- validated, that excuse has expired.
--
-- The citation lives in boq_item_sources, which already exists for exactly this
-- purpose. Three source types satisfy the rule; anything else does not.

create or replace function forbid_unsupported_scope() returns trigger
language plpgsql
set search_path = ''
as $$
declare
  offending text;
begin
  select string_agg(
           format('%s (%s %s)', bi.description, er.source_rule_id, er.confidence),
           '; ' order by bi.ordinal nulls last, bi.description)
    into offending
  from public.boq_items      bi
  join public.rule_executions re on re.id = bi.rule_execution_id
  join public.rule_versions    rv on rv.id = re.rule_version_id
  join public.engineering_rules er on er.id = rv.rule_id
  where bi.boq_id = new.id
    and er.confidence in ('spec','local')
    and not exists (
      select 1
      from public.boq_item_sources s
      where s.boq_item_id = bi.id
        and s.source_type in ('sow_clause','drawing','client_standard')
    );

  if offending is not null then
    raise exception
      'BOQ % cannot become %: these quantities come from SPEC or LOCAL rules with '
      'no drawing or SOW citation (rule X-06): %',
      new.id, new.status, offending
      using errcode = 'restrict_violation',
            hint = 'Add a boq_item_sources row of type sow_clause, drawing or '
                   'client_standard to each item, or remove the item.';
  end if;

  return new;
end $$;

comment on function forbid_unsupported_scope() is
  'Implements rule X-06 of the ELV & Telecom Installation Rule Guide Book: a SPEC '
  'or LOCAL rule is not scope by itself. See '
  'knowledge/standards-references/elv-telecom-installation-rule-guide/.';

create trigger trg_boqs_scope_basis
  before update on boqs
  for each row
  when (new.status in ('validated','approved','issued')
        and old.status is distinct from new.status)
  execute function forbid_unsupported_scope();
