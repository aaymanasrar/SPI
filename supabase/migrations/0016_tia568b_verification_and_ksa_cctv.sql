-- 0016_tia568b_verification_and_ksa_cctv
--
-- Two source documents arrived on 24 Sep 2026, after the ELV guide was encoded
-- in 0015. This migration folds both in.
--
-- 1. ANSI/TIA/EIA-568-B (condensed copy, QD-Tek from Cablingdb.com, 62 pp).
--    Re-verifies eight Part A rules, CORRECTS two that were wrong, confirms by
--    absence that two SPEC tags were right, and adds nine rules.
--
--    What it does NOT do is make anything verified. It is a condensed secondary
--    summary of a SUPERSEDED edition -- its own disclaimer says it is not meant
--    to replace the original, and the current standards are ANSI/TIA-568.2-D and
--    568.3-D. So every rule it touches keeps source_verified = false, with a
--    note that now says "confirmed against a condensed summary of 568-B" rather
--    than "from general knowledge". That is a real change in provenance and it
--    is deliberately not the same as verified.
--
-- 2. Law of the Use of Security Surveillance Cameras (Saudi Arabia), Royal
--    Decree of 3 Oct 2022, with Ministerial Decision 22688/1444. Six new LOCAL
--    rules for the jurisdiction SmartPage actually builds in -- the gap the ELV
--    guide left open, since its Part C rests on UK case studies.
--
-- Both sets are seeded as draft, like everything from 0015. Nothing here can
-- execute.
--
-- Idempotent.

-- ---------------------------------------------------------------------------
-- 1. Part A: re-verification and correction against TIA/EIA-568-B
-- ---------------------------------------------------------------------------
--
-- Rule content is edited in place rather than versioned. That is correct and
-- not a shortcut: 0010 freezes a rule version only at approved/active/
-- superseded, and every one of these is still draft. There is no approved
-- version whose history needs preserving -- draft IS the editing state
-- (spec 11.2). The first rule to reach 'approved' ends that freedom.

create or replace function apply_tia568b_verification(p_organization_id uuid)
returns integer
language plpgsql
set search_path = ''
as $fn$
declare
  v_src constant text := 'standards-references/tia-eia-568-b/';
  v_caveat constant text :=
    'Source is a condensed secondary summary of the SUPERSEDED 568-B edition, '
    'not the standard itself. Confirm against a licensed ANSI/TIA-568.2-D or '
    '568.3-D before quoting to a client.';
  v_updated integer := 0;
  v_n integer;
begin
  -- Provenance updates. source_verified stays false throughout, on purpose.
  --
  -- The caveat is concatenated HERE rather than in a second, guarded UPDATE.
  -- Doing it separately looked tidier and was wrong: this statement overwrites
  -- verification_note, so on a re-run it would wipe a caveat that the guarded
  -- statement then declined to restore, silently dropping the one sentence that
  -- tells a reader not to quote these figures at a client. Writing the whole
  -- note in one statement makes the result identical on every run.
  update public.engineering_rules er
     set verification_note = v.note || v_caveat,
         standard_reference = coalesce(v.std, er.standard_reference)
  from (values
    ('ELV-A-01',
     'CONFIRMED in 568-B p.9-10: permanent link 90 m, channel 100 m, and patch '
     'plus equipment cords 10 m combined. The 10 m allowance was previously '
     'flagged as general knowledge and is now sourced. ' , 'ANSI/TIA/EIA-568-B.1'),
    ('ELV-A-02',
     'CONFIRMED and CORRECTED by 568-B p.8, 9, 28, 31. UTP 4x confirmed; ScTP 8x '
     'and copper backbone 10x added. The previous fibre figure was wrong: 20x is '
     'INTERBUILDING backbone only, intrabuilding backbone under load is 15x, and '
     'horizontal 2/4-fibre is an absolute 25 mm no load / 50 mm under load. ', 'ANSI/TIA/EIA-568-B.1'),
    ('ELV-A-03',
     'CONFIRMED in 568-B p.9, with a scope limit the guide did not carry: the '
     'half-inch (12.7 mm) untwist limit applies to Category 5e and higher. '
     'Category 3 requires twists maintained within 3 in (76 mm). ', 'ANSI/TIA/EIA-568-B.1'),
    ('ELV-A-04',
     'SPEC TAG CONFIRMED BY ABSENCE. 568-B states no support interval anywhere; '
     'its only placement requirement is qualitative (p.8). The 4 to 5 ft figure '
     'is contractor and BICSI practice, so it cannot become scope on its own. ', null),
    ('ELV-A-08',
     'STILL UNCONFIRMED. The 40 percent conduit fill figure does not appear in '
     '568-B either. Take the fill limit from the project specification. ', null),
    ('ELV-A-09',
     'CONFIRMED in 568-B p.5, 8, 9 and addendum B.1-2 p.32, which names '
     'J-STD-607-A. Note p.4 of that document says 606, which is a transcription '
     'error in the summary: 606 is administration, 607 is bonding. ', 'ANSI/TIA/EIA-607 (J-STD-607-A)'),
    ('ELV-A-10',
     'TIA-606 reference CONFIRMED in 568-B p.6, 7, 23. Kept SPEC because the '
     'blanket every-link rule is broader than what 568-B states, which is '
     'labelling of MUTOA work area cables and administration of CPs and '
     'cross-connects. ', 'ANSI/TIA/EIA-606'),
    ('ELV-A-11',
     'CORRECTED by 568-B p.10. DC resistance is NOT in the field-test set; it is '
     'a cable component spec (9.38 ohms/100 m max). ACR-F and PSACR-F are the '
     'later names for ELFEXT and PSELFEXT. ', 'ANSI/TIA/EIA-568-B.1'),
    ('ELV-A-12',
     'Loss and polarity CONFIRMED in 568-B p.9, 11; numeric limits are now in '
     'ELV-A-20. End-face inspection is NOT stated in 568-B and remains from '
     'general knowledge. ', 'ANSI/TIA/EIA-568-B.3')
  ) as v(rule_code, note, std)
  where er.organization_id = p_organization_id
    and er.rule_code = v.rule_code;
  get diagnostics v_n = row_count; v_updated := v_updated + v_n;

  -- Name the second source document. Guarded so a re-run does not append twice.
  update public.engineering_rules
     set source_document = source_document || ' + ' || v_src
   where organization_id = p_organization_id
     and rule_code in ('ELV-A-01','ELV-A-02','ELV-A-03','ELV-A-04','ELV-A-08',
                       'ELV-A-09','ELV-A-10','ELV-A-11','ELV-A-12')
     and source_document not like '%' || v_src || '%';

  -- Content corrections, applied to the draft version 1.
  update public.rule_versions rv
     set calculation = c.calculation::jsonb,
         exceptions  = c.exceptions::jsonb
  from (values
    ('ELV-A-02',
     '{"kind":"limit","evaluator":"unassigned","basis":"cable_outside_diameter","utp_installed_multiplier":4,"sctp_installed_multiplier":8,"copper_backbone_multiplier":10,"fibre_horizontal_no_load_mm":25,"fibre_horizontal_under_load_mm":50,"fibre_intrabuilding_backbone_no_load_multiplier":10,"fibre_intrabuilding_backbone_under_load_multiplier":15,"fibre_interbuilding_backbone_no_load_multiplier":10,"fibre_interbuilding_backbone_under_load_multiplier":20,"patch_cord_utp_no_load_mm":6,"patch_cord_sctp_no_load_mm":50,"use":"stricter_of_standard_and_datasheet"}',
     '{"notes":["Cat 6A and shielded cable datasheets are commonly stricter than 4x and then govern.","Corrected 24 Sep 2026: the 20x under-load multiplier is interbuilding backbone only. Intrabuilding backbone is 15x and horizontal 2/4-fibre is an absolute mm figure."]}'),
    ('ELV-A-03',
     '{"kind":"limit","evaluator":"unassigned","max_untwist_mm":13,"max_untwist_in":0.5,"applies_to_category":"5e_and_higher","cat3_maintain_twist_within_mm":76,"cat3_maintain_twist_within_in":3}',
     '{"notes":["Excess untwist raises crosstalk and can stop 10GBASE-T from passing certification.","The 13 mm limit does not apply to Category 3, which uses the 76 mm figure."]}'),
    ('ELV-A-11',
     '{"kind":"checklist","evaluator":"unassigned","coverage_percent":100,"case_study_parameters":["wiremap","insertion_loss","next","return_loss"],"field_test_set_568b":["wiremap","length","insertion_loss","next","psnext","elfext","pselfext","return_loss","propagation_delay","delay_skew"],"renamed_in_later_editions":{"elfext":"acr_f","pselfext":"psacr_f"},"not_a_field_test":{"dc_resistance":"cable component spec, 9.38 ohms per 100 m max"},"retain":"native_result_files_unedited"}',
     '{"notes":["Native tester files, not only the PDF summary. Both go in the handover pack.","Corrected 24 Sep 2026: DC resistance was wrongly listed as a field-test parameter."]}')
  ) as c(rule_code, calculation, exceptions)
  join public.engineering_rules er
    on er.organization_id = p_organization_id and er.rule_code = c.rule_code
  where rv.rule_id = er.id
    and rv.version = 1
    and rv.approval_status = 'draft';

  return v_updated;
end $fn$;

comment on function apply_tia568b_verification(uuid) is
  'Re-verifies and corrects the Part A rules against the supplied condensed '
  'ANSI/TIA/EIA-568-B. Does not set source_verified: that edition is superseded.';

-- ---------------------------------------------------------------------------
-- 2. New rules: Part A additions (A-13..A-21) and the Saudi CCTV law
-- ---------------------------------------------------------------------------

create or replace function elv_rule_seed_v2()
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
  source_document    text,
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
  t.system_code, t.rule_code, t.source_rule_id, t.rule_name,
  t.confidence::public.rule_confidence, t.jurisdiction, t.standard_reference,
  t.priority, t.source_verified, t.verification_note, t.source_document,
  t.conditions::jsonb, t.inputs::jsonb, t.calculation::jsonb,
  t.outputs::jsonb, t.exceptions::jsonb
from (values

-- === Part A additions, from ANSI/TIA/EIA-568-B ==============================

('structured_cabling','ELV-A-13','A-13','Horizontal topology and transition points',
 'code', null, 'ANSI/TIA/EIA-568-B.1', 50, false,
 'Stated in 568-B p.3. Condensed secondary summary of a superseded edition; confirm against ANSI/TIA-568.2-D.',
 'standards-references/tia-eia-568-b/',
 '{"applies_when":[{"fact":"link.media","op":"eq","value":"copper_horizontal"}]}',
 '{"required":[{"key":"run.transition_or_consolidation_points","type":"number"},{"key":"run.has_splice_or_bridged_tap","type":"boolean"}]}',
 '{"kind":"limit","evaluator":"unassigned","topology":"star_to_horizontal_cross_connect","max_transition_or_consolidation_points":1,"forbidden":["bridged_tap","splice_in_copper_horizontal"],"keep_external_to_outlet":["balun","impedance_matching_device"],"closet_per_floor":true,"closet_sized_per":"TIA-569"}',
 '{"emits":"validation","severity":"error","code":"ELV-A-13-TOPOLOGY"}',
 '{"notes":["A consolidation point and a transition point may not share a run. See A-17."]}'),

('structured_cabling','ELV-A-14','A-14','Minimum two telecommunications outlets per work area',
 'code', null, 'ANSI/TIA/EIA-568-B.1 (and B.1-4)', 50, false,
 'Stated in 568-B p.4 and addendum B.1-4 p.34. Condensed secondary summary of a superseded edition. This rule drives outlet, faceplate, jack and horizontal cable counts, so confirm it against the current edition and the project SOW before it sets a quantity.',
 'standards-references/tia-eia-568-b/',
 '{"applies_when":[]}',
 '{"required":[{"key":"work_area.outlet_count","type":"number"},{"key":"work_area.outlet_types","type":"array"}]}',
 '{"kind":"quantity","evaluator":"unassigned","min_outlets_per_work_area":2,"outlet_1":{"media":"4_pair_100_ohm","min_category":"cat3","recommended":["cat5e","cat6"]},"outlet_2":{"one_of":[{"media":"4_pair_100_ohm","category":["cat5e","cat6"]},{"media":"multimode_fibre","fibre_count":2,"types":["62.5/125","50/125"]}]},"recognized_categories":["3","5e","6"],"not_recognized":["1","2","4","5"]}',
 '{"emits":"quantity","unit":"outlet","severity":"error","code":"ELV-A-14-OUTLETS"}',
 '{"notes":["The only rule in the set that emits a quantity rather than a validation result. It is CODE, so under X-06 it can bind without a SOW clause -- which is exactly why its unverified status matters."]}'),

('structured_cabling','ELV-A-15','A-15','Backbone hierarchy and maximum distances',
 'code', null, 'ANSI/TIA/EIA-568-B.1', 50, false,
 'Stated in 568-B p.4-5. Condensed secondary summary of a superseded edition; distances differ under ISO/IEC 11801, so confirm which standard the project uses per X-01.',
 'standards-references/tia-eia-568-b/',
 '{"applies_when":[{"fact":"link.segment","op":"eq","value":"backbone"}]}',
 '{"required":[{"key":"backbone.media","type":"string"},{"key":"backbone.segment","type":"string"},{"key":"backbone.length_m","type":"number"}]}',
 '{"kind":"limit","evaluator":"unassigned","topology":"hierarchical_star","max_cross_connect_levels":2,"max_cross_connects_passed_through":1,"distances_m":{"copper_voice":{"mc_to_hc":800,"mc_to_ic":500,"ic_to_hc":300},"multimode_fibre":{"mc_to_hc":2000,"mc_to_ic":1700,"ic_to_hc":300},"singlemode_fibre":{"mc_to_hc":3000,"mc_to_ic":2700,"ic_to_hc":300}},"distances_inclusive_of":["cable","patch_cords","jumpers","equipment_cable"],"jumper_max_m":{"main_cross_connect":20,"intermediate_cross_connect":20,"equipment":30}}',
 '{"emits":"validation","severity":"error","code":"ELV-A-15-BACKBONE"}',
 '{"notes":["Between any two horizontal cross-connects the signal passes through 3 or fewer cross-connect facilities."]}'),

('structured_cabling','ELV-A-16','A-16','Maximum pulling tension',
 'code', null, 'ANSI/TIA/EIA-568-B.1 and B.3', 50, false,
 'Stated in 568-B p.8 and p.28. Condensed secondary summary of a superseded edition. For multipair copper the standard defers to the manufacturer, so no figure is encoded.',
 'standards-references/tia-eia-568-b/',
 '{"applies_when":[]}',
 '{"required":[{"key":"pull.tension_n","type":"number"},{"key":"cable.type","type":"string"}]}',
 '{"kind":"limit","evaluator":"unassigned","max_tension_n":{"utp_4_pair":110,"fibre_inside_plant_2_or_4":222},"min_pull_strength_n":{"fibre_osp":2670,"fibre_drop":1335},"multipair_copper":"manufacturer_specification","cable_ties":"cinch_loosely_do_not_deform_sheath"}',
 '{"emits":"validation","severity":"error","code":"ELV-A-16-TENSION"}',
 '{"notes":["Pairs with A-02. Exceeding tension or bend radius damages a link in ways certification may not reveal until later."]}'),

('structured_cabling','ELV-A-17','A-17','Consolidation point placement and limits',
 'code', null, 'ANSI/TIA/EIA-568-B.1', 50, false,
 'Stated in 568-B p.7, with the 5 m CP-to-outlet recommendation from addendum B.2-1 p.45. Condensed secondary summary of a superseded edition.',
 'standards-references/tia-eia-568-b/',
 '{"applies_when":[{"fact":"run.has_consolidation_point","op":"eq","value":true}]}',
 '{"required":[{"key":"cp.distance_to_telecom_room_m","type":"number"},{"key":"cp.count_in_run","type":"number"}]}',
 '{"kind":"limit","evaluator":"unassigned","max_per_horizontal_run":1,"may_share_run_with_transition_point":false,"cross_connects_permitted_at_cp":false,"min_distance_to_telecom_room_m":15,"recommended_min_distance_to_outlet_m":5,"location":"fully_accessible_and_permanent","administered_per":"TIA-606"}',
 '{"emits":"validation","severity":"error","code":"ELV-A-17-CP"}',
 '{"notes":["The 15 m minimum exists to limit NEXT and return loss, so it is a performance rule, not a convenience."]}'),

('structured_cabling','ELV-A-18','A-18','MUTOA limits and horizontal length derating',
 'code', null, 'ANSI/TIA/EIA-568-B.1', 50, false,
 'Stated in 568-B p.6. Condensed secondary summary of a superseded edition. The document also notes a second calculation formula that it does not reproduce.',
 'standards-references/tia-eia-568-b/',
 '{"applies_when":[{"fact":"work_area.has_mutoa","op":"eq","value":true}]}',
 '{"required":[{"key":"mutoa.work_areas_served","type":"number"},{"key":"mutoa.work_area_cord_m","type":"number"},{"key":"link.horizontal_length_m","type":"number"},{"key":"cord.awg","type":"string"}]}',
 '{"kind":"limit","evaluator":"unassigned","max_work_areas_served":12,"min_per_furniture_cluster":1,"max_work_area_cord_m":22,"mounting":"permanent_part_of_building","prohibited_locations":["ceiling","furniture_not_permanently_affixed"],"derating_formula":"C = (102 - H) / (1 + D)","derating_factor_D":{"utp_sctp_24awg":0.2,"sctp_26awg":0.5},"published_table_m":[{"horizontal":90,"work_area_cord":5,"combined_cords":10},{"horizontal":85,"work_area_cord":9,"combined_cords":14},{"horizontal":80,"work_area_cord":13,"combined_cords":18},{"horizontal":75,"work_area_cord":17,"combined_cords":22},{"horizontal":70,"work_area_cord":22,"combined_cords":27}],"fibre_reduction_required":false,"administered_per":"TIA-606"}',
 '{"emits":"validation","severity":"error","code":"ELV-A-18-MUTOA"}',
 '{"notes":["Work area cables are labelled at both ends: the outlet end identifies the work area, the work area end identifies the MUTOA and port."]}'),

('structured_cabling','ELV-A-19','A-19','Propagation delay and delay skew limits',
 'code', null, 'ANSI/TIA/EIA-568-B.1', 50, false,
 'Stated in 568-B p.11 and p.48. Condensed secondary summary of a superseded edition; confirm against ANSI/TIA-568.2-D.',
 'standards-references/tia-eia-568-b/',
 '{"applies_when":[{"fact":"link.media","op":"eq","value":"copper_horizontal"}]}',
 '{"required":[{"key":"link.propagation_delay_ns","type":"number"},{"key":"link.delay_skew_ns","type":"number"},{"key":"link.model","type":"string"}]}',
 '{"kind":"limit","evaluator":"unassigned","measured_at_mhz":10,"max_propagation_delay_ns":{"channel":555,"permanent_link":498},"max_delay_skew_ns":{"channel":50,"permanent_link":44},"max_cable_delay_skew_ns_per_100m":45,"per_mated_connection":{"delay_ns":2.5,"skew_ns":1.25}}',
 '{"emits":"validation","severity":"error","code":"ELV-A-19-DELAY"}',
 '{"notes":["These are the numeric limits behind two of the A-11 field-test parameters."]}'),

('structured_cabling','ELV-A-20','A-20','Fibre link attenuation limits and test wavelengths',
 'code', null, 'ANSI/TIA/EIA-568-B.1 and B.3', 50, false,
 'Stated in 568-B p.11. Condensed secondary summary of a superseded edition; confirm against ANSI/TIA-568.3-D.',
 'standards-references/tia-eia-568-b/',
 '{"applies_when":[{"fact":"link.media","op":"eq","value":"fibre"}]}',
 '{"required":[{"key":"link.attenuation_db","type":"number"},{"key":"link.has_consolidation_point","type":"boolean"},{"key":"link.test_wavelength_nm","type":"number"}]}',
 '{"kind":"limit","evaluator":"unassigned","max_horizontal_link_attenuation_db":2.0,"max_with_consolidation_point_db":2.75,"max_with_mutoa_db":2.0,"horizontal_test":{"directions":1,"wavelengths_nm":[850,1300]},"backbone_test":{"multimode_nm":[850,1300],"singlemode_nm":[1310,1550]},"link_attenuation_equation":"cable_attenuation + connector_insertion_loss + splice_insertion_loss","max_splice_attenuation_db":0.3,"min_splice_return_loss_db":{"multimode":20,"singlemode":26,"singlemode_catv":55}}',
 '{"emits":"validation","severity":"error","code":"ELV-A-20-FIBRE-LOSS"}',
 '{"notes":["Gives A-12 a number. A-12 still carries the end-face inspection requirement, which 568-B does not state."]}'),

('structured_cabling','ELV-A-21','A-21','ScTP screen bonding and screen-to-ground potential',
 'code', null, 'ANSI/TIA/EIA-568-B.1-2 (J-STD-607-A)', 50, false,
 'Stated in 568-B addendum B.1-2 p.32 and p.9. Condensed secondary summary of a superseded edition.',
 'standards-references/tia-eia-568-b/',
 '{"applies_when":[{"fact":"cable.screened","op":"eq","value":true}]}',
 '{"required":[{"key":"screen.bonded_to_tgb","type":"boolean"},{"key":"screen.to_ground_v_rms","type":"number"},{"key":"screen.to_ground_v_dc","type":"number"}]}',
 '{"kind":"limit","evaluator":"unassigned","bond_screen_to":"tgb_in_telecommunications_room","bond_horizontal_screen_via":"screen_termination_to_connecting_hardware","max_screen_to_ground_v_rms":1.0,"max_screen_to_ground_v_dc":1.0,"drain_wire_bonded_per":"TIA-607"}',
 '{"emits":"validation","severity":"error","code":"ELV-A-21-SCREEN"}',
 '{"notes":["A measurable acceptance criterion, unlike the qualitative A-09.","Applies only where screened cable is actually installed."]}'),

-- === Saudi Arabia: Law of the Use of Security Surveillance Cameras =========
--
-- All LOCAL and jurisdiction SA. LOCAL here means jurisdiction-bound, not weak:
-- on a Saudi site these are statutory with per-camera fines, and outside Saudi
-- Arabia they do not apply at all. X-06 still asks for a citation before one
-- becomes a BOQ quantity, which is right -- the citation is what establishes
-- that the site falls under this law.

('cctv','KSA-CCTV-01','KSA-CCTV-01','Prior Ministry of Interior approval before any camera work',
 'local', 'SA', 'Law of the Use of Security Surveillance Cameras (Royal Decree, 3 Oct 2022)', 5, true,
 'Confirmed in the Saudipedia summary of the Law, opened 24 Sep 2026. The operative detail sits in Ministerial Decision 22688/1444, which has not been read.',
 'standards-references/saudi-security-camera-law/',
 '{"applies_when":[{"fact":"site.country","op":"eq","value":"SA"}]}',
 '{"required":[{"key":"project.moi_approval_reference","type":"string"},{"key":"project.moi_approval_date","type":"date"}]}',
 '{"kind":"governance","evaluator":"unassigned","approval_required_before":["manufacture","import","sale","installation","operation","maintenance"],"authority":"ministry_of_interior","is_precondition_to_work":true}',
 '{"emits":"validation","severity":"error","code":"KSA-CCTV-01-APPROVAL"}',
 '{"notes":["Penalties: SAR 500 per non-compliant camera, SAR 1000 per improperly installed camera.","This is a precondition to starting work, not a handover document."]}'),

('cctv','KSA-CCTV-02','KSA-CCTV-02','Mandatory installation premises classes',
 'local', 'SA', 'Law of the Use of Security Surveillance Cameras (Royal Decree, 3 Oct 2022)', 50, true,
 'Premises list confirmed in the Saudipedia summary, opened 24 Sep 2026. The list ends with any facility the Ministry deems necessary, so it is not closed.',
 'standards-references/saudi-security-camera-law/',
 '{"applies_when":[{"fact":"site.country","op":"eq","value":"SA"}]}',
 '{"required":[{"key":"project.premises_class","type":"string"}]}',
 '{"kind":"selection","evaluator":"unassigned","mandatory_classes":["ministry","public_institution","power_plant","desalination_plant","oil_facility","commercial_complex","residential_building","bank","two_holy_mosques","mosque","entertainment_venue","stadium","hospital","highway","school","fuel_station","public_transport","restaurant","museum"],"open_ended":"any_other_facility_the_ministry_deems_necessary"}',
 '{"emits":"validation","severity":"critical_review","code":"KSA-CCTV-02-PREMISES"}',
 '{"notes":["Broad enough that most SmartPage project types fall inside it. Confirm per project rather than assuming either way."]}'),

('cctv','KSA-CCTV-03','KSA-CCTV-03','Prohibited camera locations',
 'local', 'SA', 'Law of the Use of Security Surveillance Cameras (Royal Decree, 3 Oct 2022)', 5, true,
 'Confirmed in the Saudipedia summary, opened 24 Sep 2026.',
 'standards-references/saudi-security-camera-law/',
 '{"applies_when":[{"fact":"site.country","op":"eq","value":"SA"}]}',
 '{"required":[{"key":"camera.room_type","type":"string"}]}',
 '{"kind":"clearance","evaluator":"unassigned","prohibited_locations":["medical_operating_room","medical_examination_room","changing_room","restroom","women_salon","private_space","tourist_accommodation_residential_unit"],"check_against":["room_schedule","reflected_ceiling_plan"]}',
 '{"emits":"validation","severity":"error","code":"KSA-CCTV-03-PROHIBITED-LOCATION"}',
 '{"notes":["A hard placement constraint. A camera in one of these rooms is unlawful regardless of client instruction.","Check in the same design pass as B-04."]}'),

('cctv','KSA-CCTV-04','KSA-CCTV-04','Recording retention and incident hold',
 'local', 'SA', 'Ministerial Decision 22688/1444 (Implementing Regulation)', 10, false,
 'The duty to preserve recordings UNALTERED pending investigation is confirmed in the Saudipedia summary. The 90-day retention period is reported consistently by secondary sources (law-firm briefings and news) but was NOT read in an official document. Retention sets NVR and storage sizing and therefore a large part of the CCTV BOQ, so obtain Ministerial Decision 22688/1444 and its Security Conditions and Requirements Document before quoting storage.',
 'standards-references/saudi-security-camera-law/',
 '{"applies_when":[{"fact":"site.country","op":"eq","value":"SA"}]}',
 '{"required":[{"key":"recorder.retention_days","type":"number"},{"key":"recorder.incident_hold_procedure","type":"string"}]}',
 '{"kind":"limit","evaluator":"unassigned","min_retention_days":90,"retention_source":"secondary_unconfirmed","preserve_unaltered_on_incident":true,"until":"completion_of_investigation_procedures","drives":["nvr_sizing","storage_sizing"]}',
 '{"emits":"validation","severity":"critical_review","code":"KSA-CCTV-04-RETENTION"}',
 '{"notes":["Penalty up to SAR 5000 for failing to retain recordings.","Do not size storage from the 90-day figure until it is confirmed against the Implementing Regulation."]}'),

('cctv','KSA-CCTV-05','KSA-CCTV-05','Restriction on transferring or publishing recordings',
 'local', 'SA', 'Law of the Use of Security Surveillance Cameras (Royal Decree, 3 Oct 2022)', 10, true,
 'Confirmed in the Saudipedia summary, opened 24 Sep 2026.',
 'standards-references/saudi-security-camera-law/',
 '{"applies_when":[{"fact":"site.country","op":"eq","value":"SA"}]}',
 '{"required":[{"key":"vms.export_permissions","type":"array"},{"key":"handover.credential_record","type":"string"}]}',
 '{"kind":"governance","evaluator":"unassigned","transfer_or_publication":"prohibited","permitted_only_with":["ministry_approval","court_order","investigative_authority_request"],"implement_via":["vms_export_permissions","credential_handover_record"]}',
 '{"emits":"validation","severity":"error","code":"KSA-CCTV-05-DISCLOSURE"}',
 '{"notes":["Penalty up to SAR 20000 for unlawful transfer or publication, or destruction of equipment.","Makes C-04 a legal exposure rather than only an IT-policy preference."]}'),

('cctv','KSA-CCTV-06','KSA-CCTV-06','Ministry of Interior technical specification for camera systems',
 'local', 'SA', 'MOI general technical specifications for security surveillance camera systems', 50, false,
 'UNCONFIRMED. HD-or-higher resolution is reported by secondary sources only. The MOII conditions document and the Scribd copy of it were both unreadable on 24 Sep 2026. Obtain the MOI general technical specification issued with the executive regulations.',
 'standards-references/saudi-security-camera-law/',
 '{"applies_when":[{"fact":"site.country","op":"eq","value":"SA"}]}',
 '{"required":[{"key":"camera.resolution","type":"string"}]}',
 '{"kind":"selection","evaluator":"unassigned","min_resolution":"hd_or_higher","resolution_source":"secondary_unconfirmed","relationship_to_ELV_C_07":"where the MOI specification sets a floor, that floor binds and C-07 pixel density is the method used to satisfy it"}',
 '{"emits":"validation","severity":"critical_review","code":"KSA-CCTV-06-SPEC"}',
 '{"notes":["Resolve together with C-07 and X-01 rather than treating them as alternatives."]}')

) as t(system_code, rule_code, source_rule_id, rule_name, confidence, jurisdiction,
       standard_reference, priority, source_verified, verification_note,
       source_document, conditions, inputs, calculation, outputs, exceptions);
$fn$;

comment on function elv_rule_seed_v2() is
  'Rules added 24 Sep 2026: Part A additions from the supplied ANSI/TIA/EIA-568-B, '
  'and the Saudi security surveillance camera law.';

create or replace function seed_elv_installation_rules_v2(p_organization_id uuid)
returns integer
language plpgsql
set search_path = ''
as $fn$
declare
  v_loaded integer;
begin
  if not exists (select 1 from public.organizations o where o.id = p_organization_id) then
    raise exception 'organization % does not exist', p_organization_id
      using errcode = 'foreign_key_violation';
  end if;

  if exists (
    select 1 from public.elv_rule_seed_v2() r
    left join public.systems s on s.code = r.system_code
    where r.system_code is not null and s.id is null)
  then
    raise exception 'elv_rule_seed_v2 references a system code with no row in systems';
  end if;

  insert into public.engineering_rules (
    organization_id, system_id, rule_code, name, jurisdiction, standard_reference,
    priority, confidence, source_document, source_rule_id, source_verified,
    verification_note)
  select
    p_organization_id, s.id, r.rule_code, r.rule_name, r.jurisdiction,
    r.standard_reference, r.priority, r.confidence, r.source_document,
    r.source_rule_id, r.source_verified, r.verification_note
  from public.elv_rule_seed_v2() r
  left join public.systems s on s.code = r.system_code
  on conflict do nothing;

  insert into public.rule_versions (
    rule_id, version, conditions, inputs, calculation, outputs, exceptions,
    approval_status)
  select er.id, 1, r.conditions, r.inputs, r.calculation, r.outputs,
         r.exceptions, 'draft'
  from public.elv_rule_seed_v2() r
  join public.engineering_rules er
    on er.organization_id = p_organization_id
   and er.rule_code = r.rule_code
  where not exists (
    select 1 from public.rule_versions rv where rv.rule_id = er.id);

  get diagnostics v_loaded = row_count;
  return v_loaded;
end $fn$;

-- ---------------------------------------------------------------------------
-- 3. Test cases for the new numeric rules
-- ---------------------------------------------------------------------------

create or replace function seed_elv_installation_rule_tests_v2(p_organization_id uuid)
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
    ('ELV-A-02','ScTP needs 8x, so 4x fails',
     '{"cable.outside_diameter_mm":8,"cable.type":"sctp","route.min_bend_radius_mm":32}',
     '{"pass":false,"code":"ELV-A-02-BEND"}'),
    ('ELV-A-02','intrabuilding fibre backbone under load needs 15x not 20x',
     '{"cable.type":"fibre_intrabuilding_backbone","cable.outside_diameter_mm":10,"route.min_bend_radius_mm":150,"route.under_load":true}',
     '{"pass":true}'),
    ('ELV-A-03','Cat 3 at 50 mm untwist passes on the 76 mm limit',
     '{"cable.category":"cat3","termination.untwist_mm":50}',
     '{"pass":true}'),
    ('ELV-A-03','Cat 6 at 50 mm untwist fails on the 13 mm limit',
     '{"cable.category":"cat6","termination.untwist_mm":50}',
     '{"pass":false,"code":"ELV-A-03-UNTWIST"}'),
    ('ELV-A-14','one outlet per work area fails the minimum',
     '{"work_area.outlet_count":1,"work_area.outlet_types":["cat6"]}',
     '{"pass":false,"code":"ELV-A-14-OUTLETS"}'),
    ('ELV-A-14','two outlets, one copper one duplex fibre, passes',
     '{"work_area.outlet_count":2,"work_area.outlet_types":["cat6","multimode_fibre_2"]}',
     '{"pass":true}'),
    ('ELV-A-15','850 m copper voice backbone MC to HC exceeds 800 m',
     '{"backbone.media":"copper_voice","backbone.segment":"mc_to_hc","backbone.length_m":850}',
     '{"pass":false,"code":"ELV-A-15-BACKBONE"}'),
    ('ELV-A-15','1900 m multimode MC to HC is inside the 2000 m limit',
     '{"backbone.media":"multimode_fibre","backbone.segment":"mc_to_hc","backbone.length_m":1900}',
     '{"pass":true}'),
    ('ELV-A-16','130 N on 4-pair UTP exceeds 110 N',
     '{"cable.type":"utp_4_pair","pull.tension_n":130}',
     '{"pass":false,"code":"ELV-A-16-TENSION"}'),
    ('ELV-A-17','consolidation point 10 m from the telecom room is too close',
     '{"run.has_consolidation_point":true,"cp.distance_to_telecom_room_m":10,"cp.count_in_run":1}',
     '{"pass":false,"code":"ELV-A-17-CP"}'),
    ('ELV-A-18','MUTOA serving 14 work areas exceeds the limit of 12',
     '{"work_area.has_mutoa":true,"mutoa.work_areas_served":14,"mutoa.work_area_cord_m":10}',
     '{"pass":false,"code":"ELV-A-18-MUTOA"}'),
    ('ELV-A-18','85 m horizontal with a 9 m work area cord matches the published table',
     '{"work_area.has_mutoa":true,"mutoa.work_areas_served":8,"link.horizontal_length_m":85,"mutoa.work_area_cord_m":9,"cord.awg":"24"}',
     '{"pass":true}'),
    ('ELV-A-19','560 ns channel propagation delay exceeds 555 ns',
     '{"link.model":"channel","link.propagation_delay_ns":560,"link.delay_skew_ns":40}',
     '{"pass":false,"code":"ELV-A-19-DELAY"}'),
    ('ELV-A-19','46 ns permanent link delay skew exceeds 44 ns',
     '{"link.model":"permanent_link","link.propagation_delay_ns":400,"link.delay_skew_ns":46}',
     '{"pass":false,"code":"ELV-A-19-DELAY"}'),
    ('ELV-A-20','2.4 dB horizontal fibre link fails without a consolidation point',
     '{"link.media":"fibre","link.attenuation_db":2.4,"link.has_consolidation_point":false,"link.test_wavelength_nm":850}',
     '{"pass":false,"code":"ELV-A-20-FIBRE-LOSS"}'),
    ('ELV-A-20','2.4 dB passes where a consolidation point raises the limit to 2.75 dB',
     '{"link.media":"fibre","link.attenuation_db":2.4,"link.has_consolidation_point":true,"link.test_wavelength_nm":850}',
     '{"pass":true}'),
    ('ELV-A-21','1.4 V screen-to-ground exceeds the 1.0 V limit',
     '{"cable.screened":true,"screen.bonded_to_tgb":true,"screen.to_ground_v_rms":1.4,"screen.to_ground_v_dc":0.2}',
     '{"pass":false,"code":"ELV-A-21-SCREEN"}'),
    ('KSA-CCTV-03','a camera in a restroom is unlawful',
     '{"site.country":"SA","camera.room_type":"restroom"}',
     '{"pass":false,"code":"KSA-CCTV-03-PROHIBITED-LOCATION"}'),
    ('KSA-CCTV-03','a camera in a corridor is permitted',
     '{"site.country":"SA","camera.room_type":"corridor"}',
     '{"pass":true}'),
    ('KSA-CCTV-03','the prohibition does not apply outside Saudi Arabia',
     '{"site.country":"AE","camera.room_type":"restroom"}',
     '{"pass":true,"reason":"rule_not_applicable"}'),
    ('KSA-CCTV-04','30 days retention is below the reported 90-day requirement',
     '{"site.country":"SA","recorder.retention_days":30}',
     '{"pass":false,"code":"KSA-CCTV-04-RETENTION"}')
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

-- ---------------------------------------------------------------------------
-- 4. Apply to organizations that already exist
-- ---------------------------------------------------------------------------

do $$
declare
  o record;
begin
  for o in select id, name from organizations loop
    perform seed_elv_installation_rules(o.id);        -- in case 0015 predates the org
    perform seed_elv_installation_rule_tests(o.id);
    perform apply_tia568b_verification(o.id);
    perform seed_elv_installation_rules_v2(o.id);
    perform seed_elv_installation_rule_tests_v2(o.id);
    raise notice 'TIA-568-B verification and KSA CCTV rules applied for % (%)', o.name, o.id;
  end loop;
end $$;
