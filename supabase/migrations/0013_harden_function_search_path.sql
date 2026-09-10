-- 0013_harden_function_search_path
--
-- Raised by Supabase's security linter (0011_function_search_path_mutable):
-- all six functions from 0001 and 0010 had a role-mutable search_path.
--
-- Why this matters here specifically: forbid_mutation,
-- forbid_change_when_frozen and forbid_change_when_parent_frozen ARE the
-- immutability guarantee. A caller able to influence name resolution inside
-- them could weaken that guarantee, which would undermine spec 17.2 and 20.1.
--
-- Each function is pinned with `set search_path = ''` and every object
-- reference is schema-qualified. Existing triggers reference these functions
-- by OID, so replacing the bodies re-points them with no trigger changes.

create or replace function set_updated_at() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end $$;

create or replace function attach_updated_at(p_table text) returns void
language plpgsql
set search_path = ''
as $$
begin
  execute format(
    'create trigger trg_%s_updated_at before update on public.%I
       for each row execute function public.set_updated_at()',
    p_table, p_table);
end $$;

create or replace function forbid_mutation() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception
    '% is append-only: % is not permitted on this table',
    tg_table_name, tg_op
    using errcode = 'restrict_violation';
end $$;

create or replace function attach_append_only(p_table text) returns void
language plpgsql
set search_path = ''
as $$
begin
  execute format(
    'create trigger trg_%s_append_only before update or delete on public.%I
       for each row execute function public.forbid_mutation()',
    p_table, p_table);
end $$;

create or replace function forbid_change_when_frozen() returns trigger
language plpgsql
set search_path = ''
as $$
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

create or replace function forbid_change_when_parent_frozen() returns trigger
language plpgsql
set search_path = ''
as $$
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

  -- Schema-qualified: with an empty search_path an unqualified name resolves
  -- to nothing.
  execute format('select status::text from public.%I where id = $1', parent_table)
    into parent_status using parent_id;

  if parent_status = any (frozen_states) then
    raise exception
      'cannot modify % because its parent % is %',
      tg_table_name, parent_table, parent_status
      using errcode = 'restrict_violation';
  end if;
  return case when tg_op = 'DELETE' then old else new end;
end $$;
