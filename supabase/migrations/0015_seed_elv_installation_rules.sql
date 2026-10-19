-- 0015_seed_elv_installation_rules
--
-- Encodes the 42 rules of the ELV & Telecom Installation Rule Guide Book
-- (SmartPage, 21 Sep 2026) into the 0005 rules framework. This is the
-- "reviewed encoding" step of the chain in knowledge/README.md:
--
--   source material (knowledge/)  ->  reviewed encoding (here)
--     ->  versioned DB record  ->  approval  ->  usable by the platform
--
-- WHY THIS IS NOT A BREACH OF 0012. That migration forbids an agent adding
-- engineering rules, because an invented rule flows into a BOQ carrying the
-- appearance of engineering authority. Nothing here is invented: every row
-- transcribes a numbered rule from a SmartPage-authored document, and the files
-- under knowledge/ hold the same text with its basis note. Where the guide says
-- a figure came from general knowledge rather than an opened standard, that is
-- recorded in verification_note rather than quietly dropped.
--
-- NOTHING SEEDED HERE CAN EXECUTE. Every rule_version is inserted as 'draft'.
-- Only an Engineering Manager holding rule.approve can move a version to
-- approved/active, and spec 11.1 requires its tests to pass first. The tests
-- seeded below sit at 'not_run' because there is no evaluator yet: the
-- expression language is deliberately deferred until real rules exist
-- (ARCHITECTURE.md 9.4, D-2). These are those rules. Designing that language is
-- the next piece of work this migration unblocks, and it is not done here.
--
-- Idempotent, and safe to run per organization at any time.

-- ---------------------------------------------------------------------------
-- Two further systems
-- ---------------------------------------------------------------------------
-- 0012 seeded the three systems named in spec 5.1 and noted that `systems` is a
-- table rather than an enum precisely so a fourth is a row, not a migration.
-- Parts A and D of the guide are two more.

insert into systems (code, name) values
  ('structured_cabling',     'Structured Cabling'),
  ('outdoor_infrastructure', 'Outdoor Infrastructure and Mast')
on conflict (code) do nothing;

-- ---------------------------------------------------------------------------
-- The rule set, as data
-- ---------------------------------------------------------------------------
--
-- Held in a function rather than inline so the identity rows and the version
-- payloads are written from one list and cannot drift apart.
--
-- Payload shape. conditions/inputs/calculation/outputs/exceptions are opaque
-- versioned JSONB with a pluggable evaluator (ARCHITECTURE.md 9.4). The shape
-- below is a first proposal drawn from these 42 rules, not a committed schema:
--
--   conditions  {"applies_when": [{"fact","op","value"}]}   empty = always
--   inputs      {"required": [{"key","type"}]}
--   calculation {"kind", "evaluator", ...kind-specific keys}
--   outputs     {"emits", "severity", "code"}
--   exceptions  {"notes": [...]}
--
-- `evaluator` is "unassigned" on every rule but X-06, which is the one rule
-- already enforced in SQL (0014). That is deliberate and honest: it marks the
-- 41 rules that are stored and traceable but not yet executable.
--
-- `priority` orders rules for execution and presentation. It does NOT authorize
-- silent conflict resolution: spec 11.4 requires a genuine conflict to surface
-- both sources and halt unless a precedence policy has been explicitly approved.
-- Scheme used: 10 life-safety interlocks, 50 CODE, 100 SPEC, 150 LOCAL.
--
-- `jurisdiction` is set only where the rule is genuinely bounded by one
-- jurisdiction (the Nigerian generator rules). It is left null for standards
-- based rules, because which edition binds is a property of the project SOW and
-- the AHJ, not of the rule (see X-01).

create or replace function elv_rule_seed()
returns table (
  system_code        text,
  rule_code          text,
  source_rule_id     text,
  rule_name          text,
  confidence         public.rule_confidence,
  jurisdiction       text,
  standard_reference text,
  priority           integer,
  source_verified    boolean,
  verification_note  text,
  conditions         jsonb,
  inputs             jsonb,
  calculation        jsonb,
  outputs            jsonb,
  exceptions         jsonb
)
language sql
immutable
set search_path = ''
as $fn$
select
  t.system_code,
  t.rule_code,
  t.source_rule_id,
  t.rule_name,
  t.confidence::public.rule_confidence,
  t.jurisdiction,
  t.standard_reference,
  t.priority,
  t.source_verified,
  t.verification_note,
  t.conditions::jsonb,
  t.inputs::jsonb,
  t.calculation::jsonb,
  t.outputs::jsonb,
  t.exceptions::jsonb
from (values

-- === Part A: Structured cabling (ANSI/TIA-568, NEC Article 800) =============

('structured_cabling','ELV-A-01','A-01',
 'Horizontal permanent link and channel length limit',
 'code', null, 'ANSI/TIA-568.2-D', 50, false,
 'The 90 m permanent link is TIA-568.2-D. The 10 m patch and equipment cord allowance comes from general knowledge, not an opened standard. The Cables NYC page cited in the source text does not state the 90 m limit at all. Confirm both against a licensed copy of the current edition.',
 '{"applies_when":[{"fact":"link.media","op":"eq","value":"copper_horizontal"}]}',
 '{"required":[{"key":"link.pulled_length_m","type":"number"},{"key":"link.patch_cord_total_m","type":"number"}]}',
 '{"kind":"limit","evaluator":"unassigned","permanent_link_max_m":90,"channel_max_m":100,"cord_allowance_max_m":10,"measure":"pulled_length_including_service_loops"}',
 '{"emits":"validation","severity":"error","code":"ELV-A-01-LENGTH"}',
 '{"notes":["Service loops count toward the 90 m. Measure pulled length, not point-to-point distance."]}'),

('structured_cabling','ELV-A-02','A-02',
 'Minimum bend radius, copper and fibre',
 'code', null, 'ANSI/TIA-568', 50, false,
 'The 4x outside-diameter figure is confirmed in the Elliott Electric reference, not in TIA itself as opened. The same reference shows different bend-radius figures under ISO DIS 11801, so confirm which cabling standard the project uses.',
 '{"applies_when":[]}',
 '{"required":[{"key":"cable.outside_diameter_mm","type":"number"},{"key":"route.min_bend_radius_mm","type":"number"},{"key":"cable.datasheet_min_bend_radius_mm","type":"number"}]}',
 '{"kind":"limit","evaluator":"unassigned","basis":"cable_outside_diameter","utp_installed_multiplier":4,"fibre_installed_multiplier":10,"fibre_pulling_multiplier":20,"use":"stricter_of_standard_and_datasheet"}',
 '{"emits":"validation","severity":"error","code":"ELV-A-02-BEND"}',
 '{"notes":["Cat 6A and shielded cable datasheets are commonly stricter than 4x and then govern."]}'),

('structured_cabling','ELV-A-03','A-03',
 'Maximum pair untwist at termination',
 'code', null, 'ANSI/TIA-568.2-D', 50, true,
 'Stated directly in the Cables NYC guide, which was opened. The TIA clause number has not been read.',
 '{"applies_when":[{"fact":"termination.media","op":"eq","value":"twisted_pair"}]}',
 '{"required":[{"key":"termination.untwist_mm","type":"number"}]}',
 '{"kind":"limit","evaluator":"unassigned","max_untwist_mm":13}',
 '{"emits":"validation","severity":"error","code":"ELV-A-03-UNTWIST"}',
 '{"notes":["Excess untwist raises crosstalk and can stop 10GBASE-T from passing certification."]}'),

('structured_cabling','ELV-A-04','A-04',
 'Cable support interval and prohibited supports',
 'spec', null, 'BICSI practice', 100, true,
 'The 4 to 5 ft interval is contractor and BICSI practice, not a TIA number. It binds only where the SOW or drawing calls it out.',
 '{"applies_when":[]}',
 '{"required":[{"key":"pathway.support_interval_ft","type":"number"},{"key":"pathway.support_type","type":"string"}]}',
 '{"kind":"limit","evaluator":"unassigned","support_interval_min_ft":4,"support_interval_max_ft":5,"permitted_supports":["j_hook","tray","conduit"],"prohibited_supports":["ceiling_tile","grid_wire","pipe","ductwork"]}',
 '{"emits":"validation","severity":"warning","code":"ELV-A-04-SUPPORT"}',
 '{"notes":["Use the support type shown on the drawings."]}'),

('structured_cabling','ELV-A-05','A-05',
 'Cable listing must match the space (CMP, CMR, CM)',
 'code', null, 'NEC Article 800', 50, true,
 'Summarised by the Cables NYC page, which was opened. Cite the clause from the NEC edition the AHJ has adopted.',
 '{"applies_when":[{"fact":"space.type","op":"in","value":["plenum","riser","general"]}]}',
 '{"required":[{"key":"space.type","type":"string"},{"key":"cable.listing","type":"string"}]}',
 '{"kind":"selection","evaluator":"unassigned","map":{"plenum":"CMP","riser":"CMR","general":"CM"},"substitution":"higher_rating_may_replace_lower_never_the_reverse"}',
 '{"emits":"validation","severity":"error","code":"ELV-A-05-LISTING"}',
 '{"notes":["Air-handling space takes CMP, vertical shaft takes CMR, and CM is only for non-plenum non-riser horizontal runs."]}'),

('structured_cabling','ELV-A-06','A-06',
 'Fire-rated penetrations sealed with a listed firestop system',
 'code', null, 'Building code and NEC', 50, false,
 'The Cables NYC guide does not state any firestop requirement; the source text attributed one to it. Re-sourced to the building and fire codes, which have not been opened. Confirm the assembly rating and listed system with the AHJ.',
 '{"applies_when":[{"fact":"penetration.assembly_fire_rated","op":"eq","value":true}]}',
 '{"required":[{"key":"penetration.assembly_rating_hours","type":"number"},{"key":"penetration.firestop_system_id","type":"string"}]}',
 '{"kind":"checklist","evaluator":"unassigned","requires":"listed_firestop_system_matching_assembly_rating","note":"intumescent_sleeve_is_one_product_route_not_the_rule"}',
 '{"emits":"validation","severity":"error","code":"ELV-A-06-FIRESTOP"}',
 '{"notes":["Every sealed penetration must also appear in the firestop log, rule X-04."]}'),

('structured_cabling','ELV-A-07','A-07',
 'Separation from power and Class 1 conductors',
 'code', null, 'NEC Article 800', 50, false,
 'NEC 800.52 in older editions. Separation distances come from TIA-569 and BICSI and vary with circuit size and shielding; the guide names no figure and warns against taking one from a blog. Take the distance from the project spec.',
 '{"applies_when":[]}',
 '{"required":[{"key":"pathway.shared_with_power","type":"boolean"},{"key":"pathway.barrier_present","type":"boolean"},{"key":"pathway.crossing_angle_deg","type":"number"}]}',
 '{"kind":"checklist","evaluator":"unassigned","shared_raceway":"forbidden_without_permanent_barrier","applies_to":["raceway","compartment","box"],"crossing_angle_deg":90,"parallel_separation_distance":"from_project_spec"}',
 '{"emits":"validation","severity":"error","code":"ELV-A-07-SEPARATION"}',
 '{"notes":["Separation distance is deliberately not a number here. It is a project-spec value, not a rule constant."]}'),

('structured_cabling','ELV-A-08','A-08',
 'Conduit use and fill limit',
 'spec', null, 'Project specification', 100, false,
 'Tailwind Voice and Data was opened and confirms conduit is a choice unless local code or spec requires it. The 40 percent fill figure comes from general knowledge and is unconfirmed; the guide lists it among the numbers that may be wrong.',
 '{"applies_when":[{"fact":"pathway.type","op":"eq","value":"conduit"}]}',
 '{"required":[{"key":"pathway.cable_count","type":"number"},{"key":"pathway.fill_percent","type":"number"}]}',
 '{"kind":"limit","evaluator":"unassigned","conduit_required_when":["spec","ahj","protection_need"],"alternatives":["tray","j_hook","other_listed_support"],"max_fill_percent":40,"fill_applies_from_cable_count":3}',
 '{"emits":"validation","severity":"warning","code":"ELV-A-08-CONDUIT"}',
 '{"notes":["Conduit that is neither on the drawings nor in the SOW is not scope. See X-06."]}'),

('structured_cabling','ELV-A-09','A-09',
 'Bonding and grounding to the telecommunications bonding backbone',
 'code', null, 'ANSI/TIA-607 series, NEC Article 800', 50, false,
 'The TIA-607 reference is from general knowledge. The 2001 TIA-568-B PDF in the supplied source list predates current grounding practice and was not opened.',
 '{"applies_when":[]}',
 '{"required":[{"key":"room.bonded_to_backbone","type":"boolean"}]}',
 '{"kind":"checklist","evaluator":"unassigned","bond_to":"telecommunications_bonding_backbone","scope":["telecom_rooms","racks","shielded_cabling"]}',
 '{"emits":"validation","severity":"error","code":"ELV-A-09-BONDING"}',
 '{"notes":[]}'),

('structured_cabling','ELV-A-10','A-10',
 'Label both ends and maintain an administration schedule',
 'spec', null, 'ANSI/TIA-606', 100, true,
 'Both Voltiq and Tailwind were opened and stress labelling. The TIA-606 reference itself is from general knowledge.',
 '{"applies_when":[]}',
 '{"required":[{"key":"link.label_a","type":"string"},{"key":"link.label_b","type":"string"}]}',
 '{"kind":"checklist","evaluator":"unassigned","label":"both_ends","record_in":"administration_schedule","must_match":"as_built_drawings"}',
 '{"emits":"validation","severity":"warning","code":"ELV-A-10-LABEL"}',
 '{"notes":[]}'),

('structured_cabling','ELV-A-11','A-11',
 'Certify 100 percent of copper permanent links',
 'code', null, 'ANSI/TIA-568.2-D', 50, false,
 'Cables NYC was opened and lists five measurements: wiremap, insertion loss, NEXT, return loss and optical loss. The fuller field-test set below is the standard as recalled, not as read. Use the certifier current limit set for the installed category.',
 '{"applies_when":[{"fact":"link.media","op":"eq","value":"copper_horizontal"}]}',
 '{"required":[{"key":"link.certification_result_file","type":"string"},{"key":"link.certifier_limit_set","type":"string"}]}',
 '{"kind":"checklist","evaluator":"unassigned","coverage_percent":100,"case_study_parameters":["wiremap","insertion_loss","next","return_loss"],"full_tia_field_test_set":["wiremap","insertion_loss","next","return_loss","length","propagation_delay","delay_skew","dc_resistance","psnext","acr_f","psacr_f"],"retain":"native_result_files_unedited"}',
 '{"emits":"validation","severity":"error","code":"ELV-A-11-CERT"}',
 '{"notes":["Native tester files, not only the PDF summary. Both go in the handover pack."]}'),

('structured_cabling','ELV-A-12','A-12',
 'Test 100 percent of fibre links',
 'code', null, 'ANSI/TIA-568.3-D', 50, false,
 'Cables NYC lists optical loss as its fifth measurement. Polarity and end-face inspection come from the standard as recalled; TIA-568.3-D has not been opened.',
 '{"applies_when":[{"fact":"link.media","op":"eq","value":"fibre"}]}',
 '{"required":[{"key":"link.insertion_loss_db","type":"number"},{"key":"link.polarity_verified","type":"boolean"},{"key":"link.end_face_inspected","type":"boolean"}]}',
 '{"kind":"checklist","evaluator":"unassigned","coverage_percent":100,"parameters":["insertion_loss","polarity"],"before_mating":"end_face_inspection"}',
 '{"emits":"validation","severity":"error","code":"ELV-A-12-FIBRE"}',
 '{"notes":[]}'),

-- === Part B: Fire detection and life safety (NFPA 72, BS 5839) ==============

('fire_alarm','ELV-B-01','B-01',
 'Smoke detector spacing on a smooth flat ceiling',
 'code', null, 'NFPA 72', 50, false,
 'From the EngineersUniverse spacing guide, not from NFPA 72 itself. The Scope Fire case studies state no spacing figure. Always use the spacing on the detector listing where it is smaller than this.',
 '{"applies_when":[{"fact":"detector.type","op":"eq","value":"smoke"},{"fact":"ceiling.profile","op":"eq","value":"smooth_flat"}]}',
 '{"required":[{"key":"layout.detector_spacing_m","type":"number"},{"key":"layout.wall_distance_m","type":"number"},{"key":"detector.listed_spacing_m","type":"number"}]}',
 '{"kind":"spacing","evaluator":"unassigned","max_spacing_m":9.1,"max_spacing_ft":30,"max_wall_distance_m":4.6,"max_wall_distance_ft":15,"wall_distance_basis":"half_of_listed_spacing","override":"detector_listed_spacing_if_smaller"}',
 '{"emits":"validation","severity":"error","code":"ELV-B-01-SPACING"}',
 '{"notes":["Beams, joists, partitions and airflow change this layout. See B-04."]}'),

('fire_alarm','ELV-B-02','B-02',
 'Heat detector listed spacing and height derating',
 'code', null, 'NFPA 72', 50, false,
 'From the EngineersUniverse spacing guide. The 0.7 multiplier at a 20 ft ceiling is approximate and has not been checked against NFPA 72.',
 '{"applies_when":[{"fact":"detector.type","op":"eq","value":"heat"}]}',
 '{"required":[{"key":"layout.detector_spacing_m","type":"number"},{"key":"ceiling.height_ft","type":"number"},{"key":"detector.listed_spacing_m","type":"number"}]}',
 '{"kind":"spacing","evaluator":"unassigned","listed_spacing_m":15,"listed_spacing_ft":50,"valid_to_ceiling_height_ft":10,"derate":"reduce_as_ceiling_height_rises","derate_at_20ft_multiplier":0.7,"derate_applies_to":"fixed_temperature"}',
 '{"emits":"validation","severity":"error","code":"ELV-B-02-SPACING"}',
 '{"notes":["Use the listed spacing on the device, not the generic figure, wherever the listing is smaller."]}'),

('fire_alarm','ELV-B-03','B-03',
 'Minimum detector clearance from an air supply diffuser',
 'code', null, 'NFPA 72', 50, false,
 'Matches the case-study figure and the EngineersUniverse guide. Not confirmed against NFPA 72 itself.',
 '{"applies_when":[]}',
 '{"required":[{"key":"layout.distance_to_supply_diffuser_m","type":"number"}]}',
 '{"kind":"clearance","evaluator":"unassigned","min_distance_m":0.9,"min_distance_ft":3,"from":"air_supply_diffuser"}',
 '{"emits":"validation","severity":"error","code":"ELV-B-03-DIFFUSER"}',
 '{"notes":["Smoke dilution at the diffuser delays detection, which is why this is a hard clearance and not a preference."]}'),

('fire_alarm','ELV-B-04','B-04',
 'Recompute spacing for ceiling geometry and airflow',
 'code', null, 'NFPA 72 Chapter 17', 50, false,
 'The chapter reference is from general knowledge. The requirement itself is standard practice; the trigger list is the guide.',
 '{"applies_when":[]}',
 '{"required":[{"key":"drawings.reflected_ceiling_plan_id","type":"string"},{"key":"drawings.hvac_id","type":"string"}]}',
 '{"kind":"checklist","evaluator":"unassigned","recompute_on":["ceiling_height","beam","joist","partition","airflow","diffuser"],"drawings":["reflected_ceiling_plan","hvac"],"before":"fixing_detector_positions"}',
 '{"emits":"validation","severity":"critical_review","code":"ELV-B-04-GEOMETRY"}',
 '{"notes":["This rule is why B-01 and B-02 cannot be applied from a floor plan alone."]}'),

('fire_alarm','ELV-B-05','B-05',
 'Aspirating smoke detection selection and pipe network sizing',
 'spec', null, 'NFPA 72, EN 54-20', 100, false,
 'Listed ASD equipment is recognised by NFPA 72 and EN 54-20; neither has been opened. The Scope Fire aspirating project confirms the project type but states no sizing figure.',
 '{"applies_when":[{"fact":"space.condition","op":"in","value":["high_airflow","tall_ceiling","hidden_space","very_early_warning_required"]}]}',
 '{"required":[{"key":"asd.pipe_calculation_file","type":"string"},{"key":"asd.max_transport_time_s","type":"number"}]}',
 '{"kind":"selection","evaluator":"unassigned","use_when":["high_airflow","tall_ceiling","hidden_space","very_early_warning"],"driver":"design_brief","sizing":"manufacturer_calculation_software","constraint":"within_maximum_smoke_transport_time","boq_term":"aspirating_smoke_detection"}',
 '{"emits":"validation","severity":"warning","code":"ELV-B-05-ASD"}',
 '{"notes":["VESDA is one manufacturer brand. Write aspirating smoke detection in the BOQ unless the SOW names a brand."]}'),

('fire_alarm','ELV-B-06','B-06',
 'Fix the BS 5839-1 system category before counting detectors',
 'code', null, 'BS 5839-1', 50, true,
 'The Scope Fire pages were opened and confirm Silentnight and Real Food Hall as BS 5839-1 projects. The category definitions are standard; the current edition of BS 5839-1 has not been read.',
 '{"applies_when":[{"fact":"project.standard","op":"eq","value":"BS 5839-1"}]}',
 '{"required":[{"key":"design_brief.system_category","type":"string"}]}',
 '{"kind":"selection","evaluator":"unassigned","categories":["L1","L2","L3","L4","L5","P1","P2","M"],"L1":"all_areas","L2":"defined_risk_areas","must_precede":"detector_count"}',
 '{"emits":"validation","severity":"error","code":"ELV-B-06-CATEGORY"}',
 '{"notes":["A detector quantity produced before the category is fixed has no basis. This rule gates the Part B count."]}'),

('fire_alarm','ELV-B-07','B-07',
 'BS 5839-1 detector coverage radius',
 'code', null, 'BS 5839-1', 50, false,
 'The guide flags this rule itself: approximate, from memory of the standard. The 7.5 m and 5.3 m radii must be confirmed in the current edition before use. Do not quote to a client as-is.',
 '{"applies_when":[{"fact":"project.standard","op":"eq","value":"BS 5839-1"},{"fact":"ceiling.profile","op":"eq","value":"normal"}]}',
 '{"required":[{"key":"detector.type","type":"string"},{"key":"layout.coverage_radius_m","type":"number"}]}',
 '{"kind":"coverage","evaluator":"unassigned","smoke_radius_m":7.5,"heat_radius_m":5.3,"ceiling":"normal","status":"unconfirmed"}',
 '{"emits":"validation","severity":"critical_review","code":"ELV-B-07-COVERAGE"}',
 '{"notes":["Flagged unconfirmed by the source author. Approving this version without reading BS 5839-1 would put an unchecked number into a detector count."]}'),

('fire_alarm','ELV-B-08','B-08',
 'Automatic air handling unit shutdown on fire alarm',
 'code', null, 'NFPA 90A, NFPA 72', 10, false,
 'The NFPA 90A reference is from general knowledge. The arrangement itself is set by the mechanical design, not by this rule.',
 '{"applies_when":[{"fact":"project.has_ahu","op":"eq","value":true}]}',
 '{"required":[{"key":"cause_effect.ahu_lines","type":"array"}]}',
 '{"kind":"interface","evaluator":"unassigned","target":"air_handling_unit","action":"shutdown_or_control_on_alarm","arrangement":"per_mechanical_design","appears_as":["facp_output","relay_or_module_in_point_list"]}',
 '{"emits":"validation","severity":"error","code":"ELV-B-08-AHU"}',
 '{"notes":["Every line must appear in the single cause-and-effect matrix, rule X-03."]}'),

('fire_alarm','ELV-B-09','B-09',
 'Electromagnetic locks release on alarm and on power loss',
 'code', null, 'NFPA 101 and local building code', 10, false,
 'The NFPA 101 reference is from general knowledge. The case study calls this a mandatory fail-safe linkage. In Saudi Arabia confirm the Civil Defense requirement for door release.',
 '{"applies_when":[{"fact":"door.has_electromagnetic_lock","op":"eq","value":true},{"fact":"door.on_egress_route","op":"eq","value":true}]}',
 '{"required":[{"key":"door.release_on_alarm_tested","type":"boolean"},{"key":"door.release_on_power_loss_tested","type":"boolean"}]}',
 '{"kind":"interface","evaluator":"unassigned","target":"electromagnetic_lock","scope":"egress_doors","release_on":["fire_alarm_signal","loss_of_power"],"failure_mode":"fail_safe"}',
 '{"emits":"validation","severity":"error","code":"ELV-B-09-MAGLOCK"}',
 '{"notes":["Same physical requirement as C-06, approached from the fire alarm side. Both are encoded; a design satisfying one but not the other is a conflict to surface, not to resolve silently."]}'),

('fire_alarm','ELV-B-10','B-10',
 'Emergency voice evacuation where the fire strategy requires it',
 'code', null, 'NFPA 72 Chapter 24', 10, false,
 'The chapter reference is from general knowledge. Not every building needs voice evacuation, so this is tied to the fire strategy rather than applied by default.',
 '{"applies_when":[{"fact":"fire_strategy.requires_voice_evacuation","op":"eq","value":true}]}',
 '{"required":[{"key":"va.speech_intelligibility_result","type":"string"}]}',
 '{"kind":"selection","evaluator":"unassigned","provide_when":"building_class_or_fire_strategy_requires","test":"speech_intelligibility_on_completion"}',
 '{"emits":"validation","severity":"error","code":"ELV-B-10-VOICE"}',
 '{"notes":["Do not price voice evacuation from this rule alone. The fire strategy is what makes it scope."]}'),

('fire_alarm','ELV-B-11','B-11',
 'Test 100 percent of devices at acceptance and arrange monitoring',
 'spec', null, 'NFPA 72 Chapter 14', 100, false,
 'The Scope Fire Silentnight case study was opened and cites 24/7 monitoring. The NFPA 72 Chapter 14 reference is from general knowledge.',
 '{"applies_when":[]}',
 '{"required":[{"key":"acceptance.device_test_record","type":"string"},{"key":"monitoring.receiving_point","type":"string"}]}',
 '{"kind":"checklist","evaluator":"unassigned","device_test_coverage_percent":100,"retain":"test_record","monitoring":"per_fire_strategy"}',
 '{"emits":"validation","severity":"error","code":"ELV-B-11-ACCEPTANCE"}',
 '{"notes":["Monitoring to a receiving point is scope only where the fire strategy or SOW requires it."]}'),

-- === Part C: Security, CCTV and access control ==============================

('cctv','ELV-C-01','C-01',
 'Outdoor and perimeter camera cabling protection',
 'spec', null, 'Project risk assessment', 100, false,
 'Not a code rule. The Scope Fire CCTV case study says nothing about conduit. Metallic conduit is a security-risk decision: if it is not on the drawings or in the SOW, do not price it.',
 '{"applies_when":[{"fact":"camera.location","op":"in","value":["outdoor","perimeter"]}]}',
 '{"required":[{"key":"camera.cable_rating","type":"string"},{"key":"camera.entry_sealed","type":"boolean"},{"key":"camera.conduit_required_by","type":"string"}]}',
 '{"kind":"checklist","evaluator":"unassigned","measures":["outdoor_rated_cable","sealed_entries","high_impact_metallic_conduit"],"conduit_only_when":["risk_assessment","sow"]}',
 '{"emits":"validation","severity":"warning","code":"ELV-C-01-PATHWAY"}',
 '{"notes":["A common over-pricing trap. Conduit here is SPEC, so X-06 blocks it from becoming scope without a citation."]}'),

('cctv','ELV-C-02','C-02',
 'PoE budget sized from the switch down',
 'code', null, 'IEEE 802.3af/at/bt', 50, false,
 'IEEE 802.3 gives the class limits and has not been opened. The 20 percent design margin is SPEC, not CODE, and is recorded separately below so it cannot be quoted as a code requirement.',
 '{"applies_when":[{"fact":"device.powered_by","op":"eq","value":"poe"}]}',
 '{"required":[{"key":"switch.total_budget_w","type":"number"},{"key":"switch.port_device_class","type":"array"}]}',
 '{"kind":"budget","evaluator":"unassigned","method":"sum_port_maximum_power_then_compare_switch_total_budget","classes":["802.3af","802.3at","802.3bt"],"headroom_percent":20,"headroom_confidence":"spec"}',
 '{"emits":"validation","severity":"error","code":"ELV-C-02-POE"}',
 '{"notes":["Thermal PTZ heads and IR illuminators often need at or bt class. Do not assume af.","The 20 percent headroom is a design margin, not a code requirement."]}'),

('cctv','ELV-C-03','C-03',
 'PoE bundle temperature rise and heat dissipation',
 'code', null, 'TIA TSB-184-A', 50, false,
 'The TSB-184-A reference comes from general knowledge and is listed by the guide among the references that may be wrong.',
 '{"applies_when":[{"fact":"pathway.carries_poe","op":"eq","value":true}]}',
 '{"required":[{"key":"bundle.cable_count","type":"number"},{"key":"bundle.ambient_temp_c","type":"number"},{"key":"enclosure.dissipation_w","type":"number"}]}',
 '{"kind":"checklist","evaluator":"unassigned","checks":["bundle_temperature_rise","switch_heat_dissipation","enclosure_heat_dissipation"],"worst_case":["bundled_runs","conduit_runs"],"record_in":"certification_record"}',
 '{"emits":"validation","severity":"warning","code":"ELV-C-03-THERMAL"}',
 '{"notes":["Add to the certification record when high-power devices are used."]}'),

('cctv','ELV-C-04','C-04',
 'Security network segmentation and credential hygiene',
 'spec', null, 'Client IT security policy', 100, false,
 'Network security practice, not a cabling code. The case studies say nothing about VLANs. Follow the client IT security policy where one exists.',
 '{"applies_when":[]}',
 '{"required":[{"key":"network.security_vlan_id","type":"string"},{"key":"network.default_credentials_changed","type":"boolean"}]}',
 '{"kind":"checklist","evaluator":"unassigned","measures":["dedicated_vlan","routing_restricted_to_vms_and_controllers","unused_ports_disabled","unused_services_disabled","default_credentials_changed"],"deadline":"before_handover"}',
 '{"emits":"validation","severity":"warning","code":"ELV-C-04-SEGMENTATION"}',
 '{"notes":["Credential handover record belongs in the handover pack."]}'),

('acs','ELV-C-05','C-05',
 'OSDP with Secure Channel active, not Wiegand',
 'spec', null, 'IEC 60839-11-5:2020 (OSDP v2.2.2)', 100, true,
 'The SIA page was opened and confirms AES-128 encryption, supervised wiring, the IEC publication and the current version. Whether it binds on a given project is still a SOW question.',
 '{"applies_when":[{"fact":"reader.supports_osdp","op":"eq","value":true},{"fact":"controller.supports_osdp","op":"eq","value":true}]}',
 '{"required":[{"key":"reader.protocol","type":"string"},{"key":"reader.secure_channel_active","type":"boolean"}]}',
 '{"kind":"selection","evaluator":"unassigned","protocol":"osdp","secure_channel":"required_active","encryption":"aes_128","wiring":"supervised","not":"wiegand"}',
 '{"emits":"validation","severity":"warning","code":"ELV-C-05-OSDP"}',
 '{"notes":["Confirm Secure Channel is active on each reader at handover, not merely supported."]}'),

('acs','ELV-C-06','C-06',
 'Door failure mode set from the egress and fire strategy',
 'code', null, 'NFPA 101 and local building code', 10, false,
 'Same requirement as B-09, from the access control side. The NFPA 101 reference is from general knowledge. Drawings must state which doors are fail-safe and which are fail-secure.',
 '{"applies_when":[{"fact":"door.has_access_control","op":"eq","value":true}]}',
 '{"required":[{"key":"door.failure_mode","type":"string"},{"key":"door.linked_to_fire_alarm_release","type":"boolean"}]}',
 '{"kind":"selection","evaluator":"unassigned","modes":["fail_safe","fail_secure"],"determined_by":["egress_strategy","fire_strategy"],"linked_to":"fire_alarm_release","see_also":"ELV-B-09"}',
 '{"emits":"validation","severity":"error","code":"ELV-C-06-FAILMODE"}',
 '{"notes":["The door schedule and the cause-and-effect matrix must agree. X-03 is where that is proven."]}'),

('cctv','ELV-C-07','C-07',
 'Camera pixel density per task tier',
 'spec', null, 'IEC 62676-4', 100, false,
 'Added by the guide, not taken from the case studies. The IEC 62676-4 reference is from general knowledge. Ask the client which tier each area needs.',
 '{"applies_when":[]}',
 '{"required":[{"key":"camera.task_tier","type":"string"},{"key":"camera.pixel_density_px_per_m","type":"number"}]}',
 '{"kind":"coverage","evaluator":"unassigned","tiers":["detect","observe","recognise","identify"],"record":"per_camera","tier_source":"client"}',
 '{"emits":"validation","severity":"warning","code":"ELV-C-07-PIXEL"}',
 '{"notes":["Camera count and lens selection follow the tier. Agreeing the tier late is a common cause of redesign."]}'),

-- === Part D: Outdoor infrastructure and mast siting =========================

('outdoor_infrastructure','ELV-D-01','D-01',
 'Obtain mast setback distances in writing before design',
 'local', null, 'Local regulator and municipality', 150, true,
 'The Mubi spatial analysis was opened. It finds operators often ignore the national minimum setback, so the rule exists but is widely broken, and it gives no universal distance. There is deliberately no number in this rule.',
 '{"applies_when":[{"fact":"project.includes_mast","op":"eq","value":true}]}',
 '{"required":[{"key":"site.setback_confirmation_document","type":"string"}]}',
 '{"kind":"checklist","evaluator":"unassigned","obtain":"setback_distance_in_writing","from":["local_regulator","municipality"],"subjects":["homes","schools","high_voltage_lines"],"before":"design","distance":"not_supplied"}',
 '{"emits":"validation","severity":"error","code":"ELV-D-01-SETBACK"}',
 '{"notes":["Encoding a setback number here would be an invention. The deliverable is the written confirmation, not a distance."]}'),

('outdoor_infrastructure','ELV-D-02','D-02',
 'Generator setback from the neighbouring property line',
 'local', 'NG', 'NCC Guidelines on Technical Specifications for Masts and Towers (2009), s.3(5)', 150, true,
 'Nigeria only. Quoted in the Harlem Solicitors case analysis, which was opened. Do not carry the 5 m figure to a Saudi or GCC site: find the local equivalent.',
 '{"applies_when":[{"fact":"site.country","op":"eq","value":"NG"},{"fact":"site.has_generator","op":"eq","value":true}]}',
 '{"required":[{"key":"generator.distance_to_property_line_m","type":"number"}]}',
 '{"kind":"clearance","evaluator":"unassigned","min_distance_m":5,"from":"neighbouring_property_line","excludes":"fences","jurisdiction":"NG"}',
 '{"emits":"validation","severity":"error","code":"ELV-D-02-GENSET"}',
 '{"notes":["Measured to the property line, not to the fence."]}'),

('outdoor_infrastructure','ELV-D-03','D-03',
 'Generator sound-proofing and anti-vibration mounting',
 'local', 'NG', 'NCC Guidelines on Technical Specifications for Masts and Towers (2009)', 150, true,
 'Same 2009 NCC guideline, via the Harlem Solicitors article. Directing exhaust away from neighbours is good practice but is not stated in the sources, so it is not encoded.',
 '{"applies_when":[{"fact":"site.country","op":"eq","value":"NG"},{"fact":"site.has_generator","op":"eq","value":true}]}',
 '{"required":[{"key":"generator.acoustic_enclosure","type":"boolean"},{"key":"generator.anti_vibration_mounts","type":"boolean"}]}',
 '{"kind":"checklist","evaluator":"unassigned","measures":["sound_proofing","shock_absorber_mounts"],"objective":"minimise_vibration","jurisdiction":"NG"}',
 '{"emits":"validation","severity":"error","code":"ELV-D-03-GENSET-NOISE"}',
 '{"notes":[]}'),

('outdoor_infrastructure','ELV-D-04','D-04',
 'Keep noise within the residential limit',
 'local', 'NG', 'Nigerian environmental regulator, via Helios case', 150, true,
 'The Harlem Solicitors article was opened and reports the court noting Nigerian residential limits of 50 dB by day and 35 dB by night. Those figures are Nigerian. Find the regulator and limit for the country you build in.',
 '{"applies_when":[{"fact":"site.adjacent_use","op":"eq","value":"residential"}]}',
 '{"required":[{"key":"site.boundary_noise_day_db","type":"number"},{"key":"site.boundary_noise_night_db","type":"number"}]}',
 '{"kind":"limit","evaluator":"unassigned","residential_day_db":50,"residential_night_db":35,"jurisdiction":"NG","limit_source":"environmental_regulator","portable":false}',
 '{"emits":"validation","severity":"error","code":"ELV-D-04-NOISE"}',
 '{"notes":["The dB figures are jurisdiction-bound. Replace them, do not reuse them."]}'),

('outdoor_infrastructure','ELV-D-05','D-05',
 'Demonstrate RF exposure within the national limit',
 'local', null, 'National regulator, ICNIRP-derived', 150, false,
 'Most regulators base limits on ICNIRP, but each issues its own. In Saudi Arabia, CST cites its own Regulation on Exposure to EMF. That regulation has not been opened; obtain the document itself, not a summary.',
 '{"applies_when":[{"fact":"project.includes_rf_transmitter","op":"eq","value":true}]}',
 '{"required":[{"key":"site.rf_exposure_assessment","type":"string"}]}',
 '{"kind":"checklist","evaluator":"unassigned","demonstrate":"rf_exposure_within_national_limit","at":"accessible_locations","then":["mark","fence"],"limit_source":"national_regulator","limit_value":"not_supplied"}',
 '{"emits":"validation","severity":"error","code":"ELV-D-05-RF"}',
 '{"notes":["Part D is probably outside a typical Saudi ICT and ELV bid. Confirm scope before pricing any of it."]}'),

('outdoor_infrastructure','ELV-D-06','D-06',
 'Keep an as-built distance survey and noise record',
 'spec', null, 'SmartPage practice, from the Helios case', 100, true,
 'The practical lesson of the case, which was opened: the Court of Appeal ruled for the tower company because the neighbour could not prove the distance or that noise exceeded the limit.',
 '{"applies_when":[{"fact":"project.includes_mast_or_generator","op":"eq","value":true}]}',
 '{"required":[{"key":"site.distance_survey","type":"string"},{"key":"site.noise_measurement_record","type":"string"}]}',
 '{"kind":"checklist","evaluator":"unassigned","records":["as_built_distance_survey","noise_measurement"],"per":["generator","mast"]}',
 '{"emits":"validation","severity":"warning","code":"ELV-D-06-RECORDS"}',
 '{"notes":["Your own records are the defence. This is the rule the case actually establishes."]}'),

-- === Part X: Cross-discipline (system_id null) ==============================

(null,'ELV-X-01','X-01',
 'Confirm adopted code editions with the AHJ and SOW before design',
 'code', null, 'Authority having jurisdiction', 10, true,
 'Tailwind was opened and tells installers to confirm requirements with the AHJ before starting work. This is the rule that decides which edition every other CODE rule is quoting.',
 '{"applies_when":[]}',
 '{"required":[{"key":"design_basis.adopted_editions","type":"array"},{"key":"design_basis.client_standards","type":"array"}]}',
 '{"kind":"checklist","evaluator":"unassigned","confirm":["adopted_code_editions","client_standards"],"with":["ahj","sow"],"record_on":"design_basis_page_1"}',
 '{"emits":"validation","severity":"error","code":"ELV-X-01-EDITIONS"}',
 '{"notes":["In Saudi Arabia check the current SBC 801 text, Civil Defense approval requirements, and whether the project uses TIA-568 or ISO/IEC 11801 for cabling."]}'),

(null,'ELV-X-02','X-02',
 'Coordinate pathways with other trades before first fix',
 'spec', null, 'SmartPage practice', 100, true,
 'Practice described in the Voltiq office cabling case study, which was opened. No standard is cited by that source.',
 '{"applies_when":[]}',
 '{"required":[{"key":"coordination.first_fix_signoff","type":"string"}]}',
 '{"kind":"checklist","evaluator":"unassigned","coordinate_with":["electrical","hvac","plumbing","fire"],"before":"first_fix","route_through":"open_wall_or_ceiling","avoid":"surface_trunking_afterwards"}',
 '{"emits":"validation","severity":"warning","code":"ELV-X-02-COORDINATION"}',
 '{"notes":[]}'),

(null,'ELV-X-03','X-03',
 'One cause-and-effect matrix, every line tested',
 'code', null, 'NFPA 72 control functions', 10, false,
 'Ties together B-08, B-09, B-10 and C-06. The underlying NFPA chapter references are from general knowledge.',
 '{"applies_when":[{"fact":"project.has_fire_alarm","op":"eq","value":true}]}',
 '{"required":[{"key":"cause_effect.matrix_id","type":"string"},{"key":"cause_effect.lines_tested","type":"array"}]}',
 '{"kind":"interface","evaluator":"unassigned","artefact":"cause_and_effect_matrix","cardinality":"exactly_one_per_project","covers":["ahu","door_locks","lifts","voice_alarm","cctv_call_up"],"test":"every_line_at_acceptance","implements":["ELV-B-08","ELV-B-09","ELV-B-10","ELV-C-06"]}',
 '{"emits":"validation","severity":"error","code":"ELV-X-03-CAUSE-EFFECT"}',
 '{"notes":["A line that is not tested is an output nobody has proven."]}'),

(null,'ELV-X-04','X-04',
 'Maintain a firestop log',
 'code', null, 'Building and fire code', 50, false,
 'Supports A-06, and A-06 is itself re-sourced to codes that have not been opened. Needed to close out the fire authority inspection.',
 '{"applies_when":[{"fact":"project.has_fire_rated_penetrations","op":"eq","value":true}]}',
 '{"required":[{"key":"firestop_log.entries","type":"array"}]}',
 '{"kind":"checklist","evaluator":"unassigned","artefact":"firestop_log","fields":["location","assembly_rating","product","installer"],"per":"sealed_penetration","supports":"ELV-A-06"}',
 '{"emits":"validation","severity":"error","code":"ELV-X-04-FIRESTOP-LOG"}',
 '{"notes":["Photographs accompany the log in the handover pack."]}'),

(null,'ELV-X-05','X-05',
 'Named owner and single schedule per shared network element',
 'spec', null, 'SmartPage practice', 100, false,
 'Added by the guide to stop two trades sizing the same switch. No external source.',
 '{"applies_when":[{"fact":"project.has_shared_network","op":"eq","value":true}]}',
 '{"required":[{"key":"network.element_owners","type":"array"}]}',
 '{"kind":"checklist","evaluator":"unassigned","elements":["switch","poe_budget","vlan","ip_range"],"requires":["named_owner","single_schedule"],"supports":["ELV-C-02","ELV-C-03","ELV-C-04"]}',
 '{"emits":"validation","severity":"warning","code":"ELV-X-05-OWNERSHIP"}',
 '{"notes":[]}'),

(null,'ELV-X-06','X-06',
 'Every rule in a BOQ carries its tag and cites its scope basis',
 'spec', null, 'SmartPage BOQ traceability requirement', 5, true,
 'Authored by SmartPage. This is the only rule in the set already enforced in code: see forbid_unsupported_scope() in migration 0014.',
 '{"applies_when":[]}',
 '{"required":[{"key":"boq_item.rule_execution_id","type":"string"},{"key":"boq_item.scope_citation","type":"string"}]}',
 '{"kind":"governance","evaluator":"enforced_in_sql","requires":["confidence_tag","drawing_or_sow_citation"],"binding_alone":["code"],"not_binding_alone":["spec","local"],"enforced_by":"forbid_unsupported_scope","enforced_at":"boq_transition_to_validated_approved_issued","accepted_citation_types":["sow_clause","drawing","client_standard"]}',
 '{"emits":"validation","severity":"error","code":"ELV-X-06-SCOPE-BASIS"}',
 '{"notes":["This rule is why the other 41 can be stored without becoming quantities by accident."]}')

) as t(system_code, rule_code, source_rule_id, rule_name, confidence, jurisdiction,
       standard_reference, priority, source_verified, verification_note,
       conditions, inputs, calculation, outputs, exceptions);
$fn$;

comment on function elv_rule_seed() is
  'The 42 rules of the ELV and Telecom Installation Rule Guide Book (SmartPage, '
  '21 Sep 2026) as data. Source of record: '
  'knowledge/standards-references/elv-telecom-installation-rule-guide/.';

-- ---------------------------------------------------------------------------
-- Loading the set into one organization
-- ---------------------------------------------------------------------------

create or replace function seed_elv_installation_rules(p_organization_id uuid)
returns integer
language plpgsql
set search_path = ''
as $fn$
declare
  v_source constant text :=
    'standards-references/elv-telecom-installation-rule-guide/';
  v_loaded integer;
begin
  if not exists (select 1 from public.organizations o where o.id = p_organization_id) then
    raise exception 'organization % does not exist', p_organization_id
      using errcode = 'foreign_key_violation';
  end if;

  -- A null system_code means cross-discipline and must stay null. A non-null
  -- one that fails to join means a missing row in `systems`, which is a bug
  -- rather than a cross-discipline rule, so fail before inserting rather than
  -- silently widening that rule to every system.
  if exists (
    select 1 from public.elv_rule_seed() r
    left join public.systems s on s.code = r.system_code
    where r.system_code is not null and s.id is null)
  then
    raise exception 'elv_rule_seed references a system code with no row in systems';
  end if;

  insert into public.engineering_rules (
    organization_id, system_id, rule_code, name, jurisdiction, standard_reference,
    priority, confidence, source_document, source_rule_id, source_verified,
    verification_note)
  select
    p_organization_id, s.id, r.rule_code, r.rule_name, r.jurisdiction,
    r.standard_reference, r.priority, r.confidence, v_source, r.source_rule_id,
    r.source_verified, r.verification_note
  from public.elv_rule_seed() r
  left join public.systems s on s.code = r.system_code
  -- Untargeted, so a re-run is a no-op whether it collides on rule_code or on
  -- the partial (organization_id, source_document, source_rule_id) index.
  on conflict do nothing;

  -- Version 1, draft, for any rule that has no version yet. Deliberately not
  -- approved: approval is an Engineering Manager act, and several of these
  -- rules carry verification notes that must be closed out first.
  insert into public.rule_versions (
    rule_id, version, conditions, inputs, calculation, outputs, exceptions,
    approval_status)
  select er.id, 1, r.conditions, r.inputs, r.calculation, r.outputs,
         r.exceptions, 'draft'
  from public.elv_rule_seed() r
  join public.engineering_rules er
    on er.organization_id = p_organization_id
   and er.rule_code = r.rule_code
  where not exists (
    select 1 from public.rule_versions rv where rv.rule_id = er.id);

  get diagnostics v_loaded = row_count;
  return v_loaded;
end $fn$;

comment on function seed_elv_installation_rules(uuid) is
  'Loads the ELV and Telecom Installation Rule Guide Book into one organization '
  'as draft rule versions. Idempotent. Run it for any organization created after '
  'this migration.';

-- ---------------------------------------------------------------------------
-- Test cases (spec 11.1)
-- ---------------------------------------------------------------------------
--
-- Seeded only for the rules that carry a checkable number, and left at
-- 'not_run' because no evaluator exists yet. They are written now, against the
-- rules as encoded, so that whoever designs the expression language has a
-- target to satisfy rather than inventing one afterwards.
--
-- B-07 deliberately has no test. Writing an expectation around 7.5 m would
-- dress an unconfirmed figure as a verified one.

create or replace function seed_elv_installation_rule_tests(p_organization_id uuid)
returns integer
language plpgsql
set search_path = ''
as $fn$
declare
  v_loaded integer;
begin
  insert into public.rule_tests (rule_version_id, name, given_inputs, expected_outputs)
  select rv.id, t.test_name, t.given::jsonb, t.expected::jsonb
  from (values
    ('ELV-A-01','89 m pulled link passes',
     '{"link.pulled_length_m":89,"link.patch_cord_total_m":6}',
     '{"pass":true}'),
    ('ELV-A-01','91 m pulled link fails the permanent link limit',
     '{"link.pulled_length_m":91,"link.patch_cord_total_m":6}',
     '{"pass":false,"code":"ELV-A-01-LENGTH"}'),
    ('ELV-A-01','90 m link with 11 m of cords exceeds the channel limit',
     '{"link.pulled_length_m":90,"link.patch_cord_total_m":11}',
     '{"pass":false,"code":"ELV-A-01-LENGTH"}'),
    ('ELV-A-02','28 mm radius on a 7 mm UTP cable meets 4x',
     '{"cable.outside_diameter_mm":7,"route.min_bend_radius_mm":28}',
     '{"pass":true}'),
    ('ELV-A-02','20 mm radius on a 7 mm UTP cable is below 4x',
     '{"cable.outside_diameter_mm":7,"route.min_bend_radius_mm":20}',
     '{"pass":false,"code":"ELV-A-02-BEND"}'),
    ('ELV-A-02','stricter datasheet radius governs over 4x',
     '{"cable.outside_diameter_mm":7,"route.min_bend_radius_mm":28,"cable.datasheet_min_bend_radius_mm":35}',
     '{"pass":false,"code":"ELV-A-02-BEND"}'),
    ('ELV-A-03','13 mm untwist is at the limit and passes',
     '{"termination.untwist_mm":13}',
     '{"pass":true}'),
    ('ELV-A-03','14 mm untwist fails',
     '{"termination.untwist_mm":14}',
     '{"pass":false,"code":"ELV-A-03-UNTWIST"}'),
    ('ELV-A-05','CM cable in a plenum fails',
     '{"space.type":"plenum","cable.listing":"CM"}',
     '{"pass":false,"code":"ELV-A-05-LISTING"}'),
    ('ELV-A-05','CMP cable in a riser passes as a higher rating',
     '{"space.type":"riser","cable.listing":"CMP"}',
     '{"pass":true}'),
    ('ELV-B-01','9.0 m smoke detector spacing passes',
     '{"detector.type":"smoke","ceiling.profile":"smooth_flat","layout.detector_spacing_m":9.0,"layout.wall_distance_m":4.5}',
     '{"pass":true}'),
    ('ELV-B-01','9.5 m smoke detector spacing fails',
     '{"detector.type":"smoke","ceiling.profile":"smooth_flat","layout.detector_spacing_m":9.5,"layout.wall_distance_m":4.5}',
     '{"pass":false,"code":"ELV-B-01-SPACING"}'),
    ('ELV-B-01','a smaller listed spacing overrides the generic 9.1 m',
     '{"detector.type":"smoke","ceiling.profile":"smooth_flat","layout.detector_spacing_m":9.0,"layout.wall_distance_m":4.5,"detector.listed_spacing_m":7.5}',
     '{"pass":false,"code":"ELV-B-01-SPACING"}'),
    ('ELV-B-03','1.2 m from a diffuser passes',
     '{"layout.distance_to_supply_diffuser_m":1.2}',
     '{"pass":true}'),
    ('ELV-B-03','0.6 m from a diffuser fails',
     '{"layout.distance_to_supply_diffuser_m":0.6}',
     '{"pass":false,"code":"ELV-B-03-DIFFUSER"}'),
    ('ELV-C-02','load inside budget with 20 percent headroom passes',
     '{"switch.total_budget_w":370,"switch.port_device_class":["at","at","at","af"]}',
     '{"pass":true}'),
    ('ELV-C-02','load above budget fails regardless of headroom',
     '{"switch.total_budget_w":120,"switch.port_device_class":["bt","bt"]}',
     '{"pass":false,"code":"ELV-C-02-POE"}'),
    ('ELV-D-02','6 m generator setback passes in Nigeria',
     '{"site.country":"NG","site.has_generator":true,"generator.distance_to_property_line_m":6}',
     '{"pass":true}'),
    ('ELV-D-02','4 m generator setback fails in Nigeria',
     '{"site.country":"NG","site.has_generator":true,"generator.distance_to_property_line_m":4}',
     '{"pass":false,"code":"ELV-D-02-GENSET"}'),
    ('ELV-D-02','the 5 m figure does not apply outside Nigeria',
     '{"site.country":"SA","site.has_generator":true,"generator.distance_to_property_line_m":4}',
     '{"pass":true,"reason":"rule_not_applicable"}')
  ) as t(rule_code, test_name, given, expected)
  join public.engineering_rules er
    on er.organization_id = p_organization_id and er.rule_code = t.rule_code
  join public.rule_versions rv
    on rv.rule_id = er.id and rv.version = 1
  where not exists (
    select 1 from public.rule_tests rt
    where rt.rule_version_id = rv.id and rt.name = t.test_name);

  get diagnostics v_loaded = row_count;
  return v_loaded;
end $fn$;

comment on function seed_elv_installation_rule_tests(uuid) is
  'Spec 11.1 test cases for the numeric ELV guide rules. Left at not_run: there '
  'is no evaluator yet (ARCHITECTURE.md 9.4). B-07 has no test on purpose, '
  'because its figure is unconfirmed.';

-- ---------------------------------------------------------------------------
-- Apply to organizations that already exist
-- ---------------------------------------------------------------------------
-- A no-op on a fresh database. Organizations created later are loaded by
-- calling seed_elv_installation_rules(<org id>) deliberately.

do $$
declare
  o record;
begin
  for o in select id, name from organizations loop
    perform seed_elv_installation_rules(o.id);
    perform seed_elv_installation_rule_tests(o.id);
    raise notice 'ELV installation rules loaded for organization % (%)', o.name, o.id;
  end loop;
end $$;
