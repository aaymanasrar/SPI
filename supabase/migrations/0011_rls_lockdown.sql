-- 0011_rls_lockdown
-- Default-deny posture for every table in the public schema.
--
-- A Supabase project exposes PostgREST on the public internet using the
-- publishable key. Any table without row-level security is readable by anyone
-- holding that key — and the publishable key is, by design, not a secret.
--
-- Enabling RLS with NO policies denies all PostgREST access (anon and
-- authenticated roles) while leaving the application's server-side connection
-- unaffected: the owner and service_role bypass RLS.
--
-- Policies are added later, deliberately and per table, when a specific client
-- role genuinely needs direct access. Until then nothing is exposed.
--
-- This is applied now rather than retrofitted, because the failure mode of
-- forgetting it is silent public data exposure.

do $$
declare
  t record;
begin
  for t in
    select tablename
    from pg_tables
    where schemaname = 'public'
  loop
    -- ENABLE, not FORCE. FORCE would apply RLS to the table owner as well,
    -- locking out migrations and administrative maintenance. ENABLE already
    -- blocks the anon and authenticated roles that PostgREST uses, which is
    -- the actual exposure being closed here.
    execute format('alter table public.%I enable row level security', t.tablename);
  end loop;
end $$;
