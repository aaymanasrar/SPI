# Security actions outstanding

Things only you can do. Each says what is exposed and what closes it.

---

## S-1 — Rotate the Supabase keys committed in `.env.example`

**Status: open. Rotation is the only fix.**

`.env.example` is a committed file and held real values, not placeholders:

| Value | Exposure |
|---|---|
| `SUPABASE_SECRET_KEY` | **Bypasses RLS.** Full read/write to every table, as every tenant. |
| `SUPABASE_PUBLISHABLE_KEY` | Low risk by design, but RLS was only enabled for all tables in 0023. |
| `SUPABASE_URL` / `SUPABASE_JWKS_URL` | Project reference, so the project is identifiable. |
| `DATABASE_URL` | Held a value starting `sbp_`, which is a Supabase personal access token — an **account**-level credential, broader than a database password. |

It is in git history, in these commits:

```
1b5c3ef  Prompt B: schema migrations, validated against PostgreSQL 17
57f4e2f  Apply schema to Supabase and harden function search_path
37aeb98  Apply schema to the gmail-account Supabase project
```

The working copy now contains placeholders, **but that does not undo the
exposure.** The values are in every clone and in the reflog. Anyone who has had
the repository, at any point, has them.

**What to do:**

1. **Rotate the service-role / secret key** — Supabase dashboard → Project
   Settings → API Keys → roll `secret`. Do this first; it is the one that
   bypasses RLS.
2. **Revoke the personal access token** — Account Settings → Access Tokens.
   Any token beginning `sbp_` that appears in the table above.
3. **Change the database password** — Project Settings → Database.
4. Then update your local `.env`, which is gitignored and was never committed.

**History rewriting is your call and is not the fix.** Rotation is. If the
repository has never left your machine and has no remote, rewriting history
(`git filter-repo`) is worth doing *as well*; if it has been pushed or cloned,
rewriting achieves very little and rotation is the whole answer.

I did not rotate anything: I have no access to the Supabase dashboard, and
rolling a production key is not something to do to someone's project without
asking.

### Preventing the next one

Nothing in the repository currently stops a secret being committed. Worth
adding, in rough order of value: a `pre-commit` hook running `gitleaks` or
`detect-secrets`, and the same check in CI so it is not bypassable with
`--no-verify`. Not added here — a hook that rejects commits is a change to how
you work, so it should be your decision.

---

## S-2 — Two views bypassed RLS (fixed in 0024, needs applying)

**Status: fixed in the migration. You still have to apply it.**

0011 enabled row-level security on every table with no policies — default-deny.
Tables were sound. Views were not.

In PostgreSQL 15+ a view runs with the privileges of its **owner** unless created
`with (security_invoker = true)`. The owner here also owns the tables and
bypasses RLS, and Supabase's default privileges grant `select` on new objects in
`public` to `anon` and `authenticated`. So `engine_readiness` and
`product_variant_traps`, created in 0020 and 0021, read straight through the RLS
protecting `product_models`, `products` and `manufacturers` — for anyone holding
the publishable key, which is served to browsers by design.

Reproduced on a throwaway table, PostgreSQL 17.11:

```
--- as owner (the server-side connection) ---
owner sees 2
--- as anon (the publishable key) ---
anon via table       : 0
anon via leaky_view  : 2   <-- RLS BYPASSED
anon via safe_view   : 0   <-- RLS applied
```

**What was exposed:** part numbers, model names, verification status, PoE budgets
and supply voltages for the whole authorized product catalogue, across every
tenant. **No** price, rate or margin column appears in either view, so the
commercial visibility boundary (ARCHITECTURE §6.3) was not crossed.

**Second defect, same views:** neither selected or filtered `organization_id`,
so they were cross-tenant by construction — a server-side caller could not scope
them to one organization because the column was not there. Both now carry it,
reached through `manufacturers`.

### What to do

```
# apply 0024 to the project
psql "$DATABASE_URL" -f supabase/migrations/0024_view_security_and_rls_guard.sql

# then confirm the posture
scripts/check-rls "$DATABASE_URL"
```

To see the exposure for yourself before applying, with your publishable key:

```
curl -s "https://<project-ref>.supabase.co/rest/v1/engine_readiness?select=*&limit=1" \
  -H "apikey: <publishable-key>"
```

Rows come back before 0024; after it, an empty array (`security_invoker` denies
the rows and an explicit `revoke` denies the object).

### The durable fix

`scripts/check-rls` asserts the whole posture against any database and exits
non-zero on any failure. 0024 also runs the same assertions as part of itself, so
a future table or view created without protection **fails the migration** instead
of quietly exposing data. Verified to fail for: a table without RLS, a view
without `security_invoker`, an unreachable database, and an empty one.

This is the second time a one-shot posture has drifted — 0011's loop missed the
two tables 0017 created, which went unprotected until 0023. Hence a check that
runs rather than a loop that ran once.

---

## S-3 — Vercel environment variable names did not match the code

**Status: code and `.env.example` fixed. Check your Vercel project.**

`src/lib/supabase.ts` and `src/proxy.ts` read `NEXT_PUBLIC_SUPABASE_URL` and
`NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`. `.env.example` defined `SUPABASE_URL`
and `SUPABASE_PUBLISHABLE_KEY`. Neither name matched, and both call sites use a
`!` non-null assertion, so TypeScript was satisfied and `createServerClient`
would receive `undefined` at runtime — authentication failing with an unhelpful
error.

Both reads are server-side, so the `NEXT_PUBLIC_` prefix bought nothing and
pushed the project reference into every client bundle. The code now reads the
unprefixed names, and `.env.example` documents them.

**In Vercel, the variables must be named exactly:**

```
SUPABASE_URL
SUPABASE_PUBLISHABLE_KEY
SUPABASE_SECRET_KEY          # server-side only; never NEXT_PUBLIC_
SUPABASE_JWKS_URL
DATABASE_URL
CRAFT_SERVICE_URL
```

If a browser-side Supabase client is ever added it will need `NEXT_PUBLIC_`
copies of the first two — and only those two.

### One thing to decide about Vercel

`CRAFT_SERVICE_URL` points at the Python engines service, which is a long-running
process that shells out to LibreOffice. **It cannot run on Vercel's serverless
functions.** On a Vercel deployment the engines must be hosted separately — a
container host such as Fly, Render or Cloud Run — with `CRAFT_SERVICE_URL`
pointing at it over a private network, since the service has no authentication of
its own. Until then, every `craft.*` tool will fail with "the calculation service
is not responding" while the rest of the application works.
