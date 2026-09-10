-- 0010_immutability_triggers
-- Enforces spec 17.2 and 20.1 at the database, not only in application code.
--
-- Two guarantees:
--   1. Append-only tables reject UPDATE and DELETE outright.
--   2. Approval-frozen tables reject UPDATE and DELETE once the row has reached
--      an approved/issued state.
--
-- A correction after approval creates a new revision. There is deliberately no
-- supported path that edits an approved record in place.

-- ---------------------------------------------------------------------------
-- Append-only
-- ---------------------------------------------------------------------------

create or replace function forbid_mutation() returns trigger
language plpgsql as $$
begin
  raise exception
    '% is append-only: % is not permitted on this table',
    tg_table_name, tg_op
    using errcode = 'restrict_violation';
end $$;

create or replace function attach_append_only(p_table text) returns void
language plpgsql as $$
begin
  execute format(
    'create trigger trg_%s_append_only before update or delete on %I
       for each row execute function forbid_mutation()',
    p_table, p_table);
end $$;

select attach_append_only('rule_executions');
select attach_append_only('extraction_runs');
select attach_append_only('approvals');
select attach_append_only('audit_logs');
select attach_append_only('vendor_prices');

-- ---------------------------------------------------------------------------
-- Frozen once approved
-- ---------------------------------------------------------------------------

-- Guards a table with its own status column.
create or replace function forbid_change_when_frozen() returns trigger
language plpgsql as $$
declare
  frozen_states text[] := tg_argv[0]::text[];
  old_status    text;
begin
  execute format('select ($1).%I::text', tg_argv[1]) into old_status using old;

  if old_status = any (frozen_states) then
    raise exception
      '% % is % and is immutable; create a new revision instead',
      tg_table_name, old.id, old_status
      using errcode = 'restrict_violation';
  end if;
  return case when tg_op = 'DELETE' then old else new end;
end $$;

create trigger trg_quotation_revisions_frozen
  before update or delete on quotation_revisions
  for each row execute function forbid_change_when_frozen('{approved,issued}', 'status');

create trigger trg_boqs_frozen
  before update or delete on boqs
  for each row execute function forbid_change_when_frozen('{approved,issued}', 'status');

create trigger trg_rule_versions_frozen
  before update or delete on rule_versions
  for each row execute function forbid_change_when_frozen(
    '{approved,active,superseded}', 'approval_status');

-- Guards child rows by looking at the parent's status.
create or replace function forbid_change_when_parent_frozen() returns trigger
language plpgsql as $$
declare
  parent_table  text   := tg_argv[0];
  parent_column text   := tg_argv[1];
  frozen_states text[] := tg_argv[2]::text[];
  parent_id     uuid;
  parent_status text;
begin
  execute format('select ($1).%I', parent_column)
    into parent_id
    using case when tg_op = 'DELETE' then old else new end;

  if parent_id is null then
    return case when tg_op = 'DELETE' then old else new end;
  end if;

  execute format('select status::text from %I where id = $1', parent_table)
    into parent_status using parent_id;

  if parent_status = any (frozen_states) then
    raise exception
      'cannot modify % because its parent % is %',
      tg_table_name, parent_table, parent_status
      using errcode = 'restrict_violation';
  end if;
  return case when tg_op = 'DELETE' then old else new end;
end $$;

create trigger trg_boq_items_parent_frozen
  before insert or update or delete on boq_items
  for each row execute function forbid_change_when_parent_frozen(
    'boqs', 'boq_id', '{approved,issued}');

create trigger trg_quotation_items_parent_frozen
  before insert or update or delete on quotation_items
  for each row execute function forbid_change_when_parent_frozen(
    'quotation_revisions', 'quotation_revision_id', '{approved,issued}');

create trigger trg_quotation_terms_parent_frozen
  before insert or update or delete on quotation_terms
  for each row execute function forbid_change_when_parent_frozen(
    'quotation_revisions', 'quotation_revision_id', '{approved,issued}');
