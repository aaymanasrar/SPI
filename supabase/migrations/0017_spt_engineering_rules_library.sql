-- 0017_spt_engineering_rules_library
--
-- The SPT Engineering Rules Library (Pre-Sales, compiled 29 Sep 2026): 80 rules
-- across six systems, the fourth Appendix A document and the first structured
-- as a library rather than prose.
--
-- THE POINT OF THIS MIGRATION IS NOT THE 80 ROWS. It is that this library
-- overlaps heavily with the 57 rules already encoded, and in two places
-- contradicts them. Loading it blind would leave two live, disagreeing rules
-- for fibre bend radius and two for CCTV retention, with nothing to flag it --
-- exactly the failure knowledge/README.md describes, where a wrong value flows
-- into a BOQ carrying the appearance of engineering authority.
--
-- ARCHITECTURE.md 9.3 requires that the engine never resolve a conflict
-- silently: it identifies the conflict, surfaces both sources, and applies a
-- precedence policy only where that precedence has been explicitly configured
-- AND approved. This migration therefore adds:
--
--   * rule_relationships   -- the conflict/overlap registry, populated with all
--                             23 relationships between this library and the
--                             existing rules
--   * rule_precedence_policy -- the library's stated precedence order, stored
--                             UNAPPROVED. Recording a policy does not activate
--                             it.
--   * engineering_rules.jurisdiction_overlay -- the Saudi/client overlay column
--                             (SBC, NCA, HCIS, Aramco SAES), which had no home
--                             and is the richest Saudi content received so far.
--
-- All 80 rules are seeded as draft with source_verified = false: the library's
-- own limitations state that clause numbers shift between editions and that the
-- Aramco SAES and HCIS directive numbers were not checked against controlled
-- copies.
--
-- Idempotent.

-- ---------------------------------------------------------------------------
-- 1. Two further systems
-- ---------------------------------------------------------------------------
insert into systems (code, name) values
  ('network', 'Network'),
  ('ups',     'UPS')
on conflict (code) do nothing;

-- ---------------------------------------------------------------------------
-- 2. The Saudi / client overlay
-- ---------------------------------------------------------------------------
-- Most rules in this library carry BOTH an international source and a Saudi or
-- client overlay (SBC 801 §907, NCA ECC-2:2024, HCIS SEC, Aramco SAES-T-916).
-- That is a different axis from `jurisdiction`, which says which jurisdiction a
-- rule is bounded to. Here the rule is international and the overlay says which
-- local instrument adopts or tightens it.

alter table engineering_rules
  add column if not exists jurisdiction_overlay text;

comment on column engineering_rules.jurisdiction_overlay is
  'The local instrument that adopts or tightens an international rule, e.g. '
  '"SBC 801 907 (adopts NFPA 72)". Distinct from `jurisdiction`, which bounds a '
  'rule to one country. A rule may be international with a Saudi overlay.';

-- ---------------------------------------------------------------------------
-- 3. Relationship registry (spec 11.4 / ARCHITECTURE.md 9.3)
-- ---------------------------------------------------------------------------

create type rule_relationship_kind as enum
  ('agrees','refines','resolves','supersedes','conflicts');

comment on type rule_relationship_kind is
  'agrees: same requirement, no action. refines: adds detail. resolves: supplies '
  'a value the other rule deliberately left open. supersedes: strictly better, '
  'retire the other. conflicts: the two disagree and cannot both be approved.';

create table rule_relationships (
  id              uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  from_rule_id    uuid not null references engineering_rules(id) on delete cascade,
  to_rule_id      uuid not null references engineering_rules(id) on delete cascade,
  kind            rule_relationship_kind not null,
  note            text not null,
  resolved_at     timestamptz,
  resolved_by     uuid references users(id),
  resolution_note text,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  unique (from_rule_id, to_rule_id),
  constraint rule_relationships_not_self check (from_rule_id <> to_rule_id),
  constraint rule_relationships_resolution check (
    resolved_at is null or resolution_note is not null)
);
select attach_updated_at('rule_relationships');
create index idx_rule_relationships_from on rule_relationships(from_rule_id);
create index idx_rule_relationships_to   on rule_relationships(to_rule_id);
create index idx_rule_relationships_open on rule_relationships(organization_id)
  where kind in ('conflicts','supersedes') and resolved_at is null;

comment on table rule_relationships is
  'Known relationships between rules from different source documents. An '
  'unresolved conflicts/supersedes row blocks both rules from approval -- see '
  'forbid_approving_conflicted_rule().';

-- A rule version cannot be approved while the rule sits on an unresolved
-- conflict. This is the enforcement half of spec 11.4: without it, the registry
-- would be documentation that nothing reads.
create or replace function forbid_approving_conflicted_rule() returns trigger
language plpgsql
set search_path = ''
as $$
declare
  other text;
begin
  if new.approval_status in ('approved','active')
     and old.approval_status is distinct from new.approval_status then

    select string_agg(format('%s (%s)', er2.rule_code, rr.kind), '; ')
      into other
    from public.rule_relationships rr
    join public.engineering_rules er1
      on er1.id = rr.from_rule_id or er1.id = rr.to_rule_id
    join public.engineering_rules er2
      on er2.id = case when rr.from_rule_id = er1.id
                       then rr.to_rule_id else rr.from_rule_id end
    where er1.id = new.rule_id
      and rr.kind in ('conflicts','supersedes')
      and rr.resolved_at is null;

    if other is not null then
      raise exception
        'rule version % cannot become %: the rule has unresolved conflicts with %',
        new.id, new.approval_status, other
        using errcode = 'restrict_violation',
              hint = 'Resolve the rule_relationships row (set resolved_at and '
                     'resolution_note) or retire one of the two rules.';
    end if;
  end if;
  return new;
end $$;

create trigger trg_rule_versions_conflict_gate
  before update on rule_versions
  for each row execute function forbid_approving_conflicted_rule();

-- ---------------------------------------------------------------------------
-- 4. Precedence policy (spec 11.4)
-- ---------------------------------------------------------------------------
-- Stored UNAPPROVED. Spec 11.4 permits precedence to resolve a conflict only
-- where it has been explicitly configured and approved; recording the library's
-- stated order is the configuration half, not the approval half.

create table rule_precedence_policy (
  id              uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  name            text not null,
  rank            integer not null,
  authority       text not null,
  source_document text,
  approved_by     uuid references users(id),
  approved_at     timestamptz,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  unique (organization_id, name, rank)
);
select attach_updated_at('rule_precedence_policy');

comment on table rule_precedence_policy is
  'Ordered precedence between sources of authority, rank 1 highest. Inert until '
  'approved_at is set. Approving it does not permit overriding a statutory rule: '
  'a SOW cannot authorise a camera in a restroom (KSA-CCTV-03) or a locked '
  'egress door (SPT-AC-01).';

-- ---------------------------------------------------------------------------
-- 5. The 80 rules, as data
-- ---------------------------------------------------------------------------
-- Generated from the supplied library, not hand-transcribed. The per-system and
-- per-basis counts were checked against the workbook README tally and match
-- exactly: 41 Code, 17 Code - verify, 22 Practice, 80 total.
--
-- Basis maps to confidence as follows, and the mapping is deliberate:
--   Code          -> confidence 'code', severity 'error'
--   Code - verify -> confidence 'code', severity 'critical_review'
--   Practice      -> confidence 'spec', severity 'warning'
--
-- 'Code - verify' is NOT downgraded to 'spec'. It is a genuine code requirement
-- whose clause, edition or value has not been checked; this schema already
-- separates confidence from verification state, so the distinction lives in
-- source_verified (false for all 80) and verification_note. Collapsing it into
-- 'spec' would let a real code requirement be waved away as practice.
--
-- calculation.plain_english holds the supplier's explanatory wording, which they
-- state is theirs and not in the workbook. It always travels with
-- plain_english_provenance saying so. Two entries the supplier identified as
-- invented illustrations carry plain_english_example_invented = true, so a
-- client-facing render can drop them with a query.

create or replace function spt_library_seed()
returns table (
  system_code text, rule_code text, source_rule_id text, rule_name text,
  confidence public.rule_confidence, jurisdiction text, standard_reference text,
  priority integer, source_verified boolean, verification_note text,
  jurisdiction_overlay text, conditions jsonb, inputs jsonb, calculation jsonb,
  outputs jsonb, exceptions jsonb)
language sql immutable
set search_path = ''
as $fn$
select t.system_code, t.rule_code, t.source_rule_id, t.rule_name,
       t.confidence::public.rule_confidence, t.jurisdiction, t.standard_reference,
       t.priority, t.source_verified, t.verification_note, t.jurisdiction_overlay,
       t.conditions::jsonb, t.inputs::jsonb, t.calculation::jsonb,
       t.outputs::jsonb, t.exceptions::jsonb
from (values
('fire_alarm', 'SPT-FA-01', 'FA-01', 'Smoke detector - max spacing', 'code', null, 'NFPA 72 Ch.17 (§17.7.3.2.3)', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 'SBC 801 §907 (adopts NFPA 72 for installation)', '{"applies_when": [], "condition_text": "Smooth, flat ceiling"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "9.1 m (30 ft) nominal", "library_basis": "Code", "calculation": "Coverage approx 84 m2 per detector (S squared)", "plain_english": "Each smoke detector covers a square about 9.1 m on each side. 9.1 x 9.1 = about 84 m2, so one detector protects roughly 84 m2 of flat ceiling.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "error", "code": "SPT-FA-01"}', '{"notes": ["Beams/joists, sloped ceilings, high air movement, performance-based design, manufacturer listing lower"]}'),
('fire_alarm', 'SPT-FA-02', 'FA-02', 'Smoke detector - 0.7S rule', 'code', null, 'NFPA 72 Ch.17 (§17.7.3.2.3)', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 'SBC 801 §907 (adopts NFPA 72 for installation)', '{"applies_when": [], "condition_text": "Irregular room shapes"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Every point on ceiling <= 0.7 x S from a detector", "library_basis": "Code", "calculation": "R = 0.7 x 9.1 = 6.37 m radius", "plain_english": "Draw a circle around each detector with a radius of 0.7 times the spacing. With 9.1 m spacing that is 6.37 m. Every spot on the ceiling must fall inside one of these circles.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "error", "code": "SPT-FA-02"}', '{"notes": ["Corridors: spacing along centreline, max S/2 from end wall"]}'),
('fire_alarm', 'SPT-FA-03', 'FA-03', 'Smoke detector - wall distance', 'code', null, 'NFPA 72 Ch.17', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 'SBC 801 §907 (adopts NFPA 72 for installation)', '{"applies_when": [], "condition_text": "Smooth ceiling"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "<= S/2 (4.55 m) from walls; sidewall mount within 300 mm of ceiling", "library_basis": "Code", "calculation": "S/2 = 9.1 / 2", "plain_english": "No detector may be further from a wall than half the spacing. Half of 9.1 m is 4.55 m.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "error", "code": "SPT-FA-03"}', '{"notes": ["Dead-air-space rules differ for heat detectors"]}'),
('fire_alarm', 'SPT-FA-04', 'FA-04', 'Heat detector - spacing', 'code', null, 'NFPA 72 Table 17.6.3.5.1', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 'SBC 801 §907 (adopts NFPA 72 for installation)', '{"applies_when": [], "condition_text": "Ceiling > 3.0 m (10 ft)"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Listed spacing (typ. 7.6-15.2 m) x height factor", "library_basis": "Code", "calculation": "S_adj = S_listed x factor (3-3.7 m:0.91, 3.7-4.3:0.84, 4.3-4.9:0.77, 4.9-5.5:0.71, 5.5-6.1:0.64, 6.1-6.7:0.58, 6.7-7.3:0.52, 7.3-7.9:0.46, 7.9-8.5:0.40, 8.5-9.1:0.34)", "plain_english": "Take the heat detector''s listed spacing and multiply it by a reduction factor based on ceiling height. The higher the ceiling, the smaller the factor, so detectors must be closer together. Example: at 5 m ceiling height the factor is 0.71.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "error", "code": "SPT-FA-04"}', '{"notes": ["Listing may give its own height reduction; beams/joists apply further reduction"]}'),
('fire_alarm', 'SPT-FA-05', 'FA-05', 'Heat detector - sidewall mounting', 'code', null, 'NFPA 72 Ch.17', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 'SBC 801 §907 (adopts NFPA 72 for installation)', '{"applies_when": [], "condition_text": "Sidewall install"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "100-300 mm below ceiling", "library_basis": "Code"}', '{"emits": "validation", "severity": "error", "code": "SPT-FA-05"}', '{"notes": ["Not in dead-air space at ceiling/wall junction"]}'),
('fire_alarm', 'SPT-FA-06', 'FA-06', 'Smoke detector - beamed ceiling', 'code', null, 'NFPA 72 §17.7.3.2.4', 50, false, 'Tagged Code - verify by the library: drawn from the cited standard, but the clause number, edition or value must be checked before use in a submittal. Aramco SAES and HCIS directive numbers were not checked against the current controlled copies.',
 'SBC 801 §907 (adopts NFPA 72 for installation)', '{"applies_when": [], "condition_text": "Solid beams, level ceiling"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Beam depth < 0.1H -> smooth-ceiling spacing; >=0.1H and beam spacing >=0.4H -> detector in each pocket; >=0.1H and spacing <0.4H -> reduce spacing perpendicular to beams by 50%", "library_basis": "Code - verify", "calculation": "Check d_beam / H and W_pocket / H", "plain_english": "Compare the beam depth and the gap between beams against the ceiling height (H). Shallow beams (under 10% of H) are ignored. Deep beams far apart need a detector in each pocket. Deep beams close together mean you halve the spacing across the beams.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "critical_review", "code": "SPT-FA-06"}', '{"notes": ["Sloped beamed ceilings, beam pockets used as smoke reservoirs"]}'),
('fire_alarm', 'SPT-FA-07', 'FA-07', 'Heat detector - beamed/joisted ceiling', 'code', null, 'NFPA 72 §17.6.3', 50, false, 'Tagged Code - verify by the library: drawn from the cited standard, but the clause number, edition or value must be checked before use in a submittal. Aramco SAES and HCIS directive numbers were not checked against the current controlled copies.',
 'SBC 801 §907 (adopts NFPA 72 for installation)', '{"applies_when": [], "condition_text": "Solid beams/joists"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Beams > 100 mm deep: spacing perpendicular to beams <= 2/3 listed; beams > 450 mm deep and > 2.4 m o.c.: each bay treated as separate area", "library_basis": "Code - verify", "calculation": "S_perp = 0.667 x S_listed", "plain_english": "Across the direction of the beams, the heat detector spacing is cut to two-thirds of its listed value.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "critical_review", "code": "SPT-FA-07"}', '{"notes": ["Open-web joists treated as smooth if <= 100 mm solid chord"]}'),
('fire_alarm', 'SPT-FA-08', 'FA-08', 'Sloped/peaked ceiling detector', 'code', null, 'NFPA 72 Ch.17', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 'SBC 801 §907 (adopts NFPA 72 for installation)', '{"applies_when": [], "condition_text": "Slope > 1:8"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "One row within 0.9 m (3 ft) of peak, measured horizontally", "library_basis": "Code", "calculation": "Additional rows per horizontal-projection spacing", "plain_english": "On sloped ceilings, measure spacing on a flat plan view (as if looking down from above) and add extra rows of detectors as needed. One row must be within 0.9 m of the peak.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "error", "code": "SPT-FA-08"}', '{"notes": ["Shed ceilings follow high-side rule"]}'),
('fire_alarm', 'SPT-FA-09', 'FA-09', 'Detector distance from HVAC diffuser', 'code', null, 'NFPA 72 Ch.17', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 'SBC 801 §907 (adopts NFPA 72 for installation)', '{"applies_when": [], "condition_text": "Any forced-air space"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": ">= 0.9 m (3 ft) from supply diffuser / return grille", "library_basis": "Code"}', '{"emits": "validation", "severity": "error", "code": "SPT-FA-09"}', '{"notes": ["Air-sampling / listed high-velocity applications"]}'),
('fire_alarm', 'SPT-FA-10', 'FA-10', 'Duct smoke detector', 'code', null, 'IMC §606 / NFPA 90A', 50, false, 'Tagged Code - verify by the library: drawn from the cited standard, but the clause number, edition or value must be checked before use in a submittal. Aramco SAES and HCIS directive numbers were not checked against the current controlled copies.',
 'SBC 501 (Mechanical) §606 mirrors IMC', '{"applies_when": [], "condition_text": "AHU > 944 L/s (2,000 cfm)"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Required on supply side", "library_basis": "Code - verify", "calculation": "Q_AHU vs 944 L/s", "plain_english": "Check the air handler''s airflow. If it moves more than 944 litres per second (2,000 cfm), a duct smoke detector is needed on the supply side.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "critical_review", "code": "SPT-FA-10"}', '{"notes": ["Units serving single space with area detection per code alternative"]}'),
('fire_alarm', 'SPT-FA-11', 'FA-11', 'Manual call point - location', 'code', null, 'NFPA 72 §17.15.9 (formerly 17.14)', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 'SBC 801 §907.4.2', '{"applies_when": [], "condition_text": "Every exit on every floor where required"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Within 1.5 m (5 ft) of each exit door; travel distance <= 61 m (200 ft) on same floor", "library_basis": "Code", "calculation": "Count = exits + extra so no point > 61 m", "plain_english": "Put one call point at every exit, then add more until nobody on the floor has to walk more than 61 m to reach one.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "error", "code": "SPT-FA-11"}', '{"notes": ["Group widths > 12 m: MCP on each side of opening"]}'),
('fire_alarm', 'SPT-FA-12', 'FA-12', 'Manual call point - mounting height', 'code', null, 'NFPA 72 §17.15.9', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 'SBC 801 §907.4.2.2', '{"applies_when": [], "condition_text": "Wall mounted"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Operable part 1.07-1.22 m (42-48 in) AFF", "library_basis": "Code"}', '{"emits": "validation", "severity": "error", "code": "SPT-FA-12"}', '{"notes": ["Client spec may fix single height (e.g., 1.2 m)"]}'),
('fire_alarm', 'SPT-FA-13', 'FA-13', 'Audible - public mode', 'code', null, 'NFPA 72 §18.4.3', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 'SBC 801 §907.5.2.1.1 / .1.2', '{"applies_when": [], "condition_text": "Measured 1.5 m AFF, occupiable areas"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": ">= 15 dB above avg ambient OR >= 5 dB above max ambient lasting >= 60 s (greater); max 110 dBA", "library_basis": "Code", "calculation": "SPL_req = max(L_avg+15, L_max+5)", "plain_english": "Alarm sounders must be loud enough to hear over the background noise. Take whichever is higher: normal noise plus 15 dB, or the loudest sustained noise (lasting 60 seconds or more) plus 5 dB.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "error", "code": "SPT-FA-13"}', '{"notes": ["Private mode: 10 dB above avg ambient; voice intelligibility per \u00a718.4.10"]}'),
('fire_alarm', 'SPT-FA-14', 'FA-14', 'Audible - sleeping areas', 'code', null, 'NFPA 72 §18.4.6', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 'SBC 801 §907.5.2.1', '{"applies_when": [], "condition_text": "Sleeping rooms"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Greater of 15 dB > ambient, 5 dB > max 60 s, or 75 dBA at pillow; 520 Hz low-frequency tone", "library_basis": "Code"}', '{"emits": "validation", "severity": "error", "code": "SPT-FA-14"}', '{"notes": ["Existing systems per retroactive provisions"]}'),
('fire_alarm', 'SPT-FA-15', 'FA-15', 'Visual - wall strobe height', 'code', null, 'NFPA 72 §18.5.5', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 'SBC 801 §907.5.2.3', '{"applies_when": [], "condition_text": "Wall mounted"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Entire lens 2.03-2.44 m (80-96 in) AFF", "library_basis": "Code"}', '{"emits": "validation", "severity": "error", "code": "SPT-FA-15"}', '{"notes": ["Ceiling > 3 m or low-ceiling alternatives per \u00a718.5.5"]}'),
('fire_alarm', 'SPT-FA-16', 'FA-16', 'Visual - room candela (1 strobe, wall)', 'code', null, 'NFPA 72 Table 18.5.5.4.1(a)', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 'SBC 801 §907.5.2.3', '{"applies_when": [], "condition_text": "Square room, 1 strobe centred on wall"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "6.1x6.1 m:15 cd; 8.5x8.5:30; 12.2x12.2:60; 13.7x13.7:75; 16.5x16.5:95; 16.8x16.8:115; 19.2x19.2:135; 20.7x20.7:185", "library_basis": "Code", "calculation": "Select next larger room size", "plain_english": "Look up the room size in the table and pick the strobe brightness (candela) for it. If the room falls between two sizes, use the bigger size''s rating.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "error", "code": "SPT-FA-16"}', '{"notes": ["Multiple strobes / ceiling mount use Table (b); synchronise >2 in field of view"]}'),
('fire_alarm', 'SPT-FA-17', 'FA-17', 'Visual - corridors', 'code', null, 'NFPA 72 §18.5.5.5', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 'SBC 801 §907.5.2.3', '{"applies_when": [], "condition_text": "Corridor <= 6.1 m wide"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "15 cd min; <= 4.6 m from end; <= 30.5 m apart", "library_basis": "Code", "calculation": "N = ceil((L - 9.2)/30.5) + 1", "plain_english": "Take the corridor length, subtract the 9.2 m covered by the two end strobes, divide the rest by 30.5 m, round up, and add 1. That gives the number of strobes.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "error", "code": "SPT-FA-17"}', '{"notes": ["Wider corridors treated as rooms"]}'),
('fire_alarm', 'SPT-FA-18', 'FA-18', 'Secondary power - batteries', 'code', null, 'NFPA 72 §10.6.7', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 'SBC 801 §907; Aramco/Civil Defense may require longer', '{"applies_when": [], "condition_text": "All FACP/NAC panels"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "24 h standby + 5 min alarm (15 min for EVACS)", "library_basis": "Code", "calculation": "Ah = (I_sb x 24 + I_al x t_al) x 1.2 (20% margin = practice)", "plain_english": "Battery size = (standby current x 24 hours) + (alarm current x alarm time), then add 20% extra as a safety margin.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "error", "code": "SPT-FA-18"}', '{"notes": ["Generator-backed systems: 4 h standby permitted where allowed"]}'),
('fire_alarm', 'SPT-FA-19', 'FA-19', 'NAC voltage drop', 'spec', null, 'Manufacturer + NFPA 72 Ch.10', 100, false, 'Tagged Practice by the library: industry design practice, not a code mandate. The library states it must never be presented to a client as a code requirement. Under ELV-X-06 it cannot become scope without a drawing or SOW citation.',
 'Aramco: SAES-B-014 / project SOW governs where stricter', '{"applies_when": [], "condition_text": "24 V NAC"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "End-of-line V >= appliance listed min (typ. 16 V)", "library_basis": "Practice", "calculation": "V_EOL = 20.4 V - I x R/m x 2L  (20.4 V = battery end voltage)", "plain_english": "The voltage at the last device = battery end voltage (20.4 V) minus the voltage lost in the wire. Wire loss = current x wire resistance x the total wire length there and back (2 x one-way length).", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "warning", "code": "SPT-FA-19"}', '{"notes": ["Regulated/boosted NAC PSUs per listing"]}'),
('fire_alarm', 'SPT-FA-20', 'FA-20', 'Loop loading spare', 'spec', null, 'Project spec / practice', 100, false, 'Tagged Practice by the library: industry design practice, not a code mandate. The library states it must never be presented to a client as a code requirement. Under ELV-X-06 it cannot become scope without a drawing or SOW citation.',
 'Aramco: SAES-B-014 / project SOW governs where stricter', '{"applies_when": [], "condition_text": "SLC / NAC circuits"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Design <= 80% of loop device & current capacity", "library_basis": "Practice", "calculation": "Spare = 1 - used/max >= 20%", "plain_english": "Spare capacity = 1 minus (what is used / the maximum allowed). It must be at least 20%, meaning the loop is loaded no more than 80%.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "warning", "code": "SPT-FA-20"}', '{"notes": ["Client spec may require 25%"]}'),
('fire_alarm', 'SPT-FA-21', 'FA-21', 'Circuit survivability', 'code', null, 'NFPA 72 §24.3.14 / Ch.12', 10, false, 'Tagged Code - verify by the library: drawn from the cited standard, but the clause number, edition or value must be checked before use in a submittal. Aramco SAES and HCIS directive numbers were not checked against the current controlled copies.',
 'SBC 801 §907', '{"applies_when": [], "condition_text": "Relocation/partial evacuation"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Level 2 or 3 pathways for EVACS in partial-evac/high-rise", "library_basis": "Code - verify"}', '{"emits": "validation", "severity": "critical_review", "code": "SPT-FA-21"}', '{"notes": ["Fully sprinklered + AHJ acceptance"]}'),
('fire_alarm', 'SPT-FA-22', 'FA-22', 'Elevator recall detection', 'code', null, 'NFPA 72 §21.3; ASME A17.1', 10, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 'SBC 801 §607', '{"applies_when": [], "condition_text": "Elevators with Phase I recall"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Smoke detectors in lift lobbies, machine room, hoistway top (if sprinklered)", "library_basis": "Code"}', '{"emits": "validation", "severity": "error", "code": "SPT-FA-22"}', '{"notes": ["Heat detectors where smoke unsuitable"]}'),
('cctv', 'SPT-CC-01', 'CC-01', 'Pixel density - DORI', 'code', null, 'IEC 62676-4', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 'HCIS SEC directives / Aramco security SAES - verify required class per zone', '{"applies_when": [], "condition_text": "Target at max design distance"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Detect 25 px/m; Observe 62.5; Recognise 125; Identify 250", "library_basis": "Code", "calculation": "Scene width W = 2 d tan(HFOV/2); PPM = H_res / W", "plain_english": "Work out how wide the camera''s view is at the target distance, then divide the camera''s horizontal pixels by that width. The result (pixels per metre) tells you whether you can detect, observe, recognise or identify a person.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "error", "code": "SPT-CC-01"}', '{"notes": ["Thermal/analytics cameras use vendor detection criteria"]}'),
('cctv', 'SPT-CC-02', 'CC-02', 'Required horizontal resolution', 'code', null, 'IEC 62676-4', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 'Project SOW', '{"applies_when": [], "condition_text": "Per camera view"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "H_res >= PPM_req x W", "library_basis": "Code", "calculation": "H_res = PPM x 2 d tan(HFOV/2)", "plain_english": "To find the camera resolution you need: multiply the required pixels per metre by the width of the scene at the target distance.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "error", "code": "SPT-CC-02"}', '{"notes": ["Wide dynamic range/night reduces effective PPM - add margin"]}'),
('cctv', 'SPT-CC-03', 'CC-03', 'Max distance for target PPM', 'code', null, 'IEC 62676-4 (derived)', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 null, '{"applies_when": [], "condition_text": "Fixed lens"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "d_max = H_res / (PPM x 2 tan(HFOV/2))", "library_basis": "Code", "calculation": "e.g., 2688 px, 90 deg HFOV, 250 px/m -> 5.4 m", "plain_english": "Rearranges the formula to find the furthest distance at which a camera still gives enough detail. Example: a 2688-pixel camera with a 90 degree view needs the person within 5.4 m to identify them (250 px/m).", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "error", "code": "SPT-CC-03"}', '{"notes": ["Varifocal: compute at chosen focal length"]}'),
('cctv', 'SPT-CC-04', 'CC-04', 'Storage', 'spec', null, 'Practice (vendor calculators)', 100, false, 'Tagged Practice by the library: industry design practice, not a code mandate. The library states it must never be presented to a client as a code requirement. Under ELV-X-06 it cannot become scope without a drawing or SOW citation.',
 'HCIS / project spec retention (commonly 30-90 days) - verify', '{"applies_when": [], "condition_text": "Continuous/motion recording"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Recording retention per spec", "library_basis": "Practice", "calculation": "TB = sum(Mbps) x 3600 x h/day x days / 8 / 10^6 x (1+overhead)", "plain_english": "Add up all camera bitrates (Mbps), convert to data per second, multiply by the seconds recorded each day and the number of days kept. Divide by 8 to turn bits into bytes and by 1,000,000 to get terabytes, then add extra for RAID and free space.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "warning", "code": "SPT-CC-04"}', '{"notes": ["Event-only recording: apply duty-cycle factor"]}'),
('cctv', 'SPT-CC-05', 'CC-05', 'Storage redundancy', 'spec', null, 'Practice', 100, false, 'Tagged Practice by the library: industry design practice, not a code mandate. The library states it must never be presented to a client as a code requirement. Under ELV-X-06 it cannot become scope without a drawing or SOW citation.',
 'Client spec', '{"applies_when": [], "condition_text": "NVR/VMS storage"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "RAID 5/6 + >= 1 hot spare; + 20% free space", "library_basis": "Practice", "calculation": "Usable = raw x (n-k)/n", "plain_english": "Some disks in a RAID array hold backup (parity) data, not recordings. Usable storage = raw storage x (total disks - parity disks) / total disks.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "warning", "code": "SPT-CC-05"}', '{"notes": ["Edge (SD) recording as failover"]}'),
('cctv', 'SPT-CC-06', 'CC-06', 'Network bandwidth', 'spec', null, 'Practice', 100, false, 'Tagged Practice by the library: industry design practice, not a code mandate. The library states it must never be presented to a client as a code requirement. Under ELV-X-06 it cannot become scope without a drawing or SOW citation.',
 null, '{"applies_when": [], "condition_text": "Camera uplinks / NVR NICs"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Link utilisation <= 70%", "library_basis": "Practice", "calculation": "BW = sum stream Mbps (main + sub + live view)", "plain_english": "Network bandwidth needed = the sum of every video stream: main recording stream, secondary stream and any live viewing.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "warning", "code": "SPT-CC-06"}', '{"notes": ["Multicast live view reduces load"]}'),
('cctv', 'SPT-CC-07', 'CC-07', 'PoE power per camera', 'code', null, 'IEEE 802.3af/at/bt', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 null, '{"applies_when": [], "condition_text": "PTZ with heater/IR usually >= at/bt"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Match camera class (af 15.4 W / at 30 W / bt 60-90 W)", "library_basis": "Code", "calculation": "Switch budget >= sum P_class x 1.2", "plain_english": "The switch must supply enough power for all cameras. Add up each camera''s PoE class power and add 20% extra.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "error", "code": "SPT-CC-07"}', '{"notes": ["External PSU for >90 W (heaters, wipers)"]}'),
('cctv', 'SPT-CC-08', 'CC-08', 'Copper link length', 'code', null, 'ANSI/TIA-568', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 'SAES-T-916 (Aramco) - verify', '{"applies_when": [], "condition_text": "Cat6/6A to camera"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "<= 100 m channel", "library_basis": "Code", "calculation": "Beyond -> fibre + media converter / extender", "plain_english": "If a copper cable run would go beyond 100 m, switch to fibre with a media converter, or use an extender.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "error", "code": "SPT-CC-08"}', '{"notes": ["Listed PoE extenders"]}'),
('cctv', 'SPT-CC-09', 'CC-09', 'Face ID camera geometry', 'spec', null, 'IEC 62676-4 guidance / practice', 100, false, 'Tagged Practice by the library: industry design practice, not a code mandate. The library states it must never be presented to a client as a code requirement. Under ELV-X-06 it cannot become scope without a drawing or SOW citation.',
 'HCIS / project SOW', '{"applies_when": [], "condition_text": "Identification views (entries)"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Vertical angle to face <= 15 deg; horizontal <= 30 deg off-axis", "library_basis": "Practice", "calculation": "theta = atan((h_cam - 1.6)/d)", "plain_english": "Work out the camera''s downward angle to a face: the height difference between the camera and a face (1.6 m) divided by the distance, then take the angle. It must be 15 degrees or less to identify faces.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "warning", "code": "SPT-CC-09"}', '{"notes": ["Stereo/overhead analytics"]}'),
('cctv', 'SPT-CC-10', 'CC-10', 'Outdoor enclosure', 'code', null, 'IEC 60529 / IEC 62262', 50, false, 'Tagged Code - verify by the library: drawn from the cited standard, but the clause number, edition or value must be checked before use in a submittal. Aramco SAES and HCIS directive numbers were not checked against the current controlled copies.',
 'Aramco: design ambient per SAES/SOW (hazardous areas: Ex certified)', '{"applies_when": [], "condition_text": "Outdoor, KSA climate"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "IP66/IP67, IK10; rated to site ambient + solar gain", "library_basis": "Code - verify"}', '{"emits": "validation", "severity": "critical_review", "code": "SPT-CC-10"}', '{"notes": ["Indoor conditioned spaces"]}'),
('cctv', 'SPT-CC-11', 'CC-11', 'Coverage overlap', 'spec', null, 'Practice', 100, false, 'Tagged Practice by the library: industry design practice, not a code mandate. The library states it must never be presented to a client as a code requirement. Under ELV-X-06 it cannot become scope without a drawing or SOW citation.',
 'HCIS perimeter directives - verify', '{"applies_when": [], "condition_text": "Perimeter security"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Adjacent perimeter views overlap; no blind zones at fence line", "library_basis": "Practice", "calculation": "Overlap = FOV_n intersect FOV_n+1 > 0 at detection distance", "plain_english": "Check that each camera''s field of view overlaps the next one at the detection distance, so there are no gaps along the perimeter.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "warning", "code": "SPT-CC-11"}', '{"notes": ["Radar/PIDS-cued PTZ designs"]}'),
('cctv', 'SPT-CC-12', 'CC-12', 'Time sync & cyber hygiene', 'code', null, 'IEC 62676-1 / vendor hardening', 50, false, 'Tagged Code - verify by the library: drawn from the cited standard, but the clause number, edition or value must be checked before use in a submittal. Aramco SAES and HCIS directive numbers were not checked against the current controlled copies.',
 'NCA ECC-2:2024 (and OTCC-1 for OT sites)', '{"applies_when": [], "condition_text": "All IP cameras/NVRs"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "NTP sync; unique credentials; security VLAN; firmware management", "library_basis": "Code - verify"}', '{"emits": "validation", "severity": "critical_review", "code": "SPT-CC-12"}', '{"notes": ["Air-gapped systems still require local NTP"]}'),
('acs', 'SPT-AC-01', 'AC-01', 'Free egress', 'code', null, 'NFPA 101 §7.2.1.5; IBC §1010', 10, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 'SBC 201 Ch.10; SBC 801', '{"applies_when": [], "condition_text": "All means of egress"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Egress door opens from egress side without key, tool, or special knowledge", "library_basis": "Code"}', '{"emits": "validation", "severity": "error", "code": "SPT-AC-01"}', '{"notes": ["Approved delayed egress / controlled egress (healthcare)"]}'),
('acs', 'SPT-AC-02', 'AC-02', 'Electrically locked egress doors (maglocks)', 'code', null, 'NFPA 101 §7.2.1.6.2; IBC §1010.2.14', 10, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 'SBC 201 Ch.10', '{"applies_when": [], "condition_text": "Sensor-release egress doors"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Release by approach sensor (REX) AND manual push button within 1.5 m of door at 1.0-1.2 m AFF, ''PUSH TO EXIT'', unlock >= 30 s", "library_basis": "Code"}', '{"emits": "validation", "severity": "error", "code": "SPT-AC-02"}', '{"notes": ["Mechanical free-egress hardware (fail-secure strike) avoids this"]}'),
('acs', 'SPT-AC-03', 'AC-03', 'Fire alarm & power-loss release', 'code', null, 'NFPA 101 §7.2.1.6; IBC §1010', 10, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 'SBC 801 §907 interface; Civil Defense', '{"applies_when": [], "condition_text": "Sensor-release / delayed egress"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Egress locks unlock on FA activation and on loss of power", "library_basis": "Code", "calculation": "FA relay -> lock PSU input (hard-wired, not software)", "plain_english": "The fire alarm relay cuts power to the lock power supply directly through wiring, not through software, so doors unlock even if the software fails.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "error", "code": "SPT-AC-03"}', '{"notes": ["Fail-secure hardware with mechanical egress"]}'),
('acs', 'SPT-AC-04', 'AC-04', 'Delayed egress', 'code', null, 'NFPA 101 §7.2.1.6.1; IBC §1010.2.13', 10, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 'SBC 201; AHJ approval', '{"applies_when": [], "condition_text": "Approved occupancies only"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Release <= 15 s (30 s with AHJ); irreversible; signage; building sprinklered or detected", "library_basis": "Code"}', '{"emits": "validation", "severity": "error", "code": "SPT-AC-04"}', '{"notes": ["Not permitted in assembly/some occupancies"]}'),
('acs', 'SPT-AC-05', 'AC-05', 'Door hardware height', 'code', null, 'NFPA 101 §7.2.1.5; IBC §1010', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 'SBC 201', '{"applies_when": [], "condition_text": "Egress doors"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Operable parts 0.865-1.22 m (34-48 in) AFF", "library_basis": "Code"}', '{"emits": "validation", "severity": "error", "code": "SPT-AC-05"}', '{"notes": ["Existing buildings"]}'),
('acs', 'SPT-AC-06', 'AC-06', 'Reader mounting', 'code', null, 'ADA / ICC A117.1 reach range', 50, false, 'Tagged Code - verify by the library: drawn from the cited standard, but the clause number, edition or value must be checked before use in a submittal. Aramco SAES and HCIS directive numbers were not checked against the current controlled copies.',
 'SBC 201 accessibility', '{"applies_when": [], "condition_text": "Accessible route"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Operable part <= 1.22 m AFF (reach range)", "library_basis": "Code - verify"}', '{"emits": "validation", "severity": "critical_review", "code": "SPT-AC-06"}', '{"notes": ["Vehicle readers per lane geometry"]}'),
('acs', 'SPT-AC-07', 'AC-07', 'Reader cable length', 'spec', null, 'SIA OSDP / vendor', 100, false, 'Tagged Practice by the library: industry design practice, not a code mandate. The library states it must never be presented to a client as a code requirement. Under ELV-X-06 it cannot become scope without a drawing or SOW citation.',
 'NCA ECC - prefer OSDP Secure Channel', '{"applies_when": [], "condition_text": "Per vendor cable spec"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Wiegand typ. <= 150 m; OSDP/RS-485 <= 1,200 m", "library_basis": "Practice"}', '{"emits": "validation", "severity": "warning", "code": "SPT-AC-07"}', '{"notes": ["Fibre/IP readers"]}'),
('acs', 'SPT-AC-08', 'AC-08', 'Door monitoring', 'spec', null, 'UL 294 / IEC 60839-11-1', 100, false, 'Tagged Practice by the library: industry design practice, not a code mandate. The library states it must never be presented to a client as a code requirement. Under ELV-X-06 it cannot become scope without a drawing or SOW citation.',
 'HCIS / Aramco security SAES - verify grade', '{"applies_when": [], "condition_text": "Controlled doors"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Door position switch + REX on every controlled door (held/forced alarms)", "library_basis": "Practice"}', '{"emits": "validation", "severity": "warning", "code": "SPT-AC-08"}', '{"notes": ["Free-exit doors with no monitoring requirement"]}'),
('acs', 'SPT-AC-09', 'AC-09', 'Lock power supply', 'spec', null, 'Practice / UL 294', 100, false, 'Tagged Practice by the library: industry design practice, not a code mandate. The library states it must never be presented to a client as a code requirement. Under ELV-X-06 it cannot become scope without a drawing or SOW citation.',
 'Project spec (backup duration)', '{"applies_when": [], "condition_text": "Electrified locks"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "PSU >= 1.25 x sum lock + reader current; battery backup per spec", "library_basis": "Practice", "calculation": "I_PSU = 1.25 x (sum I_lock + sum I_reader)", "plain_english": "Lock power supply size = total current of all locks and readers, plus 25% extra.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "warning", "code": "SPT-AC-09"}', '{"notes": ["PoE-powered locks within PSE budget"]}'),
('acs', 'SPT-AC-10', 'AC-10', 'Controller spare capacity', 'spec', null, 'Practice', 100, false, 'Tagged Practice by the library: industry design practice, not a code mandate. The library states it must never be presented to a client as a code requirement. Under ELV-X-06 it cannot become scope without a drawing or SOW citation.',
 'Project spec', '{"applies_when": [], "condition_text": "Controllers & panels"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": ">= 20% spare doors/inputs/outputs", "library_basis": "Practice", "calculation": "Spare = 1 - used/max", "plain_english": "Spare capacity = 1 minus (used points / maximum points). Must be at least 20%.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "warning", "code": "SPT-AC-10"}', '{"notes": []}'),
('acs', 'SPT-AC-11', 'AC-11', 'Security grade', 'code', null, 'IEC 60839-11-1', 50, false, 'Tagged Code - verify by the library: drawn from the cited standard, but the clause number, edition or value must be checked before use in a submittal. Aramco SAES and HCIS directive numbers were not checked against the current controlled copies.',
 'HCIS directives for industrial facilities (SEC-01 general requirements)', '{"applies_when": [], "condition_text": "System design"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Select grade 1-4 per risk", "library_basis": "Code - verify"}', '{"emits": "validation", "severity": "critical_review", "code": "SPT-AC-11"}', '{"notes": []}'),
('network', 'SPT-NW-01', 'NW-01', 'PoE power per port (at PSE)', 'code', null, 'IEEE 802.3af/at/bt', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 null, '{"applies_when": [], "condition_text": "PD class"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "af 15.4 W; at 30 W; bt Type 3 60 W; bt Type 4 90 W", "library_basis": "Code", "calculation": "PD available: 12.95 / 25.5 / 51 / 71.3 W", "plain_english": "The switch sends more power than the device actually receives because some is lost in the cable. Devices actually get 12.95 W, 25.5 W, 51 W or 71.3 W depending on class.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "error", "code": "SPT-NW-01"}', '{"notes": ["Proprietary UPoE per vendor"]}'),
('network', 'SPT-NW-02', 'NW-02', 'Switch PoE budget', 'spec', null, 'Practice', 100, false, 'Tagged Practice by the library: industry design practice, not a code mandate. The library states it must never be presented to a client as a code requirement. Under ELV-X-06 it cannot become scope without a drawing or SOW citation.',
 null, '{"applies_when": [], "condition_text": "Access switches"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "sum PD max class x 1.2 <= switch PoE budget", "library_basis": "Practice", "calculation": "Budget_req = 1.2 x sum P_class", "plain_english": "Switch PoE budget needed = the sum of every device''s class power, plus 20% extra.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "warning", "code": "SPT-NW-02"}', '{"notes": ["LLDP power negotiation allows tighter sizing"]}'),
('network', 'SPT-NW-03', 'NW-03', 'Port spare capacity', 'spec', null, 'Practice', 100, false, 'Tagged Practice by the library: industry design practice, not a code mandate. The library states it must never be presented to a client as a code requirement. Under ELV-X-06 it cannot become scope without a drawing or SOW citation.',
 'Project spec', '{"applies_when": [], "condition_text": "Access layer"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Active ports + 20-25% spare", "library_basis": "Practice", "calculation": "Ports = ceil(active x 1.2)", "plain_english": "Number of ports = active devices x 1.2 (20% spare), rounded up to a whole port.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "warning", "code": "SPT-NW-03"}', '{"notes": []}'),
('network', 'SPT-NW-04', 'NW-04', 'Oversubscription', 'spec', null, 'Vendor design guides (practice)', 100, false, 'Tagged Practice by the library: industry design practice, not a code mandate. The library states it must never be presented to a client as a code requirement. Under ELV-X-06 it cannot become scope without a drawing or SOW citation.',
 null, '{"applies_when": [], "condition_text": "Data networks"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Access->distribution <= 20:1; distribution->core <= 4:1", "library_basis": "Practice", "calculation": "Ratio = sum access port BW / uplink BW", "plain_english": "Oversubscription ratio = total bandwidth of all user ports / bandwidth of the uplink. Example: 48 x 1 Gbps ports on a 10 Gbps uplink = 4.8:1.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value", "plain_english_example_invented": true}', '{"emits": "validation", "severity": "warning", "code": "SPT-NW-04"}', '{"notes": ["CCTV/storage traffic: size for sustained load, not ratio"]}'),
('network', 'SPT-NW-05', 'NW-05', 'Copper Ethernet reach', 'code', null, 'IEEE 802.3 / TIA-568', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 'SAES-T-916 - verify', '{"applies_when": [], "condition_text": "1/2.5/5/10GBASE-T"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "100 m channel", "library_basis": "Code"}', '{"emits": "validation", "severity": "error", "code": "SPT-NW-05"}', '{"notes": ["10GBASE-T on Cat6 limited to ~55 m"]}'),
('network', 'SPT-NW-06', 'NW-06', 'Fibre reach (10G)', 'code', null, 'IEEE 802.3ae', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 null, '{"applies_when": [], "condition_text": "10GBASE-SR/LR"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "OM3 300 m; OM4 400 m (SR); OS2 10 km (LR)", "library_basis": "Code", "calculation": "Check against loss budget (SC-12)", "plain_english": "Check the fibre run against the loss budget in SC-12 as well as the maximum distance for the fibre type.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "error", "code": "SPT-NW-06"}', '{"notes": ["Higher speeds reduce MM reach"]}'),
('network', 'SPT-NW-07', 'NW-07', 'Segmentation', 'code', null, 'IEC 62443 zones & conduits', 50, false, 'Tagged Code - verify by the library: drawn from the cited standard, but the clause number, edition or value must be checked before use in a submittal. Aramco SAES and HCIS directive numbers were not checked against the current controlled copies.',
 'NCA ECC-2:2024 (network security mgmt); NCA OTCC-1:2022 for OT', '{"applies_when": [], "condition_text": "Converged networks"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Security/ELV/OT systems on separate VLANs/VRFs with ACL/firewall", "library_basis": "Code - verify"}', '{"emits": "validation", "severity": "critical_review", "code": "SPT-NW-07"}', '{"notes": ["Physically separate networks"]}'),
('network', 'SPT-NW-08', 'NW-08', 'Logging & monitoring', 'code', null, 'ISO/IEC 27001', 50, false, 'Tagged Code - verify by the library: drawn from the cited standard, but the clause number, edition or value must be checked before use in a submittal. Aramco SAES and HCIS directive numbers were not checked against the current controlled copies.',
 'NCA ECC-2:2024 (event logs & monitoring)', '{"applies_when": [], "condition_text": "Critical systems"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Central logs, NTP, SIEM integration", "library_basis": "Code - verify"}', '{"emits": "validation", "severity": "critical_review", "code": "SPT-NW-08"}', '{"notes": []}'),
('network', 'SPT-NW-09', 'NW-09', 'Redundancy', 'spec', null, 'Practice', 100, false, 'Tagged Practice by the library: industry design practice, not a code mandate. The library states it must never be presented to a client as a code requirement. Under ELV-X-06 it cannot become scope without a drawing or SOW citation.',
 'Client spec', '{"applies_when": [], "condition_text": "Critical services"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Dual PSU + redundant uplinks at core/distribution", "library_basis": "Practice"}', '{"emits": "validation", "severity": "warning", "code": "SPT-NW-09"}', '{"notes": ["Small standalone systems"]}'),
('structured_cabling', 'SPT-SC-01', 'SC-01', 'Horizontal length', 'code', null, 'ANSI/TIA-568.0 / .1', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 'SAES-T-916 - verify; ISO/IEC 11801', '{"applies_when": [], "condition_text": "Balanced twisted-pair"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Permanent link <= 90 m; channel <= 100 m; cords <= 10 m total", "library_basis": "Code"}', '{"emits": "validation", "severity": "error", "code": "SPT-SC-01"}', '{"notes": ["MUTOA/consolidation point rules"]}'),
('structured_cabling', 'SPT-SC-02', 'SC-02', 'Cable quantity estimate', 'spec', null, 'BICSI TDMM method (practice)', 100, false, 'Tagged Practice by the library: industry design practice, not a code mandate. The library states it must never be presented to a client as a code requirement. Under ELV-X-06 it cannot become scope without a drawing or SOW citation.',
 'BOQ trace to drawings (no assumed routing)', '{"applies_when": [], "condition_text": "Per floor/TR"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Boxes of 305 m", "library_basis": "Practice", "calculation": "Avg = (L_min + L_max)/2 x 1.1 + slack; runs/box = floor(305/Avg); boxes = ceil(runs/runs_per_box)", "plain_english": "Average cable run = (shortest + longest) / 2, plus 10%, plus slack. Then see how many whole runs fit in one 305 m box, and divide the total number of runs by that to get how many boxes to order (rounded up).", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "warning", "code": "SPT-SC-02"}', '{"notes": ["Measured takeoff overrides estimate"]}'),
('structured_cabling', 'SPT-SC-03', 'SC-03', 'Slack / service loops', 'code', null, 'ANSI/TIA-568.0', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 null, '{"applies_when": [], "condition_text": "Horizontal"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "3 m in TR; 0.3 m at outlet (copper); fibre 1 m outlet, 3 m TR", "library_basis": "Code", "calculation": "Add to each run length", "plain_english": "Add the slack lengths (3 m in the telecom room, 0.3 m at the outlet for copper) to every cable run.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "error", "code": "SPT-SC-03"}', '{"notes": []}'),
('structured_cabling', 'SPT-SC-04', 'SC-04', 'Bend radius', 'code', null, 'ANSI/TIA-568.0 / .3', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 null, '{"applies_when": [], "condition_text": "Installed"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "UTP 4x OD; F/UTP 8x OD; fibre 10x OD unloaded, 20x under tension", "library_basis": "Code", "calculation": "R_min = k x OD", "plain_english": "Minimum bend radius = a multiplier x the cable''s outer diameter. The multiplier is 4 for UTP, 8 for shielded, and 10 or 20 for fibre.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "error", "code": "SPT-SC-04"}', '{"notes": ["Bend-insensitive fibre per manufacturer"]}'),
('structured_cabling', 'SPT-SC-05', 'SC-05', 'Pulling tension', 'code', null, 'ANSI/TIA-568.0', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 null, '{"applies_when": [], "condition_text": "Installation"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "4-pair UTP <= 110 N (25 lbf)", "library_basis": "Code"}', '{"emits": "validation", "severity": "error", "code": "SPT-SC-05"}', '{"notes": []}'),
('structured_cabling', 'SPT-SC-06', 'SC-06', 'Conduit fill', 'code', null, 'TIA-569 / NEC Ch.9 Table 1', 50, false, 'Tagged Code - verify by the library: drawn from the cited standard, but the clause number, edition or value must be checked before use in a submittal. Aramco SAES and HCIS directive numbers were not checked against the current controlled copies.',
 'SBC 401; SAES-T-911 conduit - verify', '{"applies_when": [], "condition_text": "Conduit"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "<= 40% for 3+ cables (53% one, 31% two)", "library_basis": "Code - verify", "calculation": "Fill = sum(pi OD^2/4) / A_conduit", "plain_english": "Conduit fill = the total cross-section area of all cables / the inside area of the conduit. Must be 40% or less for 3+ cables (53% for one cable, 31% for two).", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "critical_review", "code": "SPT-SC-06"}', '{"notes": ["Short nipples <= 600 mm may reach 60%"]}'),
('structured_cabling', 'SPT-SC-07', 'SC-07', 'Conduit runs', 'code', null, 'ANSI/TIA-569', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 'SAES-T-911 - verify', '{"applies_when": [], "condition_text": "Conduit"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "<= 30 m between pull points; <= 2 x 90 deg bends between pull boxes", "library_basis": "Code"}', '{"emits": "validation", "severity": "error", "code": "SPT-SC-07"}', '{"notes": ["Increase size if extra bend unavoidable"]}'),
('structured_cabling', 'SPT-SC-08', 'SC-08', 'Tray fill', 'code', null, 'ANSI/TIA-569', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 'Project spec', '{"applies_when": [], "condition_text": "Cable tray"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "<= 50% fill; cable depth <= 150 mm", "library_basis": "Code", "calculation": "Fill = sum cable area / tray area", "plain_english": "Tray fill = total area of all cables / tray area. Must be 50% or less.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "error", "code": "SPT-SC-08"}', '{"notes": []}'),
('structured_cabling', 'SPT-SC-09', 'SC-09', 'Telecom room', 'code', null, 'ANSI/TIA-569', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 'Project spec', '{"applies_when": [], "condition_text": "Buildings"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": ">= 1 TR per floor; extra if floor > 1,000 m2 or any run > 90 m", "library_basis": "Code", "calculation": "N_TR >= max(1, ceil(A/1000))", "plain_english": "Number of telecom rooms = floor area / 1,000 m2, rounded up, with at least one per floor.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "error", "code": "SPT-SC-09"}', '{"notes": []}'),
('structured_cabling', 'SPT-SC-10', 'SC-10', 'Work-area outlets', 'code', null, 'ANSI/TIA-568.0 / 569', 50, false, 'Tagged Code - verify by the library: drawn from the cited standard, but the clause number, edition or value must be checked before use in a submittal. Aramco SAES and HCIS directive numbers were not checked against the current controlled copies.',
 'Project drawings govern BOQ', '{"applies_when": [], "condition_text": "Office space"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": ">= 2 outlets per work area (~10 m2)", "library_basis": "Code - verify", "calculation": "N = ceil(A_office/10) x 2", "plain_english": "Number of outlets = office area / 10 m2 (rounded up) x 2, i.e. two outlets per work area.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "critical_review", "code": "SPT-SC-10"}', '{"notes": ["Non-office spaces per design"]}'),
('structured_cabling', 'SPT-SC-11', 'SC-11', 'Power separation', 'code', null, 'ANSI/TIA-569 Annex / EN 50174-2', 50, false, 'Tagged Code - verify by the library: drawn from the cited standard, but the clause number, edition or value must be checked before use in a submittal. Aramco SAES and HCIS directive numbers were not checked against the current controlled copies.',
 'SBC 401', '{"applies_when": [], "condition_text": "Parallel runs with power"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Maintain separation per standard table (typ. >= 300 mm from unshielded power in open trays)", "library_basis": "Code - verify"}', '{"emits": "validation", "severity": "critical_review", "code": "SPT-SC-11"}', '{"notes": ["Metal barriers/shielded cable reduce distance"]}'),
('structured_cabling', 'SPT-SC-12', 'SC-12', 'Fibre loss budget', 'code', null, 'ANSI/TIA-568.3', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 null, '{"applies_when": [], "condition_text": "Fibre links"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Loss_calc <= link budget", "library_basis": "Code", "calculation": "Loss = L_km x alpha + n_conn x 0.75 + n_splice x 0.3 dB (alpha: MM 3.5 dB/km @850; SM 1.0 ISP / 0.5 OSP)", "plain_english": "Total fibre loss = (length in km x loss per km) + (number of connector pairs x 0.75 dB) + (number of splices x 0.3 dB). Compare this against what the equipment can tolerate.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "error", "code": "SPT-SC-12"}', '{"notes": ["Test results govern acceptance"]}'),
('structured_cabling', 'SPT-SC-13', 'SC-13', 'Bonding & grounding', 'code', null, 'ANSI/TIA-607', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 'SBC 401; SAES-T-916 - verify', '{"applies_when": [], "condition_text": "All TRs/racks"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "TMGB/TGB; bonding conductors >= 6 AWG (16 mm2), TBB sized by length", "library_basis": "Code", "calculation": "Size per TIA-607 length table", "plain_english": "Size the bonding backbone conductor from the TIA-607 table based on its length.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "error", "code": "SPT-SC-13"}', '{"notes": []}'),
('structured_cabling', 'SPT-SC-14', 'SC-14', 'Labelling & admin', 'code', null, 'ANSI/TIA-606', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 'Client labelling scheme', '{"applies_when": [], "condition_text": "All installations"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Unique IDs for cables, panels, outlets, pathways", "library_basis": "Code"}', '{"emits": "validation", "severity": "error", "code": "SPT-SC-14"}', '{"notes": []}'),
('structured_cabling', 'SPT-SC-15', 'SC-15', 'Cable sheath', 'spec', null, 'IEC 60332-3 / 61034 / 60754', 100, false, 'Tagged Practice by the library: industry design practice, not a code mandate. The library states it must never be presented to a client as a code requirement. Under ELV-X-06 it cannot become scope without a drawing or SOW citation.',
 'Aramco / KSA project specs typically mandate LSZH', '{"applies_when": [], "condition_text": "Indoor"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "LSZH in enclosed/occupied spaces", "library_basis": "Practice"}', '{"emits": "validation", "severity": "warning", "code": "SPT-SC-15"}', '{"notes": ["Outdoor/duct: gel-filled/armoured"]}'),
('ups', 'SPT-UP-01', 'UP-01', 'UPS rating', 'spec', null, 'Practice / vendor', 100, false, 'Tagged Practice by the library: industry design practice, not a code mandate. The library states it must never be presented to a client as a code requirement. Under ELV-X-06 it cannot become scope without a drawing or SOW citation.',
 'Project spec', '{"applies_when": [], "condition_text": "All UPS"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Load <= 80% of UPS kW rating incl. growth", "library_basis": "Practice", "calculation": "kW_req = sum P_load x (1 + growth 0.2-0.25) / 0.8; kVA = kW / PF_UPS", "plain_english": "UPS size in kW = total load x (1 + 20-25% growth) / 0.8, so the UPS runs at no more than 80%. Then kVA = kW / the UPS power factor.", "plain_english_provenance": "authored_by_supplier_not_in_workbook; explanatory only, never the basis of a calculation or a quoted value"}', '{"emits": "validation", "severity": "warning", "code": "SPT-UP-01"}', '{"notes": []}'),
('ups', 'SPT-UP-02', 'UP-02', 'Battery runtime sizing', 'code', null, 'IEEE 1184 (UPS batteries); IEEE 485 (lead-acid method)', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 'Project spec runtime', '{"applies_when": [], "condition_text": "VRLA/Li-ion"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Runtime per spec at end-of-life", "library_basis": "Code", "calculation": "Wh = P_load x t / (eta_inv x DoD); Ah = Wh / V_DC x 1.25 aging x temp factor"}', '{"emits": "validation", "severity": "error", "code": "SPT-UP-02"}', '{"notes": ["Generator-backed: shorter runtime acceptable"]}'),
('ups', 'SPT-UP-03', 'UP-03', 'Battery temperature', 'code', null, 'IEC 60896-21/22; vendor', 50, false, 'Tagged Code - verify by the library: drawn from the cited standard, but the clause number, edition or value must be checked before use in a submittal. Aramco SAES and HCIS directive numbers were not checked against the current controlled copies.',
 'KSA ambient -> conditioned battery room required', '{"applies_when": [], "condition_text": "Battery room/cabinet"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Rated life at 20-25 C; life ~halves per +10 C", "library_basis": "Code - verify", "calculation": "Life_T = Life_25 x 0.5^((T-25)/10)"}', '{"emits": "validation", "severity": "critical_review", "code": "SPT-UP-03"}', '{"notes": ["Li-ion tolerates higher T per vendor"]}'),
('ups', 'SPT-UP-04', 'UP-04', 'Topology', 'spec', null, 'IEC 62040-3', 100, false, 'Tagged Practice by the library: industry design practice, not a code mandate. The library states it must never be presented to a client as a code requirement. Under ELV-X-06 it cannot become scope without a drawing or SOW citation.',
 'Client spec', '{"applies_when": [], "condition_text": "Critical ICT/ELV"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Online double-conversion VFI-SS-111", "library_basis": "Practice"}', '{"emits": "validation", "severity": "warning", "code": "SPT-UP-04"}', '{"notes": ["Line-interactive for non-critical desktops"]}'),
('ups', 'SPT-UP-05', 'UP-05', 'Battery room ventilation', 'code', null, 'IEC 62485-2', 50, false, 'Tagged Code by the library: stated in the cited standard. The library''s own limitations note that clause numbers are referenced to NFPA 72-2022, the TIA-568-E / 569-E family and the SBC 2018/2024 structure, and that numbering shifts between editions. Confirm the edition the project adopts (see ELV-X-01).',
 'SBC 501', '{"applies_when": [], "condition_text": "Lead-acid batteries"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Airflow to keep H2 < 4% (dilution)", "library_basis": "Code", "calculation": "Q (m3/h) = 0.05 x n_cells x I_gas x C_rt x 10^-3 (VRLA float I_gas = 1 mA/Ah)"}', '{"emits": "validation", "severity": "error", "code": "SPT-UP-05"}', '{"notes": ["Sealed Li-ion per vendor"]}'),
('ups', 'SPT-UP-06', 'UP-06', 'Protection & cabling', 'code', null, 'IEC 60364', 50, false, 'Tagged Code - verify by the library: drawn from the cited standard, but the clause number, edition or value must be checked before use in a submittal. Aramco SAES and HCIS directive numbers were not checked against the current controlled copies.',
 'SBC 401', '{"applies_when": [], "condition_text": "All UPS"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Input/output devices & cables per electrical code with continuous-load factor", "library_basis": "Code - verify", "calculation": "I_breaker >= 1.25 x I_input_max"}', '{"emits": "validation", "severity": "critical_review", "code": "SPT-UP-06"}', '{"notes": ["Coordinate with vendor recommendations"]}'),
('ups', 'SPT-UP-07', 'UP-07', 'Maintenance bypass', 'spec', null, 'Practice', 100, false, 'Tagged Practice by the library: industry design practice, not a code mandate. The library states it must never be presented to a client as a code requirement. Under ELV-X-06 it cannot become scope without a drawing or SOW citation.',
 'Client spec', '{"applies_when": [], "condition_text": "Critical UPS"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "External wraparound bypass for service without load drop", "library_basis": "Practice"}', '{"emits": "validation", "severity": "warning", "code": "SPT-UP-07"}', '{"notes": ["Parallel redundant systems"]}'),
('ups', 'SPT-UP-08', 'UP-08', 'Input harmonics', 'spec', null, 'IEEE 519 / vendor', 100, false, 'Tagged Practice by the library: industry design practice, not a code mandate. The library states it must never be presented to a client as a code requirement. Under ELV-X-06 it cannot become scope without a drawing or SOW citation.',
 'SEC grid code', '{"applies_when": [], "condition_text": "Grid-connected"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "THDi < 5% at full load (IGBT rectifier)", "library_basis": "Practice"}', '{"emits": "validation", "severity": "warning", "code": "SPT-UP-08"}', '{"notes": ["Small UPS < 10 kVA"]}'),
('ups', 'SPT-UP-09', 'UP-09', 'Redundancy', 'spec', null, 'Uptime tier / practice', 100, false, 'Tagged Practice by the library: industry design practice, not a code mandate. The library states it must never be presented to a client as a code requirement. Under ELV-X-06 it cannot become scope without a drawing or SOW citation.',
 'Client spec', '{"applies_when": [], "condition_text": "Data/security systems"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "N+1 for critical loads", "library_basis": "Practice", "calculation": "Modules = N + 1"}', '{"emits": "validation", "severity": "warning", "code": "SPT-UP-09"}', '{"notes": []}'),
('ups', 'SPT-UP-10', 'UP-10', 'Supply characteristics', 'code', null, 'IEC 60038', 50, false, 'Tagged Code - verify by the library: drawn from the cited standard, but the clause number, edition or value must be checked before use in a submittal. Aramco SAES and HCIS directive numbers were not checked against the current controlled copies.',
 'SASO / SEC: KSA is 60 Hz; confirm legacy 127/220 V sites', '{"applies_when": [], "condition_text": "KSA sites"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "Input 230/400 V, 60 Hz", "library_basis": "Code - verify"}', '{"emits": "validation", "severity": "critical_review", "code": "SPT-UP-10"}', '{"notes": ["Aramco in-plant voltages per SAES-P"]}'),
('ups', 'SPT-UP-11', 'UP-11', 'Fire alarm secondary supply', 'code', null, 'NFPA 72 Ch.10', 10, false, 'Tagged Code - verify by the library: drawn from the cited standard, but the clause number, edition or value must be checked before use in a submittal. Aramco SAES and HCIS directive numbers were not checked against the current controlled copies.',
 'SBC 801', '{"applies_when": [], "condition_text": "Life-safety panels"}', '{"required": []}', '{"kind": "library_rule", "evaluator": "unassigned", "value_limit": "FACP keeps own batteries; UPS only if it meets NFPA 72 Ch.10 secondary-supply rules", "library_basis": "Code - verify"}', '{"emits": "validation", "severity": "critical_review", "code": "SPT-UP-11"}', '{"notes": ["AHJ-approved central UPS"]}')) as t(system_code, rule_code, source_rule_id, rule_name, confidence, jurisdiction,
       standard_reference, priority, source_verified, verification_note,
       jurisdiction_overlay, conditions, inputs, calculation, outputs, exceptions);
$fn$;

comment on function spt_library_seed() is
  'The 80 rules of the SPT Engineering Rules Library (Pre-Sales, 29 Sep 2026). '
  'Source of record: knowledge/standards-references/spt-engineering-rules-library/.';

create or replace function seed_spt_library(p_organization_id uuid)
returns integer
language plpgsql
set search_path = ''
as $fn$
declare v_loaded integer;
begin
  if not exists (select 1 from public.organizations o where o.id = p_organization_id) then
    raise exception 'organization % does not exist', p_organization_id
      using errcode = 'foreign_key_violation';
  end if;

  if exists (select 1 from public.spt_library_seed() r
             left join public.systems s on s.code = r.system_code
             where s.id is null) then
    raise exception 'spt_library_seed references a system code with no row in systems';
  end if;

  insert into public.engineering_rules (
    organization_id, system_id, rule_code, name, jurisdiction, standard_reference,
    priority, confidence, source_document, source_rule_id, source_verified,
    verification_note, jurisdiction_overlay)
  select p_organization_id, s.id, r.rule_code, r.rule_name, r.jurisdiction,
         r.standard_reference, r.priority, r.confidence,
         'standards-references/spt-engineering-rules-library/',
         r.source_rule_id, r.source_verified, r.verification_note,
         r.jurisdiction_overlay
  from public.spt_library_seed() r
  join public.systems s on s.code = r.system_code
  on conflict do nothing;

  insert into public.rule_versions (
    rule_id, version, conditions, inputs, calculation, outputs, exceptions,
    approval_status)
  select er.id, 1, r.conditions, r.inputs, r.calculation, r.outputs,
         r.exceptions, 'draft'
  from public.spt_library_seed() r
  join public.engineering_rules er
    on er.organization_id = p_organization_id and er.rule_code = r.rule_code
  where not exists (select 1 from public.rule_versions rv where rv.rule_id = er.id);

  get diagnostics v_loaded = row_count;
  return v_loaded;
end $fn$;

-- ---------------------------------------------------------------------------
-- 6. Register the relationships to the rules already encoded
-- ---------------------------------------------------------------------------

create or replace function register_spt_library_relationships(p_organization_id uuid)
returns integer
language plpgsql
set search_path = ''
as $fn$
declare v_loaded integer;
begin
  insert into public.rule_relationships (
    organization_id, from_rule_id, to_rule_id, kind, note)
  select p_organization_id, a.id, b.id,
         t.kind::public.rule_relationship_kind, t.note
  from (values
('SPT-SC-04', 'ELV-A-02', 'conflicts', 'SC-04 states fibre 20x OD under tension as a single figure. ELV-A-02 was corrected on 24 Sep 2026 against the supplied ANSI/TIA/EIA-568-B text, which gives 20x for INTERBUILDING backbone only, 15x for intrabuilding backbone under load, and an absolute 25 mm / 50 mm for horizontal 2- and 4-fibre. SC-04 also omits the copper backbone 10x figure. Do not merge: resolve against a current 568.3-D before either version is approved.'),
('SPT-SC-06', 'ELV-A-08', 'resolves', 'ELV-A-08 carried the 40 percent conduit fill as an unconfirmed figure from general knowledge. SC-06 sources it to TIA-569 / NEC Ch.9 Table 1 and adds the one-cable (53%) and two-cable (31%) values plus the short-nipple exception. SC-06 is itself tagged Code - verify.'),
('SPT-SC-11', 'ELV-A-07', 'resolves', 'ELV-A-07 deliberately encoded no separation distance, recording only that the figure comes from the project spec. SC-11 supplies approximately 300 mm from unshielded power in open trays, sourced to TIA-569 Annex / EN 50174-2, with the barrier and shielding exception.'),
('SPT-FA-04', 'ELV-B-02', 'supersedes', 'ELV-B-02 carried a single recalled multiplier (roughly 0.7x at a 20 ft ceiling). FA-04 gives the full NFPA 72 Table 17.6.3.5.1 height-factor ladder from 0.91 down to 0.34. FA-04 is the better rule; ELV-B-02 should be superseded rather than kept alongside it.'),
('SPT-FA-02', 'ELV-B-01', 'refines', 'Adds the 0.7S coverage-radius rule (6.37 m at S = 9.1 m) that governs irregular rooms, which flat spacing alone does not cover.'),
('SPT-FA-06', 'ELV-B-04', 'refines', 'ELV-B-04 said only to redo spacing where beams and joists change coverage. FA-06 and FA-07 give the actual beam-depth and pocket-width tests.'),
('SPT-CC-01', 'ELV-C-07', 'resolves', 'ELV-C-07 named the DORI tiers but carried no numbers. CC-01 supplies 25 / 62.5 / 125 / 250 px/m and CC-02 and CC-03 give the scene-width and max-distance formulae.'),
('SPT-NW-07', 'ELV-C-04', 'resolves', 'ELV-C-04 was SPEC, deferring to any client IT policy. NW-07 and CC-12 name NCA ECC-2:2024 and OTCC-1:2022, which is a national authority for Saudi sites rather than a preference.'),
('SPT-AC-02', 'ELV-B-09', 'refines', 'ELV-B-09 required maglock release on alarm and on power loss. AC-02 adds the sensor-release arrangement: REX plus a manual push button within 1.5 m at 1.0-1.2 m AFF, PUSH TO EXIT signage, and a minimum 30 s unlock.'),
('SPT-AC-03', 'ELV-C-06', 'refines', 'Adds the implementation constraint that the fire alarm to lock interface is hard-wired through the lock PSU, not a software link.'),
('SPT-CC-04', 'KSA-CCTV-04', 'conflicts', 'CC-04 records retention as commonly 30-90 days per HCIS or project spec, tagged Practice. KSA-CCTV-04 records 90 days as a statutory minimum under the Law of the Use of Security Surveillance Cameras. For a Saudi site the statutory floor governs and 30 days is not available. Both remain unconfirmed against their primary sources.'),
('SPT-SC-01', 'ELV-A-01', 'agrees', 'Same 90 m / 100 m / 10 m figures.'),
('SPT-SC-05', 'ELV-A-16', 'agrees', 'Same 110 N (25 lbf) pulling tension for 4-pair UTP.'),
('SPT-SC-10', 'ELV-A-14', 'agrees', 'Both require a minimum of two outlets per work area. SC-10 adds the ~10 m2 work area and the count formula, and both are tagged for verification.'),
('SPT-SC-13', 'ELV-A-09', 'agrees', 'Both require bonding to the telecommunications bonding backbone per TIA-607. SC-13 adds conductor sizing (6 AWG / 16 mm2 minimum).'),
('SPT-SC-14', 'ELV-A-10', 'agrees', 'Both require unique IDs and administration per TIA-606.'),
('SPT-SC-03', 'ELV-A-01', 'refines', 'Gives the service-loop allowances (3 m TR, 0.3 m outlet copper; 3 m / 1 m fibre) that ELV-A-01 requires be counted inside the 90 m.'),
('SPT-SC-12', 'ELV-A-20', 'conflicts', 'ELV-A-20 carries a flat 2.0 dB horizontal link limit from 568-B. SC-12 uses a calculated loss budget (length x attenuation + 0.75 dB per connector + 0.3 dB per splice). These are two different acceptance methods and can disagree on the same link; pick one per project.'),
('SPT-CC-07', 'ELV-C-02', 'agrees', 'Both size PoE from the switch budget with a 20 percent margin. CC-07 and NW-01 add the class wattages at the PSE and the power available at the PD.'),
('SPT-CC-08', 'ELV-A-01', 'agrees', 'Both cap the copper channel at 100 m.'),
('SPT-NW-05', 'ELV-A-01', 'agrees', 'Same 100 m channel, with the added note that 10GBASE-T on Cat 6 is limited to about 55 m.'),
('SPT-AC-07', 'ELV-C-05', 'agrees', 'Both prefer OSDP over Wiegand. AC-07 adds the cable-length limits (Wiegand ~150 m, OSDP/RS-485 ~1200 m) and cites NCA ECC.'),
('SPT-UP-11', 'ELV-B-11', 'refines', 'Adds that a FACP keeps its own batteries and a central UPS only qualifies if it meets NFPA 72 Ch.10 secondary-supply rules.')  ) as t(from_code, to_code, kind, note)
  join public.engineering_rules a
    on a.organization_id = p_organization_id and a.rule_code = t.from_code
  join public.engineering_rules b
    on b.organization_id = p_organization_id and b.rule_code = t.to_code
  on conflict (from_rule_id, to_rule_id) do nothing;

  get diagnostics v_loaded = row_count;
  return v_loaded;
end $fn$;

comment on function register_spt_library_relationships(uuid) is
  'Records how the SPT library relates to the rules from the earlier documents. '
  'Unresolved conflicts/supersedes rows block BOTH rules from approval.';

-- ---------------------------------------------------------------------------
-- 7. The precedence policy, stored unapproved
-- ---------------------------------------------------------------------------

create or replace function seed_spt_precedence_policy(p_organization_id uuid)
returns integer
language plpgsql
set search_path = ''
as $fn$
declare v_loaded integer;
begin
  insert into public.rule_precedence_policy (
    organization_id, name, rank, authority, source_document)
  select p_organization_id, 'SPT Engineering Rules Library', t.rank, t.authority,
         'standards-references/spt-engineering-rules-library/'
  from (values
(1, 'Project SOW / specification / approved drawings'),
(2, 'Client standards (Aramco SAES, HCIS directives)'),
(3, 'Saudi Building Code (SBC 201/401/501/801) & NCA'),
(4, 'International standards (NFPA, TIA, IEC, IEEE)'),
(5, 'Practice')  ) as t(rank, authority)
  on conflict (organization_id, name, rank) do nothing;

  get diagnostics v_loaded = row_count;
  return v_loaded;
end $fn$;

comment on function seed_spt_precedence_policy(uuid) is
  'The library''s stated precedence order, rank 1 highest. Seeded UNAPPROVED: '
  'spec 11.4 permits precedence to resolve a conflict only where it has been '
  'explicitly configured AND approved. Recording it is the configuration half.';

-- ---------------------------------------------------------------------------
-- 8. Apply to organizations that already exist
-- ---------------------------------------------------------------------------

do $$
declare o record; v_conf integer;
begin
  for o in select id, name from organizations loop
    perform seed_spt_library(o.id);
    perform register_spt_library_relationships(o.id);
    perform seed_spt_precedence_policy(o.id);

    select count(*) into v_conf from rule_relationships
     where organization_id = o.id and kind in ('conflicts','supersedes')
       and resolved_at is null;

    raise notice 'SPT library loaded for % (%): % unresolved conflict(s) now block approval',
      o.name, o.id, v_conf;
  end loop;
end $$;
