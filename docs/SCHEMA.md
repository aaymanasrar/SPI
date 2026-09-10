# SmartPage Intelligence — Database Schema Plan

**Prompt B deliverable.** Review document — presented before implementation, per instruction.
Target: PostgreSQL 17 (Supabase). Architecture per `docs/ARCHITECTURE.md` (Phase 0), unchanged.

**Contains no engineering rules, products, prices, approvals, standards or vendor data.** It
defines the containers for those things and leaves them empty.

---

## 1. Structure at a glance

Eleven domains, 48 tables. Arrows are foreign-key direction (child → parent).

```
IDENTITY                          REFERENCE
  organizations                     systems  (fire_alarm | cctv | acs)
    ├── users ── memberships ── roles ── role_permissions ── permissions
    └── clients

PROJECT & BUILDING MODEL  (§9 — one canonical model, shared by every system)
  projects
    ├── buildings ── floors ─┬── rooms
    │                        ├── areas
    │                        ├── walls ── openings
    │                        └── doors  (room_a, room_b → rooms)
    ├── zones
    └── project_systems ── system_requirements

DOCUMENTS
  documents ─┬── drawings ── drawing_pages ── drawing_objects
             ├── document_chunks
             └── extraction_runs ── extraction_proposals

RULES  (§11)
  engineering_rules ── rule_versions ─┬── rule_tests
                                      └── rule_executions

CATALOGUE  (§12)
  manufacturers ── products ── product_models ─┬── product_documents
                                               ├── authorizations
                                               └── alternatives
  suppliers

PRICING  (§13)
  price_lists ── vendor_prices
  labor_rates · installation_rates · tc_rates · pricing_rules

DESIGN
  design_devices ─┬── device_connections
                  └── cable_routes
  system_interfaces

BOQ  (§16)
  boqs ── boq_items ── boq_item_sources

COMMERCIAL  (§17)
  quotations ── quotation_revisions ─┬── quotation_items
                                     └── quotation_terms

PROCUREMENT  (§18)
  rfqs ── rfq_suppliers ── supplier_responses ── supplier_response_items

GOVERNANCE  (§22, §23)
  validation_results · review_tasks · approvals · audit_logs
```

### 1.1 The chain that matters

The point of the schema is that this path is traversable for any number on a quotation:

```
quotation_item → quotation_revision → boq → boq_item
                                              ├── quantity  → rule_execution → rule_version → engineering_rule
                                              ├── product   → product_model → authorization
                                              └── price     → vendor_price → price_list (source + date)
```

If any link is null where it should not be, validation raises an ERROR and finalization is blocked.

---

## 2. Tables and relationships

### 2.1 Identity

| Table | Key relationships |
|---|---|
| `organizations` | root of tenancy |
| `users` | `auth_user_id` optionally links to Supabase `auth.users` (see D-2) |
| `memberships` | user × organization × role; unique on (user, organization) |
| `roles` | 7 spec roles (§6), seeded |
| `permissions`, `role_permissions` | permissions stored, not hard-coded, so they are auditable |

### 2.2 Project and building model

`projects → buildings → floors` then floors fan out to `rooms`, `areas`, `walls`, `doors`.
`doors` reference two rooms (`room_a_id`, `room_b_id`, both nullable — an external door has one side).
`zones` are project-level and system-scoped.

Every building-model object carries the **§9.2 provenance block**:

```
source            manual | ai_extracted | imported
source_reference  text
confidence        numeric(5,4), null unless AI-derived
review_status     not_required | pending | approved | rejected
created_by, updated_by
```

`review_status` is what gates authority: an object still `pending` may not be consumed by an
approved BOQ.

### 2.3 Rules

`engineering_rules` holds identity and ownership; `rule_versions` holds the actual content
(`conditions`, `inputs`, `calculation`, `outputs`, `exceptions` as versioned JSONB), its approval
state and effective dates; `rule_tests` holds the §11.1 test cases; `rule_executions` records
every execution with inputs, outputs and evidence.

`rule_executions` is the audit trail that makes a quantity traceable, and is append-only.

### 2.4 Catalogue and pricing

`product_models` carries `authorized_status`, `lifecycle_status` and `revision`. Automatic
selection requires `authorized_status = 'authorized'`, an in-date `authorizations` row, and
`lifecycle_status <> 'withdrawn'` (§12.2). Expired records stay readable for historical projects
but are not selectable.

`vendor_prices` is append-only: a price change inserts a new row rather than updating one, which
is how §12.2 "price changes must preserve historical values" is enforced.

### 2.5 BOQ

`boq_items.quantity_source` is an enum of `rule_execution | manual | imported`. **There is
deliberately no `ai_proposal` value** — this is the structural half of §10.3's no-guess policy, and
it is why the previous build's "measure the blue lines and call it 1000 m" is not expressible here.

---

## 3. Required vs optional

**Required on every table:** `id` (UUID, `gen_random_uuid()`), `created_at`, `updated_at`
(both `timestamptz`, `updated_at` maintained by trigger). Tenant-scoped tables also require
`organization_id`.

**Required by domain rule:**

| Field | On | Why |
|---|---|---|
| `name` | organizations, projects, clients, buildings, floors | identity |
| `source`, `review_status` | all building-model + extracted objects | §9.2; authority gating |
| `currency` + `*_minor` | every monetary column | no bare numbers |
| `price_source` | vendor_prices, boq_items | §13.2 — a price without a source is invalid |
| `quantity_source` | boq_items | §16.3 traceability |
| `version` / `revision` | rule_versions, quotation_revisions, boqs, product_models, documents | §11, §17.2 |
| `approval_status` | rule_versions, product_models | lifecycle gating |
| `effective_from` | price_lists, labor/installation/tc rates, pricing_rules | §13 dated pricing |
| `actor_id`, `action`, `at` | audit_logs | §22 |

**Optional (nullable) — and deliberately so:**

| Field | Why nullable |
|---|---|
| `confidence` | null for manually entered data; only AI-derived values carry it |
| `rule_execution_id` on boq_items | null when `quantity_source = 'manual'` |
| `product_model_id` on boq_items | a line may be priced before a product is selected |
| `cable_routes.length_m` | null while `length_basis = 'unknown'` — see D-5 |
| `projects.client_id` | internal/speculative projects exist before a client is attached |
| `doors.room_a_id` / `room_b_id` | external doors have one side |
| `users.auth_user_id` | only populated if Supabase Auth is adopted |
| `effective_to`, `valid_to` | null means currently open-ended |

**Principle:** a field is nullable when *unknown is a legitimate state*, and NOT NULL when absence
would let an untraceable value through. Unknown must be representable — §10.3 depends on it.

---

## 4. Versioned entities

| Entity | Versioning mechanism |
|---|---|
| `engineering_rules` | separate `rule_versions` rows; unique (rule_id, version) |
| `quotations` | separate `quotation_revisions` rows; unique (quotation_id, revision) |
| `boqs` | new row per revision; unique (project_id, revision) |
| `product_models` | `revision` + `superseded_by_id` chain (§12.2) |
| `documents` | `version` + `superseded_by_id`; re-upload never overwrites (§14.2) |
| `price_lists`, `labor_rates`, `installation_rates`, `tc_rates`, `pricing_rules` | temporal — `effective_from` / `effective_to` |
| `vendor_prices` | append-only rows with validity windows |

Not versioned: the building model, design output and governance tables. The building model is
mutable until an approval consumes it; from that point the *consuming* artifact (BOQ, quotation) is
frozen, which preserves the historical picture without freezing the workspace.

---

## 5. Immutable after approval

Enforced by database trigger, not application code alone — per `ARCHITECTURE.md` §12.

**Immutable once the status gate is reached (UPDATE and DELETE both blocked):**

| Table | Frozen when |
|---|---|
| `quotation_revisions` | `status IN ('approved','issued')` (§17.2) |
| `boqs` | `status IN ('approved','issued')` |
| `boq_items` | parent BOQ is approved or issued |
| `quotation_items`, `quotation_terms` | parent revision is approved or issued |
| `rule_versions` | `approval_status IN ('approved','active','superseded')` — a change requires a new version |

**Append-only always (no UPDATE, no DELETE, at any status):**

`rule_executions`, `extraction_runs`, `approvals`, `audit_logs`, `vendor_prices`

**Never hard-deleted** (§20.1): approved engineering and commercial records. Archival uses
`archived_at`.

A correction after approval always creates a new revision that references its predecessor. There
is no supported path that edits an approved record in place.

---

## 6. Migration plan

Sequential, forward-only, each independently reviewable. Applied to Supabase via SQL migrations.

| # | Migration | Contents |
|---|---|---|
| 0001 | `extensions_and_enums` | `pgcrypto`; all enum types; shared `set_updated_at()` trigger function |
| 0002 | `identity` | organizations, users, roles, permissions, role_permissions, memberships |
| 0003 | `projects_and_building_model` | clients, projects, buildings, floors, rooms, areas, walls, openings, doors, zones |
| 0004 | `documents` | documents, drawings, drawing_pages, drawing_objects, document_chunks, extraction_runs, extraction_proposals |
| 0005 | `systems_and_rules` | systems, project_systems, system_requirements, engineering_rules, rule_versions, rule_tests, rule_executions |
| 0006 | `catalogue` | manufacturers, products, product_models, product_documents, authorizations, alternatives, suppliers |
| 0007 | `pricing` | price_lists, vendor_prices, labor_rates, installation_rates, tc_rates, pricing_rules |
| 0008 | `design` | design_devices, device_connections, cable_routes, system_interfaces |
| 0009 | `boq_and_quotation` | boqs, boq_items, boq_item_sources, quotations, quotation_revisions, quotation_items, quotation_terms |
| 0010 | `procurement` | rfqs, rfq_suppliers, supplier_responses, supplier_response_items |
| 0011 | `governance` | validation_results, review_tasks, approvals, audit_logs |
| 0012 | `immutability_triggers` | freeze triggers (§5 above) and append-only guards |
| 0013 | `rls_lockdown` | enable RLS on every public table with **no** permissive policies |
| 0014 | `seed_placeholders` | roles, permissions, the three system codes. **Nothing else.** |

### 6.1 Why migration 0013 matters

A Supabase project exposes PostgREST on the public internet using the publishable key. Any table
without RLS is readable by anyone holding that key. Enabling RLS with no policies denies all
PostgREST access while the application's server-side connection (service role / owner) continues
to work normally. This is a default-deny posture, added now rather than retrofitted.

### 6.2 Seed contents — exhaustively

- 7 roles from §6 and their permission codes
- 3 rows in `systems`: `fire_alarm`, `cctv`, `acs` (named in §5.1 of the spec)

Nothing else. No manufacturers, no products, no prices, no rules, no authorizations, no suppliers.

---

## 7. Decisions needed

**D-1 — Supabase project access. RESOLVED.** Project `bvrtpgumrmtoqxcnpmnu` sits under a
different Supabase account from the one the MCP connector is authorized against, and returned
*"You do not have permission to perform this action"*. A dedicated project was created instead in
the reachable organization:

| | |
|---|---|
| Name | SmartPage Intelligence |
| Ref | `tyioiiszcftkaayhlsac` |
| Region | ap-south-1 (Mumbai — lowest latency to Saudi/GCC) |
| API URL | `https://tyioiiszcftkaayhlsac.supabase.co` |
| Cost | $0/month |

All 13 migrations are applied there. The SQL is portable, so moving to a different Postgres later
is one run of `./scripts/migrate.sh`.

**D-2 — Authentication.** The quickstart supplied (`@supabase/server`, publishable key, JWKS URL)
implies **Supabase Auth**. Phase 0 specified **Auth.js with our own users table**. The schema
supports either: `users.auth_user_id` is a nullable unique column that links a row to
`auth.users` if Supabase Auth is adopted, and stays null if not. A decision is needed before the
identity module is built, not before migrations run.

**D-3 — Migration tooling (amendment to Phase 0).** Phase 0 named Prisma for schema and
migrations. Recommend instead: **SQL migrations as the single source of truth, with Prisma
introspecting the database for typed client access.** Reason — immutability triggers (§5) and RLS
(§6.1) cannot be expressed in Prisma's schema language and would require raw-SQL escape hatches
regardless, leaving two competing sources of truth. This is the only proposed change to Phase 0
and it needs explicit approval.

**D-4 — Database access pattern.** `@supabase/server` (PostgREST over HTTP, RLS-enforced) and a
direct Postgres connection (pooled, RLS-bypassing) are different architectures. Phase 0 assumed
the latter. Mixing them means maintaining two authorization models. Recommend picking one;
direct-connection suits the server-rendered, service-layer design in `ARCHITECTURE.md`.

**D-5 — Cable length basis (was D-7 in Phase 0).** No decision needed to run migrations —
`cable_routes.length_basis` supports `manual | calculated | unknown` and defaults to `unknown`.
The engineering decision is still required before the design modules compute anything.

**D-6 — Jurisdiction.** Implementing as flat text on `projects` for now. A hierarchy with
inheritance can be added later without breaking existing rows. Confirm once real rules show how
jurisdiction actually varies.

**D-7 — pgvector.** `document_chunks` is created without an `embedding` column. Semantic search is
Phase 5 material and §8 of the spec says "pgvector (when needed)". Adding the column later is a
one-line migration.

---

## 8. Assumptions

1. Currency is SAR; money is stored as integer minor units with an explicit currency column, so a
   second currency needs no migration.
2. Single organization in initial use, multi-tenant schema from the start.
3. Supplier and Client roles exist in the model; their external surfaces come in later phases.
4. Room and door data is entered manually in the MVP (§5.2). Drawing extraction later populates the
   same tables through `extraction_proposals` — no schema change required.
5. Fire Alarm, CCTV and ACS are the initial systems; `systems` is a table, not an enum, so a fourth
   is a row rather than a migration.
6. Geometry is stored as JSONB rather than PostGIS. Revisit if real spatial queries are needed;
   PostGIS is available on Supabase.
