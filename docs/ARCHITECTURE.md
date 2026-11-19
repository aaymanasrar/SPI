# SmartPage Intelligence — Technical Architecture

**Phase 0 deliverable.** Corresponds to Prompt A of the Master Build Specification v1.0 §28.
Status: draft for review by SmartPage engineering management.

---

## 0. What this document is

This is the technical architecture for SmartPage Intelligence, derived from the Master Build
Specification v1.0. Per Prompt A it defines repository structure, application modules, database
schema, service boundaries, authentication/RBAC, file handling, AI orchestration, validation
architecture and testing strategy, and it records assumptions and unresolved decisions.

**What this document deliberately does not contain**, per §26 and §27:

- No engineering rules. Not one. Rules are SmartPage engineering data (Appendix A), not
  something this architecture may invent.
- No product data, manufacturer approvals or model numbers.
- No prices, labour rates or margins.
- No coverage, spacing, storage or bandwidth assumptions.

Where those values are required, this document defines the *shape of the container* and leaves the
container empty. Section 16 lists what must be supplied before the corresponding module can do
real work.

---

## 1. Architectural position

The whole design follows from one sentence in §32:

> Do not build a chatbot that makes BOQs. Build an engineering intelligence system that uses AI.

Concretely that means a fixed chain of custody for every number that reaches a customer:

```
AI            proposes and interprets   — never authoritative
Building Model  holds project truth     — one canonical model, shared by all systems
Rules Engine    calculates              — deterministic, versioned, tested
Catalogue       constrains selection    — only active, authorized products
Pricing Engine  computes commercials    — every price carries source + date
Validation      checks                  — ERROR blocks finalization
Engineer        approves                — nothing is issued without this
```

Each arrow is a **boundary that must be enforced in code, not by convention**. The failure mode this
architecture exists to prevent is a plausible-looking number with no traceable origin. Section 4
turns these boundaries into enforced module dependency rules; §8 turns the first one into a
proposal/promotion flow.

### 1.1 The invariant

> Every engineering-impacting value in the system can answer: *where did you come from?*

For a quantity, that answer is a rule ID + version + the building-model objects it consumed.
For a product, an active catalogue record. For a price, a price source and date. For an
AI-extracted value, an extraction run plus the human who confirmed it. Any value that cannot
answer is a defect, not a rounding detail.

---

## 2. Stack decisions

| Concern | Decision | Rationale | Alternative considered |
|---|---|---|---|
| App framework | Next.js (App Router) + TypeScript | §8 recommends it; server actions keep mutations server-side, which suits "authorize every mutation" (§21.1) | Remix; separate React SPA + Node API |
| Database | PostgreSQL | §8; the model is heavily relational with FK integrity, enums and audit requirements | None seriously — the data model rules out a document store |
| Schema/migrations | Prisma | §26 requires migrations; Prisma's migration tooling and generated types are the most conventional choice for handover to a technical team | Drizzle (SQL-first, lighter); revisit if raw-SQL control becomes limiting |
| Background jobs | pg-boss | Document/vision/CAD work and long AI jobs must not block requests (§8 Workers). pg-boss uses the Postgres we already run — no Redis to operate | BullMQ + Redis, if job volume later justifies the extra infrastructure |
| Object storage | S3-compatible behind a `StorageProvider` interface | §8 object storage, §22 signed/time-limited access, §14.2 originals preserved | Local filesystem for development only |
| Auth | Auth.js with database sessions | Multi-tenant isolation (§22) and 7 custom roles (§6) need full control over the session/role model | Clerk or a managed auth provider — rejected to avoid coupling tenancy to a vendor |
| AI providers | Internal adapter, provider-agnostic | §10 defines capabilities, not vendors. Model availability and pricing change frequently | — |
| Testing | Vitest (unit/integration) + Playwright (E2E) | §26 requires tests for every deterministic calculation | — |

### 2.1 Modular monolith, not microservices

§8's service tree lists *logical* services. This architecture implements them as **modules inside one
deployable application**, plus one worker process. Module boundaries are enforced by dependency
rules (§4.1) and typed interfaces, so any module can later be extracted to its own service without
rewriting its callers. Splitting into network services now would add operational cost and
distributed-transaction problems with no benefit at this stage.

### 2.2 Local infrastructure note

Neither PostgreSQL nor Docker is currently installed on the development machine. Before Phase 0
implementation begins, one of the following must be chosen — see §16, D-1.

---

## 3. Repository structure

```
smartpage-intelligence/
├── docs/
│   ├── ARCHITECTURE.md              this document
│   ├── MASTER_SPEC_v1.0.pdf         governing specification
│   ├── decisions/                   ADRs, numbered, append-only
│   └── data-requests/               Appendix A tracking (§17)
│
├── prisma/
│   ├── schema.prisma
│   ├── migrations/
│   └── seed/                        non-engineering placeholders ONLY (Prompt B)
│
├── src/
│   ├── app/                         Next.js routes
│   │   ├── (auth)/
│   │   ├── (app)/
│   │   │   ├── projects/[id]/       overview, documents, building, systems,
│   │   │   │                        design, validation, boq, pricing,
│   │   │   │                        quotations, rfqs, audit   (§19.2)
│   │   │   ├── catalogue/
│   │   │   ├── rules/
│   │   │   └── admin/
│   │   └── api/
│   │
│   ├── modules/                     the service layer of §8
│   │   ├── identity/                users, orgs, memberships, RBAC
│   │   ├── projects/                projects, clients
│   │   ├── documents/               upload, storage, classification
│   │   ├── building/                canonical Building Intelligence Model (§9)
│   │   ├── systems/                 system selection + requirements
│   │   ├── rules/                   rule storage, lifecycle, execution (§11)
│   │   ├── design/                  per-system design modules
│   │   │   ├── fire-alarm/
│   │   │   ├── cctv/
│   │   │   └── acs/
│   │   ├── catalogue/               products, authorizations, datasheets (§12)
│   │   ├── pricing/                 cost model, price sources (§13)
│   │   ├── boq/                     BOQ generation (§16)
│   │   ├── quotation/               quotations, revisions (§17)
│   │   ├── procurement/             RFQ (§18) — later phase, modelled early
│   │   ├── validation/              validation engine (§23)
│   │   ├── ai/                      AI orchestration (§10)
│   │   └── audit/                   audit log, approvals
│   │
│   ├── lib/                         cross-cutting: db, storage, auth, errors, money
│   └── types/
│
├── workers/
│   ├── document-processing/
│   ├── vision-extraction/
│   ├── cad-extraction/
│   └── index.ts
│
└── tests/
    ├── unit/
    ├── integration/
    ├── e2e/
    └── ground-truth/                replay harness (§24)
```

---

## 4. Module boundaries

### 4.1 Dependency rules (enforced, not advisory)

These are checked in CI by a dependency linter. A violation fails the build.

1. **`ai/` may not write to authoritative tables.** It writes only to `*_proposals` and
   `extraction_runs`. This is the code-level expression of §9.2 and §10.1.
2. **`design/` may not compute quantities directly.** It assembles inputs, calls `rules/`, and
   records results with rule references. A hard-coded number inside a design module is the exact
   defect §11 exists to prevent.
3. **`boq/` may not select products.** It consumes design output and asks `catalogue/` to resolve
   products; `catalogue/` refuses inactive or unauthorized records (§12.2).
4. **`pricing/` may not invent a price.** Every price resolves through the §13.2 hierarchy or the
   calculation fails loudly.
5. **No module writes an approved/issued record in place.** Corrections create revisions (§17.2,
   §20.1).
6. **UI components contain no business logic** (§26). Routes call module services; modules own rules.

### 4.2 Service interface shape

Every module exposes a typed service with explicit inputs and a result type that carries
provenance. The shared result envelope:

```ts
type EngineeringResult<T> = {
  value: T;
  sources: SourceRef[];          // rule ids+versions, document refs, catalogue ids
  assumptions: Assumption[];
  unknowns: Unknown[];           // §10.3 — populated instead of guessing
  warnings: Warning[];
  requiresEngineerReview: boolean;
};
```

`unknowns` being non-empty is a normal, expected outcome. Code that quietly drops unknowns to
produce a cleaner number is a defect.

---

## 5. Database schema

Schema by domain, following §20. Every table carries `id` (UUID), `created_at`, `updated_at`;
tenant-scoped tables carry `organization_id`.

### 5.1 Identity

```
organizations        id, name, status
users                id, email, name, status, last_login_at
memberships          id, user_id, organization_id, role, status
roles/permissions    see §6 — stored, not hard-coded, so permissions are auditable
sessions             Auth.js database sessions
```

### 5.2 Projects and the building model (§9)

```
clients              id, organization_id, name, contact
projects             id, organization_id, client_id, name, code, jurisdiction,
                     status, created_by
buildings            id, project_id, name
floors               id, building_id, name, level, elevation
rooms                id, floor_id, name, code, room_type, area, height,
                     occupancy, source, source_reference, confidence, review_status
areas                id, floor_id, name, geometry
doors                id, floor_id, room_a_id, room_b_id, code, type, width,
                     fire_rating, security_level, source, source_reference,
                     confidence, review_status
walls                id, floor_id, geometry, type
openings             id, wall_id, type, geometry
zones                id, project_id, system, name, purpose
drawing_objects      id, drawing_page_id, object_type, geometry, extracted_value,
                     confidence, review_status
design_devices       id, project_id, system, device_type, room_id, location,
                     rule_reference, source_design_objects, status
cable_routes         id, project_id, system, from_device_id, to_device_id,
                     length_basis, length, calculation_reference
system_interfaces    id, project_id, system_a, system_b, event, action, status
                     (§15.2 — proposed | approved | implemented)
```

Every object carries the §9.2 metadata block: `source`, `source_reference`, `confidence`,
`status`, `created_by`, `updated_by`, `review_status`. **`review_status` gates authority**: an
object with `review_status = 'pending'` may not be consumed by an approved BOQ.

### 5.3 Documents

```
documents            id, project_id, filename, content_type, byte_size, checksum,
                     storage_key, classification, uploaded_by, version
drawings             id, document_id, discipline, sheet_number, revision
drawing_pages        id, drawing_id, page_number, render_key, width, height
document_chunks      id, document_id, page, ordinal, text, embedding
extraction_runs      id, document_id, provider, model, prompt_version, input_hash,
                     started_at, finished_at, status, raw_output, cost
```

`documents.storage_key` points at the **immutable original** (§14.2). Derived artifacts —
renders, extracted text — are separate rows referencing it. Originals are never overwritten;
a re-upload creates a new version.

### 5.4 Systems and rules (§11)

```
systems              id, code, name                       (Fire Alarm, CCTV, ACS)
project_systems      id, project_id, system_id, status
system_requirements  id, project_system_id, key, value, source

engineering_rules    id, rule_id, system_id, name, jurisdiction,
                     standard_reference, priority, owner, status
rule_versions        id, rule_id, version, conditions, inputs, calculation,
                     outputs, exceptions, effective_from, effective_to,
                     approval_status, approved_by, approved_at
rule_tests           id, rule_version_id, name, given_inputs, expected_outputs
rule_executions      id, project_id, rule_version_id, inputs, outputs,
                     executed_at, evidence
```

`rule_executions` is the audit trail that lets any quantity be traced back to the exact rule
version and inputs that produced it. It is append-only.

### 5.5 Catalogue (§12)

```
manufacturers        id, name, status
products             id, manufacturer_id, product_family, category, description,
                     status
product_models       id, product_id, model, technical_specifications,
                     approval_status, authorized_status, authorized_regions,
                     lifecycle_status
product_documents    id, product_model_id, document_id, doc_type
                     (datasheet, compliance, warranty)
authorizations       id, product_model_id, authority, reference, valid_from,
                     valid_to, evidence_document_id
alternatives         id, product_model_id, alternative_model_id, approved_by,
                     approved_at, notes
```

Automatic selection filters on `authorized_status = 'authorized'` **and** an in-date
authorization **and** `lifecycle_status != 'withdrawn'` (§12.2). Expired records remain readable
for historical projects but are not selectable.

### 5.6 Pricing (§13)

```
price_lists          id, organization_id, name, currency, effective_from,
                     effective_to, status
vendor_prices        id, price_list_id, product_model_id, unit_price,
                     price_source, price_valid_from, price_valid_to, lead_time
labor_rates          id, organization_id, activity, unit, rate, effective_from
installation_rates   id, organization_id, item_type, unit, rate, effective_from
tc_rates             id, organization_id, activity, unit, rate, effective_from
pricing_rules        id, organization_id, kind (overhead|margin|logistics),
                     basis, value, effective_from, approved_by
```

All monetary values are stored as integer minor units with an explicit currency. No floats.

### 5.7 BOQ, quotation, procurement, governance

```
boqs                 id, project_id, revision, status, generated_at
boq_items            id, boq_id, system, category, description, manufacturer,
                     model, unit, quantity, rule_reference, price_source,
                     unit_cost, installation_cost, tc_cost, selling_price,
                     notes, status
boq_item_sources     id, boq_item_id, source_type, source_id
                     (design_device | rule_execution | document | manual)

quotations           id, project_id, boq_id, number, status
quotation_revisions  id, quotation_id, revision, content, status, approved_by,
                     approved_at, issued_at, immutable
quotation_items      id, quotation_revision_id, description, scope, amount
terms                id, quotation_revision_id, kind, body

rfqs                 id, project_id, boq_id, status, created_by
rfq_suppliers        id, rfq_id, supplier_id, sent_at, responded_at
supplier_responses   id, rfq_supplier_id, document_id, received_at
supplier_response_items id, supplier_response_id, boq_item_id, extracted_value,
                     confidence, confirmed_by, confirmed_at

validation_results   id, project_id, layer, severity, code, message,
                     subject_type, subject_id, resolved_at
review_tasks         id, project_id, kind, subject_type, subject_id,
                     assigned_role, status, resolved_by
approvals            id, subject_type, subject_id, role, approved_by,
                     approved_at, signature_note
audit_logs           id, organization_id, actor_id, action, subject_type,
                     subject_id, before, after, at, ip
```

### 5.8 Database principles (§20.1)

UUID keys; `created_at`/`updated_at` everywhere; soft-delete/archive where history matters;
approved engineering and commercial records are never hard-deleted; FKs and constraints on;
status enums as Postgres enums or reference tables; source references stored for every generated
value. Immutability of approved revisions is enforced by trigger, not only in application code.

---

## 6. Identity, tenancy and RBAC

### 6.1 Tenancy

Every tenant-scoped query is filtered by `organization_id`. This is enforced in a repository layer
rather than left to individual call sites; Postgres row-level security is a candidate hardening
step once the access patterns settle (see §16, D-4).

### 6.2 Roles (§6)

Seven roles: Super Admin, Engineering Manager, Pre-Sales Engineer, Estimator, Procurement,
Supplier, Client. Roles map to named permissions stored in the database, so the permission set is
inspectable and auditable rather than scattered through code.

Approval-state transitions (§6.1) are permission-checked individually:
`DRAFT → AI GENERATED → ENGINEER REVIEW → CORRECTIONS → VALIDATED → APPROVED → ISSUED`.
Only permitted roles may perform a given transition, and every transition writes an `approvals`
and an `audit_logs` row.

### 6.3 Commercial visibility boundary

§13.3, §21.1 and §29.1 all require that internal cost and margin never reach client-facing users.
Hiding these in the UI is insufficient. Enforcement is at serialization: each resource has
role-specific DTOs, and the client-facing DTO has no cost or margin fields to leak. A test asserts
that no client-role API response contains cost or margin keys.

---

## 7. File handling

- Uploads are streamed to object storage; the database stores metadata plus a checksum.
- The original file is immutable (§14.2). Re-uploading produces a new version; nothing is
  overwritten.
- Derived artifacts (page renders, extracted text, thumbnails) are separate objects that reference
  the original.
- Access is via short-lived signed URLs (§22); files are never public.
- Type and size are validated server-side; archives are expanded with limits on entry count,
  total expanded size and path traversal.
- Heavy parsing happens in workers, never in the request path.

The **craft engines** (§18) are the read/write half of this: they consume originals from object
storage and emit new objects, never mutating what was uploaded.

**Carried forward from earlier work:** PDF text extraction, table extraction and page rendering
for drawings that carry no extractable text were built and proven against a real Aramco package.
That work is applicable at Phase 5–6 and should be reused rather than rediscovered. It is *not*
part of Phases 0–4.

---

## 8. AI orchestration (§10)

### 8.1 Every AI call returns the §10.2 contract

```ts
{ result, confidence, sources, assumptions, unknowns, warnings,
  requires_engineer_review }
```

Enforced by schema-constrained structured output. A response that cannot be parsed into this shape
is an error, not a fallback to free text.

### 8.2 Proposal and promotion

AI output never lands in an authoritative table. It writes a proposal row; a permitted human
promotes it. Promotion records who, when, and what changed between proposed and accepted values.
This is the mechanism behind §9.2 and Prompt L's "reviewable before becoming authoritative".

```
extraction run → *_proposals (confidence, sources) → human review → authoritative row
                                                   ↘ rejected (retained for audit)
```

### 8.3 Provider adapter

One internal interface; provider implementations behind it. Requirements learned from the previous
build: model identifiers change and get decommissioned; providers differ in how they carry images
and system instructions; some models spend their output budget on internal reasoning and truncate
structured output unless explicitly configured. Model IDs belong in configuration, never in code,
and every call records provider, model and prompt version in `extraction_runs`.

### 8.4 No-guess enforcement (§10.3)

Prompt-level instruction is necessary but insufficient — the previous build proved a model will
still infer a quantity from a drawing when told not to. So it is also enforced structurally:

- A quantity whose provenance is an AI inference cannot become a BOQ quantity. `boq_items.quantity`
  accepts a rule execution or a confirmed manual entry as its source, and rejects an AI proposal.
- AI-derived values with confidence below the configured threshold create a `review_task`.
- Material unknowns raise a validation result that blocks finalization.

---

## 9. Rules engine (§11)

### 9.1 Rules are data

Rules are versioned rows with an approval lifecycle
(`DRAFT → ENGINEER REVIEW → APPROVED → ACTIVE → SUPERSEDED`), not code and not prompts. An
Engineering Manager can author and approve a rule without a deployment.

### 9.2 Execution (§11.3)

Resolve jurisdiction and project requirements → load active approved rules → collect inputs →
check for missing/invalid inputs → execute deterministically → store rule ID, version and inputs →
emit result plus validation evidence → flag exceptions for engineer review.

Execution is pure: same inputs and same rule version always produce the same outputs. No clock, no
randomness, no network calls inside a rule. This is what makes ground-truth replay (§24) meaningful.

### 9.3 Conflict handling (§11.4)

When two active rules conflict, the engine never picks silently. It identifies the conflict,
surfaces both sources, and applies a precedence policy **only where that precedence has been
explicitly configured and approved**. Otherwise it raises a review task and halts that calculation.

### 9.4 Deliberately deferred: the expression language

The rule *storage, lifecycle, versioning, testing and execution framework* is specified here. The
**expression language** for `conditions` and `calculation` is deliberately not finalized.

Reason: designing a DSL against imagined rules would either be too weak for SmartPage's real rules
or so general that it becomes arbitrary code execution with no auditability. The honest sequence is
to see 10–20 real SmartPage rules first, then design the smallest language that expresses them.

Interim position: the framework treats `conditions` and `calculation` as opaque versioned payloads
with a pluggable evaluator, so the evaluator can be implemented once real rules exist without
touching storage, lifecycle or audit. See §16, D-2.

**Status: the precondition is now met.** Migrations 0015-0017 encode 137 rules — the ELV &
Telecom Installation Rule Guide Book, additions from ANSI/TIA/EIA-568-B, and the Saudi security
surveillance camera law. They are stored, tagged, traceable and versioned, and none of them
executes: every version is `draft` and every payload carries `"evaluator": "unassigned"`. The one
exception is X-06, whose evaluator is `enforced_in_sql` because it is implemented as a trigger
(§9.5). Designing the expression language against these 137 rules — rather than against imagined
ones — is now unblocked and is the next piece of work here. The shapes the real rules take are
`limit`, `spacing`, `clearance`, `coverage`, `selection`, `budget`, `interface`, `checklist` and
`governance`; all but one are constraints that emit a validation result rather than calculations
that emit a quantity, which is itself a finding the deferral was meant to surface. The exception is
A-14 (minimum two outlets per work area), which emits `{"emits":"quantity","unit":"outlet"}` — the
first rule in the set that can put a number on a BOQ line by itself.

### 9.5 Conflict registry and precedence (§11.4)

§9.3 says the engine never resolves a conflict silently. Until the fourth source document arrived
that was cheap to honour, because no two documents disagreed. The SPT Engineering Rules Library
(80 rules, migration 0017) overlaps the earlier three heavily and disagrees with them in three
places, so the requirement is now load-bearing.

`rule_relationships` records how a rule from one source relates to a rule from another:
`agrees`, `refines`, `resolves`, `supersedes` or `conflicts`, each with a note. It is enforced, not
documentation: `forbid_approving_conflicted_rule()` refuses to move a rule version to
`approved`/`active` while that rule sits on an unresolved `conflicts` or `supersedes` row — **on
either side**. Resolving requires both `resolved_at` and a `resolution_note`.

The worked case is fibre bend radius. `SPT-SC-04` states a flat 20× under tension; `ELV-A-02` was
corrected on 24 Sep against the supplied 568-B text to 20× interbuilding, 15× intrabuilding. Both
are plausible, both are tagged CODE, and without the registry both would have been approvable.

`rule_precedence_policy` stores an ordered list of authorities, rank 1 highest. The SPT library
supplies the first one the platform has ever had. It is seeded **unapproved**, because §9.3 permits
precedence to resolve a conflict only where it has been explicitly configured *and* approved.
Note what its order implies — a project SOW outranks the Saudi Building Code and NCA — which is
defensible for scope but cannot override a statutory duty. Approving it should carry that
carve-out.

### 9.6 Rule confidence and the scope gate (§11.4, §16)

Real engineering rules do not all carry the same authority, and the difference is not cosmetic.
`engineering_rules.confidence` (`code` / `spec` / `local`, migration 0014) records it:

- `code` — stated in a published standard. May bind on its own.
- `spec` — project or client practice. Binds only where the SOW or drawing calls it out.
- `local` — one jurisdiction or regulator. Never carried across borders unchecked.

The column is `not null`, so an untagged rule is not representable. `forbid_unsupported_scope()`
enforces the consequence at the transition into `validated`, `approved` or `issued`: a BOQ item
whose quantity traces through `rule_executions` to a `spec` or `local` rule must carry a
`boq_item_sources` row of type `sow_clause`, `drawing` or `client_standard`, or the transition is
rejected and the offending items are named.

This is the structural counterpart to the §10.3 no-guess policy. That policy stops an *AI*
inference becoming a quantity; this one stops a *real but non-binding* rule doing the same. The
worked example is C-01: metallic conduit for perimeter cameras is a genuine SmartPage practice and
a common over-pricing trap, and it cannot reach an approved BOQ without a clause behind it.

Alongside it, `source_document`, `source_rule_id`, `source_verified` and `verification_note` record
where a rule came from and whether that source was actually read. An unverified rule must say what
is missing — a check constraint requires the note.

---

## 10. Pricing and commercial (§13)

Cost model per §13.1: material + accessories + cable/conduit + installation labour +
configuration/programming + testing & commissioning + engineering + logistics + overhead + margin
= selling price. Each component is a separate stored line so the build-up is inspectable.

Price resolution follows §13.2 strictly: current approved SmartPage/vendor price → approved
supplier quotation linked to an RFQ → approved internal price list → manual override with reason
and audit log. **There is no fifth step.** If none resolves, the calculation fails with a
validation error; it never falls back to an invented market price.

Every priced line stores `price_source` and the source's date. Stale prices beyond a configured
age raise an INFO or WARNING validation result (§23.2) rather than being silently used.

---

## 11. Validation architecture (§23)

Four layers — input, engineering, commercial, AI anomaly — implemented as check sets that run over
project state and write `validation_results`.

| Severity | Behaviour |
|---|---|
| ERROR | Blocks finalization |
| CRITICAL REVIEW | Requires engineer approval |
| WARNING | Progress allowed, must be visible |
| INFO | Informational |

Validation runs on demand and automatically before any state transition toward APPROVED or ISSUED.
Blocking is enforced in the transition service, so it cannot be bypassed by calling a different
route. Each result names its subject so the UI can link directly to the offending object.

---

## 12. Revisions, immutability and audit

- Approved and issued revisions are immutable (§17.2). Enforced by database trigger as well as
  application logic.
- A correction creates a new revision that references its predecessor.
- Approved engineering and commercial records are never deleted (§20.1).
- `audit_logs` captures actor, action, subject, before/after and timestamp for every significant
  mutation, and admin activity is logged separately (§22).

---

## 13. Testing strategy

| Level | Scope |
|---|---|
| Unit | Every deterministic calculation (§26). Pricing arithmetic, quantity aggregation, unit conversion |
| Rule tests | Each rule version carries `test_cases` (§11.1); they must pass before a rule may reach APPROVED. Rule approval is therefore gated by its own tests |
| Integration | Module boundaries: design → BOQ, BOQ → pricing, transition gating, RBAC on every mutation |
| Permission tests | Each role against each mutation, plus the assertion that client-role responses carry no cost or margin fields |
| E2E | The §29.2 acceptance path: create project → rooms → select systems → run engineering → review warnings → select products → BOQ → prices → quotation → validate → approve → export |
| Ground-truth replay | Historical projects replayed; generated output diffed against approved output, reported as the §24.2 metrics |

**§24.3 governs prioritisation:** optimise against approved historical engineering outputs, not
against demos. A change that improves the demo and worsens ground-truth accuracy is a regression.

---

## 14. Environments and deployment

Development uses a local Postgres and local object storage. Staging and production use managed
Postgres and S3-compatible storage, with migrations applied on deploy and secrets held only in
server-side environment variables (§22). No API key ever reaches browser code.

Backups, retention policy and recovery are required before production use (§22) and are tracked as
D-5 in §16.

---

## 15. Assumptions

1. Single organization (SmartPage) in initial use, but the schema is multi-tenant from the start
   because retrofitting tenancy is expensive.
2. Currency is SAR; the money type is currency-aware to avoid a costly later migration.
3. Users are internal for Phases 0–4; Supplier and Client roles exist in the model but their
   external-facing surfaces come later (§4.1, §25).
4. Fire Alarm, CCTV and ACS are the initial systems; the design module interface is uniform so a
   fourth system is an addition, not a refactor.
5. Jurisdiction affects which rules apply, so it is a first-class project field from day one.
6. Room and door data is entered manually in the MVP (§5.2); drawing extraction populates the same
   tables later (§25 Phase 6) without a schema change.

---

## 16. Unresolved decisions

These need a decision from SmartPage before or during Phase 0. Each names what is blocked.

**D-1 — Local database setup.** *Blocks: all implementation.* Neither Postgres nor Docker is
installed. Options: Homebrew Postgres locally; Docker Desktop; or a managed Postgres for
development. SmartPage already holds a Supabase account, which is Postgres and would also cover
object storage — if used, it should be a **new dedicated project**, not the existing one, and all
access should stay behind the repository layer so it remains swappable. *Recommendation:* local
Homebrew Postgres for development, managed Postgres for staging/production.

**D-2 — Rule expression language.** *Blocks: Prompts E–H (rules engine and all three design
modules).* Cannot be responsibly designed until 10–20 real SmartPage rules are in hand. See §9.4.

**D-3 — Rule authoring interface.** Do engineers author rules through a UI form, a reviewed
structured file, or both? Affects how much of Phase 0 UI is needed. Depends partly on D-2.

**D-4 — Row-level security.** Whether to add Postgres RLS on top of repository-level tenant
filtering. Recommended before any external (Supplier/Client) access is enabled.

**D-5 — Retention and backup policy.** Required by §22. Needs a business answer on retention
periods for project data and documents.

**D-6 — Jurisdiction model.** Whether jurisdiction is a flat code (e.g. Saudi/Aramco) or a
hierarchy with inheritance. Depends on how SmartPage's rules actually vary across authorities —
answerable once Appendix A rules arrive.

**D-7 — Cable length basis.** §16.3 requires every cable/route to have a calculation or a manual
quantity. Whether MVP takes manual lengths, computes from a route model, or both, needs an
engineering decision. This is exactly the value the previous build fabricated by measuring lines
on a drawing, so it warrants an explicit answer.

**D-8 — LGPL in the dependency tree.** *Blocks: nothing; the gate passes with the exception
recorded.* The allowed set is MIT, BSD, Apache-2.0, ISC, PSF and MPL-2.0 (separate process only);
AGPL and GPL-in-the-browser are forbidden. LGPL is on neither list. Two packages are LGPL-3.0
(`@img/sharp-libvips-*` and `@img/sharp-wasm32`), both server-side libvips arriving via
`next` → `sharp`. They are recorded as exceptions in `scripts/npm-licence-policy.mjs` with
`signedOff: false`, so every run of the gate prints them. Options and consequences are set out in
`docs/data-requests/craft-engines.md` §7.

---

## 17. Appendix A status

Per Master Spec Appendix A this is a **data request, not a list of values**. The platform must not
invent these. Build impact of each:

| Item | Blocks | Status |
|---|---|---|
| Approved system design standards/methodologies | Rules engine, design modules | **Partial** — 57 rules encoded as draft in 0015/0016 from three documents (ELV guide, TIA/EIA-568-B, Saudi camera law) |
| Project-specific engineering rules and precedence | Prompts E–H; D-2; D-6 | **Partial** — rules supplied and tagged; no approved precedence policy yet (§9.3) |
| Applicable Saudi/GCC authority requirements | Rule jurisdiction model | **Partial** — the Saudi security surveillance camera law is encoded (6 LOCAL rules, jurisdiction `SA`). SBC 801, Civil Defense and CST EMF remain items to confirm per project under X-01 |
| Manufacturer authorization records | Catalogue authorization (§12) | Not supplied |
| Approved product catalogue | Product selection; BOQ | Not supplied |
| Current and historical pricing | Pricing engine | Not supplied |
| Supplier list | RFQ (later phase) | Not supplied |
| Labour / install / T&C rates | Pricing engine | Not supplied |
| Quotation templates | Quotation engine | Not supplied |
| BOQ templates | BOQ engine | Not supplied |
| Typical assumptions and exclusions | Quotation engine | Not supplied |
| Integration standards | Integration matrix (§15) | Not supplied |
| Historical ground-truth projects | Testing (§24); accuracy measurement | Not supplied |

The first row moved off "Not supplied" on 24 Sep 2026. It is worth being precise about what that
buys: the rules are stored, tagged and traceable, but all 57 versions are `draft`, 39 of them carry
a `verification_note` saying the cited source was not read or is superseded, and no evaluator
exists. The platform can now *answer* where a rule came from. It cannot yet *run* one.

The 568-B document is the model for how a second source should land: it did not merely add rules,
it **corrected two** (A-02's fibre bend multiplier, A-11's field-test set) and **confirmed by
absence** that two SPEC tags were right, because the figures genuinely are not in the standard.
Both corrections were applied to version 1 in place — legitimate only because those versions are
still `draft`. The first rule to reach `approved` ends that freedom, and every later correction
becomes a new version (§12).

**Phases 0–2 (foundation, workspace, schema, catalogue and rule *frameworks*) can be built now
without any of this.** Everything from the design modules onward produces an empty shell until the
corresponding data arrives. Collecting it is organizational work that is slower than the coding,
so it should start immediately and in parallel — it is the real critical path, not the software.

---

## 18. Craft engines

The platform can reason about rules and compute numbers, but engineers work in .xlsx, .docx, .dxf
and .pdf. The craft engines read and write those files. They are headless tools, not editors: Excel,
Word and AutoCAD keep their jobs.

### 18.1 Position

A separate Python process (`engines/`), exposed over HTTP and called from `src/modules/craft/`.
`engines/Dockerfile` builds it, and `compose.yaml` runs it on loopback; the image carries
LibreOffice because `word.to_pdf` shells out to it, plus Carlito and Liberation so generated PDFs
keep the metrics the templates were laid out for.
The service has **no authentication of its own** — authorisation happens in the server action
before the call — so it must never be bound to a public address.
Separate because the mature libraries for these formats are Python (openpyxl, python-docx, ezdxf,
pdfplumber) and because a CPU-bound parse must not sit in a Next.js request path.

`src/modules/craft/actions.ts` makes the HTTP call **outside** the transaction, then opens one to
write `craft_operations`, the output `documents` row and the audit entry together. The postgres.js
pool is `max: 10`; a slow parse holding a pooled connection would starve the application.

### 18.2 The rule that shapes every tool

**No tool invents an engineering value.** Where a value is absent, the tool returns
`status='missing_data'` with an itemised list naming the record and field, and — when the output
is a document — **writes no file at all**. A half-finished document circulates as if it were
finished.

| Situation | What happens |
|---|---|
| Template placeholder with no value | No .docx written; the key is itemised |
| Spec clause with no captured value | Not "Comply"; no sheet written |
| Block insert not in the symbol map | Whole count is `missing_data`; partial tallies still returned |
| DXF with `$INSUNITS = 0` | Outlines returned, areas refused |
| PDF page with no text layer | Reported as needing OCR, not as empty text |
| BOQ line with no approved price | `missing_data`, not zero |

### 18.3 Tools

| Engine | Tool | Writes |
|---|---|---|
| Grid | `grid.write_boq` | .xlsx, value **and** live formula per cell, hidden provenance sheet |
| Grid | `grid.read_client_boq` | nothing — returns proposals |
| PDF | `pdf.extract` | nothing — text, tables, vector paths |
| PDF | `pdf.pack` | merged, stamped submittal pack |
| CAD | `cad.read_dxf` | nothing — layer/block/insert inventory |
| CAD | `cad.count_devices` | `drawing_objects` rows, `source='imported'`, `review_status='pending'` |
| CAD | `cad.extract_rooms` | nothing — outlines, labels, areas |
| CAD | `cad.place_devices` | `drawing_objects` proposals from a cited spacing rule |
| CAD | `cad.markup` | a **new** DXF with notes on an `SPI_MARKUP` layer |
| CAD | `cad.takeoff_sheet` | a **new** DXF: devices ringed and tagged by system, a schedule per system, unmapped blocks in a red NOT COUNTED table, room areas — on `SPI_TAKEOFF` / `SPI_SCHEDULE` / `SPI_ROOMS` |
| CAD | `cad.sheet_setup` | a **new** DXF on an `SPI_SHEET` layer: ISO 5457 frame and zones, ISO 7200 title block (missing mandatory fields drawn as MISSING and returned as `missing_data`), scale bar, north arrow only from a stated bearing |
| Word | `word.fill_template` | .docx from a default or supplied template |
| Word | `word.compliance_sheet` | Comply/Deviate/Clarify .docx |
| Word | `word.to_pdf` | .pdf, via LibreOffice headless |
| BIM | `bim.read_ifc` | nothing — schema, authoring tool, units, storeys, element classes and types |
| BIM | `bim.count_devices` | `drawing_objects` rows, `source='imported'`, `review_status='pending'`, per storey |
| BIM | `bim.extract_spaces` | nothing — rooms, storeys, areas from the model's own quantities |
| BIM | `bim.scene_3d` | nothing — room outlines and heights, device positions; feeds the simulator |

BIM reads **IFC**, which Revit exports natively; `.rvt` is recognised and refused with the export
route, because it is undocumented, changes every release and may not be reverse-engineered under
Autodesk's licence. The STEP reader is our own: IfcOpenShell is LGPL-3.0. Revit's export habits
(location baked into geometry, devices contained in the storey rather than the room, proxies) and
the reasons are in `docs/decisions/0002-bim-engine.md`. Family-to-device mapping is an
`ElementMap`, data with a required `source_document`, exactly as §18.5 describes for symbols.

`simulator/` builds a page from `bim.scene_3d`: the model in 3D, plan and walk views, coverage
checks against SPT-FA-01/02/04/13 and SPT-CC-01/03/09, what-if proposals, and a fire-drill
sequence. `simulator/rules.py` copies those rules out of migration 0017 and stops the build if
their text no longer states the values the page applies.

`cad.place_devices` is implemented. It was a stub while nothing could supply a spacing figure with
a source; the rules library now carries them, and the rule is passed in as data — `max_spacing_m`,
`max_wall_distance_m` and the code that says so. **No spacing value exists anywhere in the package**,
and a test asserts it. Everything it emits is a proposal: `source='ai_extracted'`,
`review_status='pending'`, never `'imported'`, because a device counted off a drawing is evidence
and one computed from a rule is a suggestion.

`cad.measure_route` is still registered as `implemented=false` and raises `NotImplementedError`.
Cable length needs containment routes, risers and a slack allowance — **D-7**. Measuring a straight
line between two symbols is the fabrication the previous build shipped.

### 18.4 Word output has one default look

`craft/word/style.py` holds the shared document style — A4, 2 cm margins, one typeface, a title, a
borderless label/value block, then content — and `craft/word/templates.py` holds three default
templates built on it: transmittal, submittal cover and compliance statement.
`word.compliance_sheet` uses the same style, so every Word output matches.

No logo, no letterhead, no company name. That artwork is SmartPage's, and a generated one would go
out on a document sent to a client; a test asserts no identity is invented. To override a template,
put a .docx in storage with `{{placeholders}}` typed into it and point `word.fill_template` at it —
the substitution works on any .docx.

Every placeholder is mandatory, because an unfilled one blocks the write. Field sets are therefore
kept to what a document of that kind cannot go out without, and
`templates.placeholders(kind)` returns the set at runtime for a form to build from. The submittal
cover and the compliance statement state that they are generated proposals and not submittals until
signed; the transmittal does not, because it makes no engineering claim.

### 18.5 Symbol mapping is data

`cad.count_devices` takes a `SymbolMap` as input. No mapping is hard-coded, because a block named
`FD` is a smoke detector on one job and a fire damper on another. A map must declare
`source_document`; one with no stated origin cannot be audited later and is rejected.

A generic default ships as data in `engines/craft/cad/default_symbols.json` and is used when no map
is supplied. It matches **descriptive** block names only — a block literally called
`SMOKE-DETECTOR`, `CARD-READER`, `DOME-CAMERA`. It deliberately does **not** interpret short codes:
`SD`, `FD`, `MCP`, `PANEL` and thirteen others are listed in `deliberately_unmapped` with the
reason, and `cad.count_devices` puts that reason into the `missing_data` note, so the gap reads as a
decision rather than an oversight.

The reasoning: a *wrong* mapping is worse than a missing one. A missing one produces
`missing_data`, which someone acts on. A wrong one produces a confident count that flows into a BOQ
and is never looked at again. `SD` is smoke detector on a fire alarm layer and smoke damper on a
mechanical one; guessing moves a device between packages. The default is a starting point, not a
client standard — request #4 in `docs/data-requests/craft-engines.md` is still open.

### 18.6 Authority

Every tool returns a proposal. `TOOL_POLICY` in `src/modules/craft/tools.ts` sets `aiMayCommit:
false` for all of them (§4.1 rule 1 — `ai/` may not write to authoritative tables). The AI may
assemble a submittal pack; a person issues it. Counted devices land in `drawing_objects` as
`pending` and reach `design_devices` only through the existing `building_model.review` flow.

### 18.7 Licensing

Allowed: MIT, BSD, Apache-2.0, ISC, PSF, MPL-2.0 (separate process only). Forbidden: AGPL, GPL
shipped to the browser, HyperFormula, the ODA SDK.

Consequences actually taken: **no PyMuPDF** (AGPL) — `pdfplumber` and `pypdf` instead; **no
docxtpl** (LGPL-2.1) — `craft/word/placeholders.py` does the run merging with `python-docx`, which
is why that module exists; **no formula evaluator** — GridCraft writes the formula text and lets
Excel calculate; **no DWG reader** — the usual one is the ODA SDK, so DWG must be converted
upstream. LibreOffice is MPL-2.0 and is invoked as a separate process, never linked.

`scripts/check-licenses` gates both halves of the tree and fails rather than skips when it cannot
run. The npm half judges each package (`scripts/npm-licence-policy.mjs`), because a flat `grep GPL`
can only express "no GPL anywhere", which would reject Next.js itself. See **D-8**.

### 18.8 Record

Every run inserts one `craft_operations` row (migration 0023, append-only): engine, tool, actor,
mode, inputs, outputs, provenance, missing items, warnings, status, duration and engine version.
Output `documents` rows carry `source_operation_id`, so any generated file can be traced to the run
that made it and the inputs it read.
