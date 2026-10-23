# Runbook — the unvalidated constraint on `craft_operations` in `spi_dev`

## What is wrong

`spi_dev` holds two rows in `craft_operations`. One of them could not be
inserted today.

| id | tool | status | findings | violates 0025 |
|---|---|---|---|---|
| `212d541d…` | `t` | `ok` | `[{"code":"X","severity":"blocker"}]` | **yes** |
| `7056b483…` | `probe-ok` | `ok` | `[{"code":"X","severity":"review"}]` | no |

Both are test probes, not records of real work: `engine_version = 'v'`,
`actor_type = 'system'`, tool names `t` and `probe-ok`.

## Why it happened

Exactly, in order:

1. Migration 0025 was first written with the blocker check expressed as a
   subquery. PostgreSQL forbids subqueries in `CHECK`, so the whole migration
   aborted at that statement and **no constraint was created**.
2. A probe insert was then run to test the constraint. With no constraint
   present it succeeded, writing row `212d541d…` — `status='ok'` carrying a
   blocker finding, the exact combination 0025 exists to forbid.
3. 0025 was rewritten using the `@>` containment operator, which is immutable
   and therefore legal in a `CHECK`. `ADD CONSTRAINT … NOT VALID` succeeded,
   because `NOT VALID` deliberately skips existing rows.
4. `VALIDATE CONSTRAINT` then failed against row `212d541d…` and left the
   constraint `convalidated = false`.

So the defect is mine, from testing against a live database instead of a
throwaway one.

## What it does and does not affect

- **New writes are protected.** `NOT VALID` still enforces the check on every
  insert and update. Verified: a blocker marked `ok` is rejected, a review
  finding is accepted.
- **The constraint is unvalidated in `spi_dev` only.** A fresh build applies all
  25 migrations and validates cleanly — confirmed on an empty database.
- **No production or remote database is affected.** Neither has been reached.

## Repair options

`craft_operations` is append-only by trigger (`forbid_mutation`), so `DELETE` is
refused. That is the table doing its job.

### Option A — leave it, document it *(recommended)*

The rows are test artifacts in a development database. The constraint protects
every future write. Nothing downstream reads `craft_operations` yet.

Cost: `spi_dev` keeps an unvalidated constraint, so `\d craft_operations` shows
`NOT VALID` there and nowhere else. This document is the explanation.

### Option B — rebuild `spi_dev`

Clean, and it validates the constraint. **But see the bootstrap gap below:** the
migrations alone do not reproduce this database's contents, so the organisation
and user must be recreated first or the 181 rules and 45 product models will not
load.

### Option C — authorised surgical removal

Disable the append-only trigger, delete the two rows, re-enable, validate.

**This defeats the control it is removing rows under.** The trigger exists so
that no path deletes an audit record. A procedure that disables it is a path.
It is listed for completeness and is not recommended; if it is ever used it
needs written authorisation recorded against the two row ids, because afterwards
nothing in the database shows that anything was removed.

`scripts/repair-craft-operations` implements B and C. It refuses to do anything
without `--authorized` and prints what it would do otherwise.

## The bootstrap gap found while investigating this

A database built from all 25 migrations and nothing else contains:

```
organizations 0   users 0   rule_versions 0   product_models 0
```

The seed migrations (0015–0021) loop `for o in select id from organizations`.
With no organisation they insert nothing and report success. `spi_dev` has 181
rules and 45 models only because an organisation was created by hand before
those migrations ran.

**The migration set therefore does not produce a usable database.** Anyone
applying it to a new environment — including the remote Supabase project — gets
an empty rules library and an empty catalogue, with no error to indicate it.

This needs a bootstrap migration or a documented first step that creates the
organisation. It is not fixed here because which organisation, with what name
and slug, is SmartPage's decision, not mine.

## Validation after any repair

```sh
scripts/check-rls "$DATABASE_URL"
scripts/tests/tenant-isolation.test.sh "$DATABASE_URL"
psql "$DATABASE_URL" -c "\
  select conname, convalidated from pg_constraint \
   where conname = 'craft_operations_blocker_not_ok'"
psql "$DATABASE_URL" -c "\
  select count(*) as should_be_zero from craft_operations \
   where status = 'ok' and findings_json @> '[{\"severity\":\"blocker\"}]'::jsonb"
```
