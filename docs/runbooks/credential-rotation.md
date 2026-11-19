# Runbook — rotating the exposed Supabase credentials

`.env.example` was committed holding real values. They are in three commits of
history (`1b5c3ef`, `57f4e2f`, `37aeb98`) and therefore in every clone. The
working copy now holds placeholders; **that does not undo the exposure.**
Rotation is the only fix.

Nothing in this runbook has been performed. I have no dashboard access, and
credential rotation is not something to do to someone's project unasked.

## What was exposed

| Value | Scope | Priority |
|---|---|---|
| `SUPABASE_SECRET_KEY` | **Bypasses RLS.** Read/write to every table as every tenant. | 1 |
| `SUPABASE_ACCESS_TOKEN` (`sbp_…`) | **Account level**, not project level. Broader than the database. | 2 |
| Database password (in `DATABASE_URL`) | Direct Postgres access | 3 |
| `SUPABASE_PUBLISHABLE_KEY` | Public by design; only matters because RLS was incomplete until 0024 | 4 |
| `SUPABASE_URL`, project ref | Identifies the project | — |

## Checklist

Tick each as it is done; the verification column is what proves it.

- [ ] **1. Roll the secret / service-role key.**
      Dashboard → Project Settings → API Keys → roll `secret`.
      *Verify:* the old key returns 401 against
      `GET {URL}/rest/v1/organizations` with `apikey: <old secret>`.
- [ ] **2. Revoke the account access token.**
      Account Settings → Access Tokens → revoke the `sbp_…` token.
      *Verify:* `curl -H "Authorization: Bearer <old token>" https://api.supabase.com/v1/projects`
      returns 401.
- [ ] **3. Change the database password.**
      Project Settings → Database → reset.
      *Verify:* `psql` with the old connection string is refused.
- [ ] **4. Roll the publishable key** (optional, lower value).
      *Verify:* the old key returns 401.

## Dependent services to update, in this order

Rotating first and updating second causes an outage. Rotating second causes a
window where the old key still works. Accept the outage.

- [ ] **Local `.env`** — gitignored, never committed. Update all four values.
      *Verify:* `scripts/verify-remote --db "$DATABASE_URL"` connects.
- [ ] **Vercel environment variables** — Project → Settings → Environment
      Variables, for every environment (Production, Preview, Development).
      The names must be exactly those in `.env.example`:
      `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY`,
      `SUPABASE_JWKS_URL`, `DATABASE_URL`, `CRAFT_SERVICE_URL`.
      They previously did **not** match what the code read — see
      `docs/SECURITY-ACTIONS.md` S-3.
      *Verify:* `vercel env ls`, then redeploy, then sign in on the deployed app.
- [ ] **The engines container host**, once one exists — `CRAFT_SERVICE_URL` is
      consumed by the Next.js app, not by the engines, so the engines need no
      Supabase credentials at all. If any are set there, remove them.
- [ ] **Any CI** holding Supabase secrets.
- [ ] **Local shells and anything that sourced `.env`** — open terminals keep
      the old values in their environment.

## After rotation, verify the project itself

```sh
scripts/verify-remote --db "$DATABASE_URL" \
                      --url https://<ref>.supabase.co \
                      --publishable sb_publishable_<new>
```

That runs migration history, RLS posture, view permissions, tenant isolation,
the data bootstrap check, and a live PostgREST exposure test against the
publishable key. It fails closed: if it cannot connect, or the exposure check is
not given a key, it reports failure rather than success.

Keep the output with the date. Until it has been run against the remote, remote
security is **unverified**, not **passing**.

## Also outstanding

Rewriting git history is a separate question and is **not** the fix. If the
repository has never been pushed or cloned, `git filter-repo` is worth doing as
well. If it has, rotation is the whole answer and history rewriting achieves
very little.

Nothing in the repository currently prevents the next secret being committed.
A `gitleaks` or `detect-secrets` hook plus the same check in CI would. Not added
here: a hook that rejects commits changes how you work, so it is your call.
