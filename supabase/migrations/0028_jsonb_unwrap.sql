-- 0028_jsonb_unwrap
--
-- Until this release the app wrote jsonb columns from JSON.stringify(...), so
-- craft_operations, audit_logs and system_requirements hold rows whose value is
-- a JSON *string* containing the JSON ('"[]"' instead of '[]'). The writers are
-- fixed. craft_operations and audit_logs are append-only, so those rows stay
-- as written: readers unwrap them with this function instead. It returns any
-- value that is not such a string unchanged, so it is safe on every row.

create or replace function jsonb_unwrap(v jsonb)
returns jsonb
language sql
immutable
parallel safe
set search_path = public
as $$
  select case
    when jsonb_typeof(v) = 'string'
     and left(v #>> '{}', 1) in ('[', '{')
    then (v #>> '{}')::jsonb
    else v
  end
$$;

comment on function jsonb_unwrap(jsonb) is
  'Reads a jsonb value that may have been double-encoded as a JSON string. See 0028.';

-- system_requirements is not append-only: repair arrays and objects in place.
-- A double-encoded scalar ('"5"') is left as it is: it cannot be told apart
-- from a requirement whose value really is the text "5".
update system_requirements
   set value = jsonb_unwrap(value)
 where jsonb_typeof(value) = 'string'
   and jsonb_unwrap(value) is distinct from value;
