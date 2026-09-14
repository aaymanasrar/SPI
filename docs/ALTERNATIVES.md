# Alternative Products — Design Proposal

**Status: proposal for review. Nothing applied.** No migration has been run and no code
written. This defines the entities and rules so the feature can be built later without a
database redesign.

**Contains no products, specifications, prices, approvals or engineering rules.** It defines
containers and the rules that govern them.

---

## 0. The load-bearing idea

"Alternative product" is not one thing. The three classes differ in **what evidence justifies
them and who may approve them** — not merely in what they are called:

| Class | Justified by | Approved by |
|---|---|---|
| Technically equivalent | Every mandatory requirement met or bettered, each with datasheet evidence, no unknowns | Engineer |
| Functionally suitable | Performs the same function; some non-mandatory specs deviate | Engineer, with the deviations shown |
| Commercial alternative | Functionally suitable **and** advantaged on price or lead time | Engineer **and** commercial |

Everything below follows from that. If the three collapse into one "similar products" list, the
system will eventually present a cheaper part that misses a rating nobody re-checked.

Two structural consequences, enforced in the schema rather than by convention:

1. **A specification that has no source document does not exist.** `specification_values` requires
   a `source_document_id`. There is no way to record a spec without pointing at the datasheet it
   came from, so "never invent specifications" is not a prompt instruction — it is a NOT NULL.

2. **No write path exists from a computed match to an approved alternative.** The engine writes to
   `alternative_candidates`. Only a human approval moves anything into `alternatives`. This mirrors
   the extraction proposal pattern already in ARCHITECTURE.md §8.2.

---

## 1. Proposed entities and fields

Seven new tables, three new columns on existing ones, eleven new enums.

### 1.1 Specification dictionary — `specification_definitions`

The canonical vocabulary. Without it, `ingress_protection`, `IP Rating` and `Ingress Prot.` are
three different specs and nothing can be compared.

```
id                uuid pk
organization_id   -> organizations
key               text          canonical key, unique per org per category
name              text          display name
category          text          product category this applies to
value_type        spec_value_type       numeric | integer | boolean | enum | range | text
canonical_unit    text          null for non-numeric; all values normalise to this
comparison        spec_comparison       how "better" is defined for this spec
enum_values       text[]        for value_type = 'enum'
tolerance_percent numeric(6,3)  for comparison = 'within_tolerance'
is_safety_related boolean       see note below
notes             text
status            lifecycle_status
unique (organization_id, category, key)
```

`comparison` values: `higher_is_better`, `lower_is_better`, `must_equal`, `must_be_one_of`,
`within_tolerance`, `boolean_required`, `not_comparable`.

**`not_comparable` is deliberate.** Housing colour, datasheet revision, packaging quantity —
informational specs that must never contribute to a match score. Without this, noise inflates
match percentages and makes them meaningless.

**`is_safety_related`** marks specs where a deviation can never be waived silently. Which specs
these are is SmartPage engineering data (Appendix A), not something to be guessed here.

### 1.2 Normalized values — `specification_values`

One row per product model per spec. Derived from the datasheet; the raw
`product_models.technical_specifications` JSONB stays untouched as the unaltered record of what
was published.

```
id                  uuid pk
product_model_id    -> product_models
specification_id    -> specification_definitions
value_numeric       numeric(20,6)   in canonical_unit
value_numeric_max   numeric(20,6)   upper bound for ranges
value_text          text
value_bool          boolean
raw_value           text            exactly as printed on the datasheet
unit_as_published   text            before conversion
source              source_type     manual | ai_extracted | imported
source_document_id  -> documents    NOT NULL
source_reference    text            page / section / table
confidence          numeric(5,4)    null unless ai_extracted
review_status       review_status   pending until a human confirms
created_by, updated_by
unique (product_model_id, specification_id)
```

Constraints:
- `source_document_id is not null` — the structural ban on invented specs
- at least one of the value columns populated
- `confidence is null or source = 'ai_extracted'`

`raw_value` and `unit_as_published` are kept alongside the converted number so a unit-conversion
error is detectable after the fact rather than baked in invisibly.

**Only `review_status = 'approved'` rows are usable as equivalence evidence.** An AI-extracted
spec awaiting review can be displayed, but cannot support a technical-equivalence claim.

### 1.3 Requirements — `specification_requirements`

The other half of a comparison. You cannot match without something to match *against*, and that
something is a constraint set, whether it originates from a specified product, a project
specification, or a rule.

```
id                  uuid pk
organization_id     -> organizations
project_id          -> projects            } exactly one of these
project_system_id   -> project_systems     } four is non-null
design_device_id    -> design_devices      } (enforced by check constraint)
boq_item_id         -> boq_items           }
specification_id    -> specification_definitions
operator            spec_operator   gte | lte | eq | neq | in | between | required
value_numeric, value_numeric_max, value_text, value_bool, enum_values
is_mandatory        boolean         mandatory failure disqualifies equivalence
origin              requirement_origin  project_specification | rule_execution | engineer | client
rule_execution_id   -> rule_executions    set when origin = 'rule_execution'
source_document_id  -> documents
source_reference    text
created_by
```

`origin` carries the same weight it does elsewhere in this system: a requirement produced by a
rule is traceable to that rule version and its inputs; one from a project specification is
traceable to the document and clause.

### 1.4 Asserted alternatives — `alternatives` (extended)

The existing table already carries approval fields. It gains classification, scope and validity:

```
+ alternative_kind   alternative_kind      technically_equivalent | functionally_suitable | commercial
+ direction          alternative_direction substitutes_for | bidirectional
+ scope              alternative_scope     catalogue | project
+ project_id         -> projects           non-null iff scope = 'project'
+ declared_by        declared_by           manufacturer | smartpage_engineering | supplier
+ basis              text                  why this is claimed
+ approval_status    product_approval_status
+ valid_from, valid_to  date
```

**Direction is not symmetric by default.** A product that exceeds requirements can substitute for
a lesser one; the reverse is not true. Modelling alternatives as an undirected pair would silently
permit downgrades. `bidirectional` must be asserted deliberately.

`unique (product_model_id, alternative_model_id)` becomes
`unique (product_model_id, alternative_model_id, scope, coalesce(project_id, ...))` so a project
can hold an approval that does not leak into the catalogue.

### 1.5 Evidence — `alternative_evidence`

```
id              uuid pk
alternative_id  -> alternatives
document_id     -> documents
evidence_type   text    datasheet | manufacturer_letter | test_report | authority_approval
reference       text    page / clause
added_by
```

An alternative with `alternative_kind = 'technically_equivalent'` and no evidence row is a
validation ERROR. The claim and its proof are stored together or not at all.

### 1.6 Computed candidates — `alternative_candidates`

Engine output. **Never authoritative.**

```
id                       uuid pk
organization_id          -> organizations
project_id               -> projects        null for catalogue-wide searches
for_product_model_id     -> product_models  the product being replaced
candidate_model_id       -> product_models
proposed_kind            alternative_kind
match_percentage         numeric(5,2)
mandatory_total          integer
mandatory_satisfied      integer
mandatory_unknown        integer
mandatory_failed         integer
eligibility_passed       boolean
ineligibility_reasons    text[]
price_delta_minor        bigint
currency                 char(3)
lead_time_delta_days     integer
rationale                text            may be AI-drafted; facts come from the spec rows
engine_version           text
computed_at              timestamptz
status                   proposal_status  pending | accepted | rejected | superseded
reviewed_by, reviewed_at, review_note
```

`mandatory_unknown` is reported separately from `mandatory_failed` on purpose. "We checked and it
does not meet this" and "the datasheet does not say" are different facts and must not be averaged
into one number.

### 1.7 Per-specification detail — `alternative_candidate_specs`

What makes a result explainable. The UI's "matching specifications" and "specifications that
differ" read from here — they are data, not a generated sentence.

```
id                  uuid pk
candidate_id        -> alternative_candidates
specification_id    -> specification_definitions
is_mandatory        boolean
requirement_operator spec_operator
requirement_value   jsonb
candidate_value     jsonb
candidate_value_source_document_id -> documents   evidence for this specific comparison
outcome             spec_match_outcome  satisfied | exceeded | deviates | unknown | not_applicable
weight              numeric(6,3)
```

### 1.8 Project overrides — `project_product_constraints`

```
id                uuid pk
project_id        -> projects
constraint_type   project_constraint_type
manufacturer_id   -> manufacturers
product_model_id  -> product_models
authority         text
note              text
source_document_id -> documents
source_reference  text
created_by
```

`project_constraint_type`: `require_authorized`, `require_manufacturer`, `forbid_manufacturer`,
`require_authority`, `require_product_model`, `forbid_product_model`, `require_specification`.

These are **filters, not preferences**. A project that mandates a manufacturer does not rank that
manufacturer higher — everything else becomes ineligible.

### 1.9 Substitution workflow — `substitution_requests`

```
id                       uuid pk
organization_id, project_id
boq_item_id              -> boq_items        } one of
design_device_id         -> design_devices   } these two
from_product_model_id    -> product_models
to_product_model_id      -> product_models
alternative_id           -> alternatives              the asserted relationship relied on
candidate_id             -> alternative_candidates    what prompted it, if any
kind                     alternative_kind
reason                   text
price_delta_minor, currency
status                   substitution_status
requested_by, requested_at
engineering_approved_by, engineering_approved_at
commercial_approved_by,  commercial_approved_at
applied_boq_id           -> boqs             the revision created by applying it
rejected_reason          text
```

### 1.10 New enums

`spec_value_type`, `spec_comparison`, `spec_operator`, `spec_match_outcome`, `alternative_kind`,
`alternative_direction`, `alternative_scope`, `declared_by`, `requirement_origin`,
`project_constraint_type`, `substitution_status`.

---

## 2. Specification normalization

Comparison is impossible while specs are prose in a JSONB blob. Four steps:

**Identify.** Map a published spec name onto a `specification_definitions.key`. Synonyms
("IP Rating", "Ingress Protection", "Protection Degree") resolve to one canonical key. AI may
propose mappings; a reviewed mapping becomes authoritative.

**Convert.** Normalise to `canonical_unit` and store the converted number, keeping `raw_value` and
`unit_as_published` beside it so a bad conversion stays visible and correctable.

**Type.** A spec is numeric, a range, an enum, a boolean or free text. Free text is
`not_comparable` and never scores — recorded for display only.

**Attest.** Every value points at the datasheet and its page or clause, and carries a
`review_status`.

Extraction from datasheets is Phase 5–6 work and reuses the document pipeline already proven
against the Aramco package (ARCHITECTURE.md §7). Extracted values arrive as
`review_status = 'pending'` and are not usable as equivalence evidence until reviewed — the same
gate the building model already applies to extracted rooms and doors.

**What this does not do:** it does not guess a missing spec. A datasheet that omits a value yields
no row, and the comparison outcome is `unknown`.

---

## 3. Relationship model

Two distinct things, deliberately in separate tables:

```
alternatives              asserted, approved, authoritative
                          a human or manufacturer states the relationship
                          survives independently of any engine

alternative_candidates    computed, proposed, advisory
                          produced by the matching engine
                          expires, is recomputed, never trusted on its own
```

The promotion path is one-way and passes through a person:

```
matching engine → alternative_candidates (status: pending)
                        ↓ engineer reviews evidence
                  substitution_requests → approval
                        ↓
                  alternatives (approved, with evidence rows)
```

There is no direct insert from engine to `alternatives`. That is what makes "do not allow AI
similarity alone to approve a product substitution" a property of the schema rather than a policy
someone has to remember.

Scope matters as much as classification. A product accepted for one project — perhaps because that
client waived a requirement — must not silently become a catalogue-wide equivalent. Hence
`scope` and `project_id`.

---

## 4. Matching and ranking

Five stages. Stages 1–3 are deterministic; AI participates only where marked.

### Stage 1 — Eligibility (hard filters, before any scoring)

Applied as query filters. A product failing any of these does not appear at any score:

- `lifecycle_status <> 'withdrawn'`
- where the project requires authorized products:
  `authorized_status = 'authorized'` **and** an in-date `authorizations` row
- project jurisdiction present in `authorized_regions` where that is set
- every applicable `project_product_constraints` row satisfied

Failures are recorded in `ineligibility_reasons` so "why is product X not offered?" is answerable,
but an ineligible product is never ranked or shown as an option.

### Stage 2 — Constraint evaluation (deterministic)

For each requirement, compare against the candidate's approved `specification_values`:

| Situation | Outcome |
|---|---|
| Meets the requirement | `satisfied` |
| Betters it on a `higher_is_better` / `lower_is_better` spec | `exceeded` |
| Differs within an acceptable direction on a non-mandatory spec | `deviates` |
| Candidate has no approved value for this spec | `unknown` |
| Spec does not apply to this category | `not_applicable` |

**`unknown` never counts as a pass.** This is the §10.3 no-guess policy applied to product
selection.

### Stage 3 — Classification (rule-based, not score-based)

The class is decided by rules, not by a threshold on the score:

```
technically_equivalent  ⟺  mandatory_failed = 0
                       and  mandatory_unknown = 0
                       and  every mandatory spec has evidence
                       and  no safety-related spec has outcome 'deviates'

functionally_suitable   ⟺  mandatory_failed = 0
                       and  at least one 'deviates' or non-mandatory 'unknown'

commercial              ⟺  functionally_suitable
                       and  a price or lead-time advantage exists

otherwise               →   not an alternative; not returned
```

A 97% match with one mandatory spec unknown is **not** technically equivalent. Deciding class by
score is precisely the failure this design exists to prevent.

### Stage 4 — Ranking within class

Weighted score across evaluated specs, used only to order results *inside* a class. Never to
determine the class. Reported as "technical match percentage" with the mandatory-unknown count
shown beside it, so a high percentage cannot be read as completeness.

### Stage 5 — Explanation

Assembled from `alternative_candidate_specs` rows. AI may write the prose summary, but every
claim in it must correspond to a row with an outcome and a source document. The structured
comparison remains visible next to any generated text.

### Where AI is permitted

| Allowed | Not allowed |
|---|---|
| Proposing candidate products to evaluate | Setting `alternative_kind` |
| Mapping published spec names to canonical keys (for review) | Marking a candidate accepted |
| Extracting spec values from datasheets (as `pending`) | Writing to `alternatives` |
| Drafting rationale text | Supplying a spec value that becomes authoritative unreviewed |
| Flagging anomalies | Overriding an eligibility filter |

This mirrors the §10.1 boundary table: AI interprets and proposes, deterministic logic decides,
a human approves.

---

## 5. Approval workflow

```
draft
  → engineering_review     always; technical judgement cannot be skipped
  → commercial_review      only when there is a price impact
  → approved  |  rejected
  → applied                creates a new BOQ revision
```

Rules:

- **Engineering review is never skipped**, including for a candidate classified
  `technically_equivalent`. The classification says the evidence supports equivalence; it does not
  say an engineer has accepted it for this project.
- **Commercial review is additionally required** when `price_delta_minor <> 0`.
- Each transition writes to the existing `approvals` table and `audit_logs`.
- `substitution_requests` rows are frozen once `approved`, `rejected` or `applied`, by the same
  trigger pattern as migration 0010. A correction creates a new request.
- Applying a substitution to an approved BOQ **creates a new BOQ revision**. The existing
  immutability triggers already make an in-place edit impossible, so this falls out of the schema
  rather than needing new enforcement.

---

## 6. Integration with BOQ and design

Substitution targets are `design_devices.product_model_id` and `boq_items.product_model_id` — both
already exist.

**Price never travels with a substitution.** The alternative's price re-resolves through the §13.2
hierarchy against its own catalogue and price-list records. Inheriting the original's price would
produce a line whose `price_source` points at a different product — precisely the untraceable
number this system is built to prevent.

**`boq_item_sources` needs no schema change.** Its `source_type` is already free text, so a
substitution records itself as `source_type = 'substitution'` with `source_id` pointing at the
`substitution_requests` row. The chain in SCHEMA.md §1.1 stays traversable:

```
boq_item → product → substitution_request → alternative → evidence → datasheet
                                                        ↘ candidate → per-spec comparison
```

**Two new validation checks** (spec §23, engineering layer):

| Severity | Check |
|---|---|
| ERROR | A BOQ item whose product arrived via a substitution that is not `approved` |
| ERROR | An `alternatives` row marked `technically_equivalent` with no evidence row |
| CRITICAL REVIEW | A substitution where any safety-related spec deviates |
| WARNING | An accepted alternative whose supporting spec values are older than the configured staleness window |
| INFO | A candidate offered with one or more mandatory specs unknown |

**Design modules are unaffected.** They select products through the catalogue as before;
alternatives operate on the result. No change to Prompts E–H.

---

## 7. Required documentation changes

### docs/ARCHITECTURE.md

- **§1** — add the substitution chain to the chain-of-custody diagram.
- **§3** — add `src/modules/catalogue/alternatives/` to the repository structure.
- **§4.1** — add dependency rule 7: *the alternatives engine may not write to `alternatives`,
  `specification_values` (as approved) or `boq_items`. It writes candidates; approval writes the
  rest.*
- **§8** — extend the AI boundary table with the permitted/not-permitted split from §4 above.
- **§9** — note that specification requirements may originate from a rule execution, linking the
  rules engine to product selection.
- **§16** — two new open decisions:
  - **D-8** Spec staleness window: how old may a spec value be before an equivalence claim needs
    re-verification? Needs a SmartPage answer.
  - **D-9** Which specifications are safety-related per category. Appendix A data; cannot be
    guessed.

### docs/SCHEMA.md

- **§1** — new domain block for specifications and alternatives; table count 62 → 69.
- **§2** — new subsection describing the seven tables.
- **§3** — required/optional: `specification_values.source_document_id` NOT NULL is the notable
  entry; `confidence` nullable on the same rule as elsewhere.
- **§4** — `alternatives` becomes date-versioned via `valid_from`/`valid_to`.
- **§5** — `substitution_requests` frozen at approved/rejected/applied;
  `alternative_candidates` superseded rather than deleted.
- **§6** — migrations 0014–0017:
  - `0014_specification_dictionary` — definitions, values, requirements
  - `0015_alternatives` — extend `alternatives`, add evidence, candidates, candidate specs
  - `0016_substitutions` — project constraints, substitution requests
  - `0017_alternative_triggers_and_rls` — freeze triggers, RLS on the new tables
- **§7** — record D-8 and D-9.

---

## 8. What is deliberately not decided here

**Spec weighting.** Which specs matter more within a category is engineering knowledge, and
inventing weights would produce confident rankings built on nothing. The `weight` column exists;
the values come from SmartPage.

**Safety-related spec list.** Same reason. The flag exists; the classification does not.

**Staleness window.** A business and engineering decision about how long a datasheet-derived spec
remains trustworthy.

**The synonym dictionary.** Mapping published spec names to canonical keys should be seeded from
real datasheets, not imagined ones — the same argument as deferring the rule expression language
in ARCHITECTURE.md §9.4. Designing it against invented spec names would produce a vocabulary that
fits no real manufacturer.

These are the reasons the schema can be built now and the engine later: the containers do not
depend on the values.
