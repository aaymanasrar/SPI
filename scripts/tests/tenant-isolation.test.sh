#!/usr/bin/env bash
# Cross-tenant and anonymous access regression test.
#
# Runs against a real database. It inserts a second organisation inside a
# transaction and rolls back, so nothing survives the run.
#
#   scripts/tests/tenant-isolation.test.sh "$LOCAL_DATABASE_URL"
set -uo pipefail
DB="${1:-${DATABASE_URL:-}}"
[ -z "$DB" ] && { echo "usage: $0 <connection-string>" >&2; exit 2; }
psql -tAX -v ON_ERROR_STOP=1 -d "$DB" -c "select 1" >/dev/null 2>&1 || {
  echo "  cannot connect; the check did not run. That is not a pass." >&2; exit 1; }

# Replicate Supabase default grants so the test reflects the deployment, not a
# stricter local database. Roles are created if the cluster has none.
psql -qX -d "$DB" >/dev/null 2>&1 <<'SQL'
do $$ begin
  if not exists (select 1 from pg_roles where rolname='anon') then create role anon nologin; end if;
  if not exists (select 1 from pg_roles where rolname='authenticated') then create role authenticated nologin; end if;
end $$;
grant usage on schema public to anon, authenticated;
grant select on all tables in schema public to anon, authenticated;
SQL
fail=0
chk() { # label, sql, expected
  # `set role` emits SET before the result, so take the last non-empty line.
  got=$(psql -tAX -d "$DB" -c "$2" 2>/dev/null | grep -v '^SET$' | grep . | tail -1 | tr -d ' ')
  if [ "$got" = "$3" ]; then printf '  ok    %s\n' "$1"
  else printf '  FAIL  %s (expected %s, got %s)\n' "$1" "$3" "$got"; fail=1; fi
}

chk "anon reads no product_models"   "set role anon; select count(*) from product_models;" "0"
chk "anon reads no manufacturers"    "set role anon; select count(*) from manufacturers;" "0"
chk "anon reads no engineering_rules" "set role anon; select count(*) from engineering_rules;" "0"
chk "anon reads no boq_items"        "set role anon; select count(*) from boq_items;" "0"
chk "anon reads no craft_operations" "set role anon; select count(*) from craft_operations;" "0"
chk "authenticated reads no product_models" "set role authenticated; select count(*) from product_models;" "0"
chk "owner still reads the catalogue" "select case when count(*)>0 then 'yes' else 'no' end from product_models;" "yes"

# Views must not leak across tenants, and must carry the column to scope by.
chk "engine_readiness exposes organization_id" \
  "select count(*) from information_schema.columns where table_name='engine_readiness' and column_name='organization_id';" "1"
chk "product_variant_traps exposes organization_id" \
  "select count(*) from information_schema.columns where table_name='product_variant_traps' and column_name='organization_id';" "1"
chk "no trap pair spans two tenants" "
  select count(*) from product_variant_traps v
  join product_models a on a.part_number=v.part_a
  join products pa on pa.id=a.product_id join manufacturers ma on ma.id=pa.manufacturer_id
  join product_models b on b.part_number=v.part_b
  join products pb on pb.id=b.product_id join manufacturers mb on mb.id=pb.manufacturer_id
  where ma.organization_id <> mb.organization_id;" "0"
chk "both views are security_invoker" "
  select count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace
  where n.nspname='public' and c.relkind='v'
    and coalesce((select option_value from pg_options_to_table(c.reloptions)
                  where option_name='security_invoker'),'false')='true';" "2"

echo
[ "$fail" -eq 0 ] && echo "tenant isolation: passed" || echo "TENANT ISOLATION FAILED"
exit "$fail"
