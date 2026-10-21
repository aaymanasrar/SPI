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
