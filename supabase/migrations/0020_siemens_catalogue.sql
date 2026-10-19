-- 0020_siemens_catalogue
--
-- Siemens manufacturer knowledge base, captured 29 Sep 2026: 38 records across
-- Fire (27), LV Distribution (8) and Network (3).
--
-- This is the KB layer that calc_engine/__init__.py names:
--
--     AI layer   decides a calculation is needed, gathers inputs
--     KB layer   supplies manufacturer data  <-- THIS MIGRATION
--     engine     does the maths
--
-- 0006 already created manufacturers / products / product_models with a jsonb
-- technical_specifications. What it lacked was (a) the part number, which is
-- the ordering identity and the thing a BOQ line actually carries, and (b) the
-- handful of NUMERIC fields the engine consumes. Those are added as typed
-- columns, not buried in jsonb, because the engine reads them and a jsonb text
-- blob cannot be summed.
--
-- WHAT THIS DATA CANNOT DO YET. Every fire device here has a quiescent current
-- and NO alarm current. calc_engine.fire_alarm_battery() needs both -- its
-- formula is (I_standby x T_standby + I_alarm x T_alarm) x factor. So rule
-- FA-18 cannot be computed from this catalogue for a single device. The panel
-- FC726-ZA has neither figure, and the panel is usually the largest single
-- draw. The engine_readiness view below reports this rather than letting a
-- null quietly become a zero.
--
-- authorized_status stays 'not_authorized' on every row, which is the 0006
-- default and is correct: capturing a Siemens datasheet does not make SmartPage
-- an authorized reseller. Spec 12.2 needs an in-date authorizations row before
-- automatic selection, and none was supplied.
--
-- Idempotent.

create type mfr_verification_status as enum
  ('verified_mfr', 'pn_only', 'reseller');

comment on type mfr_verification_status is
  'verified_mfr: part number and specs read from a manufacturer datasheet or '
  'service. pn_only: part number confirmed by the manufacturer, specs not '
  'captured. reseller: mapping seen only on a distributor site -- confirm '
  'before quoting.';

alter table product_models
  add column if not exists part_number          text,
  add column if not exists market               text,
  add column if not exists product_line         text,
  add column if not exists verification_status  mfr_verification_status,
  add column if not exists certifications       jsonb not null default '[]'::jsonb,
  add column if not exists approvals            jsonb not null default '[]'::jsonb,
  add column if not exists compatible_accessories jsonb not null default '[]'::jsonb,
  add column if not exists datasheet_url        text,
  add column if not exists source_url           text,
  add column if not exists captured_on          date,
  add column if not exists capture_notes        text,
  -- Engine-facing numerics. Null means NOT CAPTURED and the engine must refuse
  -- to assume a value, which is the whole point of typing them separately.
  add column if not exists supply_voltage       text,
  add column if not exists quiescent_current_ma numeric(10,4),
  add column if not exists alarm_current_ma     numeric(10,4),
  add column if not exists power_w              numeric(10,3),
  add column if not exists poe_budget_w         numeric(10,2),
  add column if not exists poe_ports            integer,
  add column if not exists poe_max_class        integer;

comment on column product_models.part_number is
  'Manufacturer ordering number (Siemens MLFB). This is what goes on a BOQ line.';
comment on column product_models.quiescent_current_ma is
  'Standby current in mA. NULL = not captured. calc_engine must treat NULL as '
  'unknown and refuse the calculation, never as zero.';
comment on column product_models.poe_max_class is
  'Highest IEEE 802.3 class the PSE ports support. Note this is a single value '
  'and cannot express a switch with mixed port classes -- see 6GK5208-0RA00-5AC2.';

create unique index if not exists uq_product_models_part_number
  on product_models (part_number) where part_number is not null;
create index if not exists idx_product_models_engine
  on product_models (verification_status)
  where quiescent_current_ma is not null or poe_budget_w is not null;

create or replace function siemens_seed()
returns table (
  part_number text, model text, family text, product_line text, market text,
  category text, description text, specs jsonb, certs jsonb, approvals jsonb,
  accessories jsonb, datasheet_url text, source_url text,
  verification_status mfr_verification_status, capture_notes text,
  supply_voltage text, quiescent_current_ma numeric, alarm_current_ma numeric,
  power_w numeric, poe_budget_w numeric, poe_ports integer, poe_max_class integer)
language sql immutable
set search_path = ''
as $fn$
select t.part_number, t.model, t.family, t.product_line, t.market, t.category,
       t.description, t.specs::jsonb, t.certs::jsonb, t.approvals::jsonb,
       t.accessories::jsonb, t.datasheet_url, t.source_url,
       lower(replace(t.verification_status,'-','_'))::public.mfr_verification_status,
       t.capture_notes, t.supply_voltage,
       -- Explicit casts: a column of all-NULL literals infers as text.
       t.quiescent_current_ma::numeric, t.alarm_current_ma::numeric,
       t.power_w::numeric, t.poe_budget_w::numeric,
       t.poe_ports::integer, t.poe_max_class::integer
from (values
('S54320-F7-A3', 'OOH740', 'Fire', 'Cerberus PRO FD720 (C-NET)', 'EN 54', 'Automatic fire detector - multi-sensor (optical + heat), ASA', 'Multi-sensor smoke detector, ASAtechnology, for addressable C-NET detector bus', '{"Operating voltage": "DC 12-33 V", "Quiescent current": "~170-250 uA", "Operating temperature": "-25...+55 C", "Protection": "IP40", "Principle": "Dual-angle scattered light + heat"}', '["EN 54-5", "EN 54-7", "EN 54-17", "EN 54-29"]', '["VdS", "LPCB"]', '["DB721 base (S54319-F11-A1)", "DB721D base (S54319-F15-A1)", "DB722 base with seal (S54319-F19-A1)", "BA720 (S54319-F20-A1)", "BA721 (S54319-F29-A1)", "FDUD491 detector exchanger"]', 'https://sid.siemens.com/v/u/A6V10334425', 'https://sid.siemens.com/v/u/A6V10334425', 'VERIFIED-MFR', 'Quiescent uses upper bound 250 uA for battery calc. Alarm current not captured.', '12-33 VDC', 0.25, null, null, null, null, null),
('S54320-F8-A3', 'OOHC740', 'Fire', 'Cerberus PRO FD720 (C-NET)', 'EN 54', 'Automatic fire detector - multi-sensor + CO, neural ASA', 'Fire and CO detector, neural ASAtechnology, C-NET', '{"Operating voltage": "DC 12-33 V", "Quiescent current": "~300-380 uA", "Operating temperature": "-10...+50 C", "Protection": "IP40", "Principle": "Scattered light + heat + CO"}', '["EN 54-5", "EN 54-7", "EN 54-17", "EN 54-29"]', '["VdS", "LPCB"]', '["DB721 base (S54319-F11-A1)", "DB721D base (S54319-F15-A1)", "DB722 base with seal (S54319-F19-A1)"]', 'https://sid.siemens.com/v/u/A6V10334425', 'https://sid.siemens.com/v/u/A6V10334425', 'VERIFIED-MFR', 'EN 54-26 (CO) listing not captured - confirm. Alarm current not captured.', '12-33 VDC', 0.38, null, null, null, null, null),
('S54319-F11-A1', 'DB721', 'Fire', 'Cerberus PRO FD720 (C-NET)', 'EN 54', 'Detector base', 'Standard detector base with loop contact; recess or surface mount (cable dia max 8 mm)', '{}', '[]', '[]', '[]', 'https://sid.siemens.com/v/u/A6V10334425', 'https://sid.siemens.com/v/u/A6V10334425', 'VERIFIED-MFR', null, null, null, null, null, null, null, null),
('S54319-F15-A1', 'DB721D', 'Fire', 'Cerberus PRO FD720 (C-NET)', 'EN 54', 'Detector base', 'Multi-mode base (collective or addressed) with loop contact', '{}', '[]', '[]', '[]', 'https://sid.siemens.com/v/u/A6V10334425', 'https://sid.siemens.com/v/u/A6V10334425', 'VERIFIED-MFR', null, null, null, null, null, null, null, null),
('S54319-F19-A1', 'DB722', 'Fire', 'Cerberus PRO FD720 (C-NET)', 'EN 54', 'Detector base', 'Detector base with seal', '{}', '[]', '[]', '[]', 'https://sid.siemens.com/v/u/A6V10334425', 'https://sid.siemens.com/v/u/A6V10334425', 'VERIFIED-MFR', null, null, null, null, null, null, null, null),
('A5Q00012020', 'FDM225-RP', 'Fire', 'Cerberus PRO', 'EN 54', 'Manual call point', 'Addressable manual call point, indoor, resettable plastic insert', '{"Operating voltage": "DC 12-33 V", "Quiescent current": "180 uA", "Operating temperature": "-25...+70 C", "Protection": "IP44"}', '["EN 54-11 Type A"]', '["VdS G207092", "LPCB 126ap/01"]', '["FDMC295 protective cover (A5Q00013440)", "FDMH295-R back box (A5Q00013437)", "FDMH295-S back box w/ grommets (A5Q00013438)", "FDMK295 reset key (A5Q00013448)", "Plastic insert neutral (A5Q00013445)"]', 'https://sid.siemens.com/v/u/A6V10062093', 'https://sid.siemens.com/v/u/A6V10062093', 'VERIFIED-MFR', null, '12-33 VDC', 0.18, null, null, null, null, null),
('A5Q00013434', 'FDM225-RG', 'Fire', 'Cerberus PRO', 'EN 54', 'Manual call point', 'Addressable manual call point, indoor, glass insert', '{"Operating voltage": "DC 12-33 V", "Quiescent current": "180 uA", "Operating temperature": "-25...+70 C", "Protection": "IP44"}', '["EN 54-11 Type A"]', '["VdS G209194", "LPCB 126ap/02"]', '["FDMC295 protective cover (A5Q00013440)", "FDMH295-R back box (A5Q00013437)", "Glass insert neutral (A5Q00013442)"]', 'https://sid.siemens.com/v/u/A6V10062093', 'https://sid.siemens.com/v/u/A6V10062093', 'VERIFIED-MFR', null, '12-33 VDC', 0.18, null, null, null, null, null),
('A5Q00013436', 'FDM226-RP', 'Fire', 'Cerberus PRO', 'EN 54', 'Manual call point', 'Addressable manual call point, indoor/outdoor, plastic insert, back box included', '{"Operating voltage": "DC 12-33 V", "Quiescent current": "180 uA", "Operating temperature": "-25...+70 C", "Protection": "IP66"}', '["EN 54-11 Type A"]', '["VdS G207092", "LPCB 126ap/03"]', '["FDMC295 protective cover (A5Q00013440)", "FDMK295 reset key (A5Q00013448)"]', 'https://sid.siemens.com/v/u/A6V10062093', 'https://sid.siemens.com/v/u/A6V10062093', 'VERIFIED-MFR', null, '12-33 VDC', 0.18, null, null, null, null, null),
('A5Q00013435', 'FDM226-RG', 'Fire', 'Cerberus PRO', 'EN 54', 'Manual call point', 'Addressable manual call point, indoor/outdoor, glass insert, back box included', '{"Operating voltage": "DC 12-33 V", "Quiescent current": "180 uA", "Operating temperature": "-25...+70 C", "Protection": "IP66"}', '["EN 54-11 Type A"]', '["VdS G209194", "LPCB 126ap/04"]', '["FDMC295 protective cover (A5Q00013440)", "Glass insert neutral (A5Q00013442)"]', 'https://sid.siemens.com/v/u/A6V10062093', 'https://sid.siemens.com/v/u/A6V10062093', 'VERIFIED-MFR', null, '12-33 VDC', 0.18, null, null, null, null, null),
('S54433-C116-A1', 'FC726-ZA', 'Fire', 'Cerberus PRO FS720', 'EN 54', 'Fire control panel - modular, networkable', 'Fire control panel (modular), large housing', '{"Loops": "4 loops / 8 stubs, expandable to 28 loops / 56 stubs", "Max addresses": "1512", "Mains": "AC 115/230 V (+10/-15 %)", "PSU output": "250 W", "Operating voltage": "DC 21-28.4 V", "Operating current": "max 5 A", "Battery": "2 x 12 V, max 45 Ah in housing", "Dimensions": "443 x 802 x 288 mm", "Operating temperature": "-8...+42 C", "Protection": "IP30", "Compatible detector series": "FD720, Cerberus Nova, SynoLOOP"}', '["EN 54-2 / EN 54-4 (not explicitly listed in datasheet - confirm)"]', '["VdS G210084", "LPCB 126bn/08", "FM 3051081"]', '["FCL2008-A1 line card FDnet/C-NET (S54400-A182-A1) - model as extracted, confirm", "FCI2008-A1 programmable I/O card (S54400-A6-A1)", "FTO2001-A1 event printer (A5Q00010126)", "FCA2001-A1 RS232 module (A5Q00005327)", "FA2007-A1 battery 45 Ah (A5Q00022897)", "CXG3.X200 Connect X200 gateway (S55842-Z131-A100)"]', 'https://sid.siemens.com/v/u/A6V10303108', 'https://sid.siemens.com/v/u/A6V10303108', 'VERIFIED-MFR', 'Panel quiescent/alarm current not in datasheet - take from Siemens battery calc tool / FX7230 planning. SID page also lists stock no. S54400-C87-A1 against FC726-ZA - confirm whether earlier variant.', '115/230 VAC', null, null, null, null, null, null),
('A5Q00022897', 'FA2007-A1', 'Fire', 'Cerberus PRO FS720', 'EN 54', 'Standby battery', 'Battery 12 V 45 Ah (VdS)', '{"Voltage": "12 V", "Capacity": "45 Ah"}', '[]', '["VdS"]', '[]', 'https://sid.siemens.com/v/u/A6V10303108', 'https://sid.siemens.com/v/u/A6V10303108', 'VERIFIED-MFR', null, null, null, null, null, null, null, null),
('A5Q00004813', 'FDOOT241-9', 'Fire', 'Sinteso S-LINE (FDnet)', 'EN 54', 'Automatic fire detector - multi-sensor', 'Multi-sensor fire detector, FDnet', '{"Operating voltage": "DC 12-33 V", "Quiescent current": "65-230 uA", "Operating temperature": "-25...+70 C", "Protection": "IP43 std base / IP44 with accessory"}', '["EN 54 parts per doc 007005 - confirm (extraction listed 54-5, 54-17)"]', '["VdS", "LPCB", "FM"]', '["FDB221 base (surface/recess)", "FDB222 base (flush)"]', 'https://sid.siemens.com/v/u/A6V10061740', 'https://sid.siemens.com/v/u/A6V10061740', 'VERIFIED-MFR', null, '12-33 VDC', 0.23, null, null, null, null, null),
('S54310-F21-A1', 'FDOOT241-A', 'Fire', 'Sinteso S-LINE (FDnet)', 'EN 54', 'Automatic fire detector - multi-sensor', 'Multi-sensor fire detector, FDnet', '{"Operating voltage": "DC 12-33 V", "Quiescent current": "180-230 uA", "Operating temperature": "-35...+70 C"}', '[]', '["VdS", "LPCB", "FM"]', '["FDB221 base", "FDB222 base"]', 'https://sid.siemens.com/v/u/A6V10061740', 'https://sid.siemens.com/v/u/A6V10061740', 'VERIFIED-MFR', null, '12-33 VDC', 0.23, null, null, null, null, null),
('S54310-F19-A1', 'FDO241', 'Fire', 'Sinteso S-LINE (FDnet)', 'EN 54', 'Automatic fire detector - optical smoke', 'Optical smoke detector, FDnet', '{"Operating voltage": "DC 12-33 V", "Quiescent current": "130-200 uA", "Operating temperature": "-25...+70 C"}', '["EN 54-7"]', '["VdS", "LPCB", "FM"]', '["FDB221 base", "FDB222 base"]', 'https://sid.siemens.com/v/u/A6V10061740', 'https://sid.siemens.com/v/u/A6V10061740', 'VERIFIED-MFR', null, '12-33 VDC', 0.2, null, null, null, null, null),
('A5Q00004812', 'FDT241', 'Fire', 'Sinteso S-LINE (FDnet)', 'EN 54', 'Automatic fire detector - heat', 'Heat detector, FDnet', '{"Operating voltage": "DC 12-33 V", "Quiescent current": "130-200 uA", "Operating temperature": "-25...+50 C (parameter-set dependent)"}', '["EN 54-5"]', '["VdS", "FM"]', '["FDB221 base", "FDB222 base"]', 'https://sid.siemens.com/v/u/A6V10061740', 'https://sid.siemens.com/v/u/A6V10061740', 'VERIFIED-MFR', null, '12-33 VDC', 0.2, null, null, null, null, null),
('S54329-F7-A1', 'FDOOT241-A9-Ex', 'Fire', 'Sinteso (FDnet) - Ex', 'EN 54 / ATEX', 'Automatic fire detector - multi-sensor, intrinsically safe', 'Multi-sensor fire detector for hazardous areas', '{}', '[]', '[]', '[]', 'https://sid.siemens.com/v/u/A6V10444387', 'https://sid.siemens.com/v/u/A6V10444387', 'PN-ONLY', 'Datasheet A6V10349345; installation A6V10349621. Specs not yet captured.', null, null, null, null, null, null, null),
('S54433-C105-A1', 'FC901', 'Fire', 'Cerberus PRO (US)', 'UL', 'Fire control panel - 50 point', '50-point addressable panel with built-in DACT and 2 NACs, 24 VDC nominal', '{}', '["UL 864 10th Edition"]', '["FM 3010", "CSFM 7165-0067:0259", "FDNY 6104"]', '[]', 'https://cdn.thefirepanel.com/docs/siemens/Siemens%20-%20Cerberus%20Pro%20Comprehensive%20Fire%20Protection%20System%20Data%20Sheet.pdf', 'https://cdn.thefirepanel.com/docs/siemens/Siemens%20-%20Cerberus%20Pro%20Comprehensive%20Fire%20Protection%20System%20Data%20Sheet.pdf', 'VERIFIED-MFR', 'Source: Siemens datasheet 9800 rev 9 (Nov 2021)', null, null, null, null, null, null, null),
('S54400-Z60-A1', 'FP2012-U1', 'Fire', 'Cerberus PRO (US)', 'UL', 'Power supply module', '300 W power supply, 11.5 A at 24 VDC', '{"Output": "300 W / 11.5 A @ 24 VDC"}', '[]', '[]', '[]', 'https://cdn.thefirepanel.com/docs/siemens/Siemens%20-%20Cerberus%20Pro%20Comprehensive%20Fire%20Protection%20System%20Data%20Sheet.pdf', 'https://cdn.thefirepanel.com/docs/siemens/Siemens%20-%20Cerberus%20Pro%20Comprehensive%20Fire%20Protection%20System%20Data%20Sheet.pdf', 'VERIFIED-MFR', null, null, null, null, 300, null, null, null),
('500-450222', 'FP2011-U1', 'Fire', 'Cerberus PRO (US)', 'UL', 'Power supply module', '170 W power supply, 6.5 A at 24 VDC', '{"Output": "170 W / 6.5 A @ 24 VDC"}', '[]', '[]', '[]', 'https://cdn.thefirepanel.com/docs/siemens/Siemens%20-%20Cerberus%20Pro%20Comprehensive%20Fire%20Protection%20System%20Data%20Sheet.pdf', 'https://cdn.thefirepanel.com/docs/siemens/Siemens%20-%20Cerberus%20Pro%20Comprehensive%20Fire%20Protection%20System%20Data%20Sheet.pdf', 'VERIFIED-MFR', null, null, null, null, 170, null, null, null),
('S54400-A60-A1', 'FN2001-U1', 'Fire', 'Cerberus PRO (US)', 'UL', 'Network module', 'C-WEB network module - up to 32 panels (SafeDLink / CV Web)', '{}', '[]', '[]', '[]', 'https://cdn.thefirepanel.com/docs/siemens/Siemens%20-%20Cerberus%20Pro%20Comprehensive%20Fire%20Protection%20System%20Data%20Sheet.pdf', 'https://cdn.thefirepanel.com/docs/siemens/Siemens%20-%20Cerberus%20Pro%20Comprehensive%20Fire%20Protection%20System%20Data%20Sheet.pdf', 'VERIFIED-MFR', null, null, null, null, null, null, null, null),
('S54400-A63-A1', 'FCA2015-U1', 'Fire', 'Cerberus PRO (US)', 'UL', 'Communicator', 'Digital alarm communicator transmitter (DACT)', '{}', '[]', '[]', '[]', 'https://cdn.thefirepanel.com/docs/siemens/Siemens%20-%20Cerberus%20Pro%20Comprehensive%20Fire%20Protection%20System%20Data%20Sheet.pdf', 'https://cdn.thefirepanel.com/docs/siemens/Siemens%20-%20Cerberus%20Pro%20Comprehensive%20Fire%20Protection%20System%20Data%20Sheet.pdf', 'VERIFIED-MFR', null, null, null, null, null, null, null, null),
('S54400-A39-A1', 'FCA2016-U1', 'Fire', 'Cerberus PRO (US)', 'UL', 'Interface module', 'RS-485 interface', '{}', '[]', '[]', '[]', 'https://cdn.thefirepanel.com/docs/siemens/Siemens%20-%20Cerberus%20Pro%20Comprehensive%20Fire%20Protection%20System%20Data%20Sheet.pdf', 'https://cdn.thefirepanel.com/docs/siemens/Siemens%20-%20Cerberus%20Pro%20Comprehensive%20Fire%20Protection%20System%20Data%20Sheet.pdf', 'VERIFIED-MFR', null, null, null, null, null, null, null, null),
('S54400-A65-A1', 'FCA2018-U1', 'Fire', 'Cerberus PRO (US)', 'UL', 'Interface module', 'Remote peripheral module', '{}', '[]', '[]', '[]', 'https://cdn.thefirepanel.com/docs/siemens/Siemens%20-%20Cerberus%20Pro%20Comprehensive%20Fire%20Protection%20System%20Data%20Sheet.pdf', 'https://cdn.thefirepanel.com/docs/siemens/Siemens%20-%20Cerberus%20Pro%20Comprehensive%20Fire%20Protection%20System%20Data%20Sheet.pdf', 'VERIFIED-MFR', null, null, null, null, null, null, null, null),
('S54400-B80-A1', 'FT2014-U3', 'Fire', 'Cerberus PRO (US)', 'UL', 'Remote display terminal', 'Remote display terminal, black (red variant FT2014-R3 S54400-B73-A1)', '{}', '[]', '[]', '[]', 'https://cdn.thefirepanel.com/docs/siemens/Siemens%20-%20Cerberus%20Pro%20Comprehensive%20Fire%20Protection%20System%20Data%20Sheet.pdf', 'https://cdn.thefirepanel.com/docs/siemens/Siemens%20-%20Cerberus%20Pro%20Comprehensive%20Fire%20Protection%20System%20Data%20Sheet.pdf', 'VERIFIED-MFR', null, null, null, null, null, null, null, null),
('S54400-B88-A1', 'FT2015-U3', 'Fire', 'Cerberus PRO (US)', 'UL', 'Remote display terminal', 'Remote display terminal with controls, black (red variant FT2015-R3 S54400-B16-A1)', '{}', '[]', '[]', '[]', 'https://cdn.thefirepanel.com/docs/siemens/Siemens%20-%20Cerberus%20Pro%20Comprehensive%20Fire%20Protection%20System%20Data%20Sheet.pdf', 'https://cdn.thefirepanel.com/docs/siemens/Siemens%20-%20Cerberus%20Pro%20Comprehensive%20Fire%20Protection%20System%20Data%20Sheet.pdf', 'VERIFIED-MFR', null, null, null, null, null, null, null, null),
('S54320-F4-A1', 'FDO421', 'Fire', 'Cerberus PRO (US)', 'UL', 'Automatic fire detector - photoelectric smoke', 'Smoke detector (SiePortal: ''FDO421 - Smoke Detector''), status Active', '{"Net weight": "0.108 kg", "Country of origin": "China"}', '["RoHS"]', '[]', '[]', 'https://mall.industry.siemens.com/mall/en/WW/Catalog/Product/S54320-F4-A1', 'https://mall.industry.siemens.com/mall/en/WW/Catalog/Product/S54320-F4-A1', 'PN-ONLY', null, null, null, null, null, null, null, null),
('S54320-F4-A2', 'OP921', 'Fire', 'Cerberus PRO (US)', 'UL', 'Automatic fire detector - photoelectric smoke', 'Intelligent photoelectric smoke detector', '{}', '[]', '[]', '[]', 'NOT CAPTURED', 'https://thefirealarmsupplier.com/products/siemens-op921-s54320-f4-a2-smoke-detector', 'RESELLER', 'Confirm part number on SiePortal before quoting.', null, null, null, null, null, null, null),
('5SL6116-7', '5SL6116-7', 'LV Distribution', 'SENTRON 5SL', 'IEC', 'Miniature circuit breaker', 'Miniature circuit breaker 230/400 V 6 kA, 1-pole, C, 16 A', '{"Rated current": "16 A @30 C (15.23 A @40 C, 13.99 A @55 C)", "Breaking capacity": "6 kA (EN 60898 & IEC 60947-2)", "Energy limitation class": "3", "Power loss": "1.8 W/pole", "Conductors": "0.75-25 mm2", "Ambient": "-25...+45 C", "Protection": "IP20 with conductors connected"}', '["IEC/EN 60898-1", "IEC 60947-2"]', '[]', '["5ST3010 auxiliary switch 1NO+1NC"]', 'https://support.industry.siemens.com/teddatasheet/?format=pdf&mlfbs=5SL6116-7&language=en', 'https://support.industry.siemens.com/teddatasheet/?format=pdf&mlfbs=5SL6116-7&language=en', 'VERIFIED-MFR', null, null, null, null, 1.8, null, null, null),
('5SL6316-7', '5SL6316-7', 'LV Distribution', 'SENTRON 5SL', 'IEC', 'Miniature circuit breaker', 'Miniature circuit breaker 400 V 6 kA, 3-pole, C, 16 A', '{"Breaking capacity": "6 kA (EN 60898 & IEC 60947-2)", "Power loss": "1.8 W/pole", "Conductors": "0.75-25 mm2", "Ambient": "-25...+45 C", "Protection": "IP20"}', '["IEC/EN 60898-1", "IEC 60947-2"]', '[]', '["5ST3010 auxiliary switch 1NO+1NC"]', 'https://support.industry.siemens.com/teddatasheet/?format=pdf&mlfbs=5SL6316-7&language=en', 'https://support.industry.siemens.com/teddatasheet/?format=pdf&mlfbs=5SL6316-7&language=en', 'VERIFIED-MFR', 'power_w DERIVED: 1.8 W/pole x 3 poles.', null, null, null, 5.4, null, null, null),
('5SY6116-7', '5SY6116-7', 'LV Distribution', 'SENTRON 5SY', 'IEC', 'Miniature circuit breaker', 'Miniature circuit breaker 230/400 V 6 kA, 1-pole, C, 16 A', '{"Breaking capacity": "6 kA EN 60898 / 15 kA IEC 60947-2", "Power loss": "1.6 W/pole", "Conductors": "0.75-35 mm2 solid/stranded", "Ambient": "-25...+55 C", "Dimensions": "90 x 18 x 76 mm", "Mechanical life": "10,000 cycles"}', '["IEC/EN 60898-1", "IEC 60947-2"]', '[]', '["5ST3010 auxiliary switch 1NO+1NC"]', 'https://support.industry.siemens.com/teddatasheet/?format=pdf&mlfbs=5SY6116-7&language=en', 'https://support.industry.siemens.com/teddatasheet/?format=pdf&mlfbs=5SY6116-7&language=en', 'VERIFIED-MFR', '5SY vs 5SL at same rating: 5SY has 15 kA IEC 60947-2 rating and 55 C ambient - relevant for Gulf panels.', null, null, null, 1.6, null, null, null),
('5SV3344-6', '5SV3344-6', 'LV Distribution', 'SENTRON 5SV', 'IEC', 'Residual current circuit breaker (RCCB)', 'RCCB 4-pole, 40 A, 30 mA, type A, 400 V', '{"Short-circuit strength": "10 kA", "Power loss": "3.9 W/pole", "Conductors": "0.75-35 mm2", "Ambient": "-25...+45 C"}', '["IEC/EN 61008-1 (standard not named in extract - confirm)"]', '[]', '["5ST3010 auxiliary switch 1NO+1NC"]', 'https://support.industry.siemens.com/teddatasheet/?format=pdf&mlfbs=5SV3344-6&language=en', 'https://support.industry.siemens.com/teddatasheet/?format=pdf&mlfbs=5SV3344-6&language=en', 'VERIFIED-MFR', 'power_w DERIVED: 3.9 W/pole x 4 poles.', null, null, null, 15.6, null, null, null),
('5ST3010', '5ST3010', 'LV Distribution', 'SENTRON 5ST', 'IEC', 'Accessory - auxiliary switch', 'Auxiliary switch 1 NO + 1 NC for miniature circuit breakers, 9 mm', '{"Mounts to": "5SL, 5SY, 5SP MCB; 5TL1; 5SU1 RCBO; 5SV RCCB", "Width": "9 mm", "Ambient": "-25...+55 C", "Protection": "IP20"}', '["IEC/EN 60947-5-1", "IEC/EN 62019"]', '[]', '[]', 'https://support.industry.siemens.com/teddatasheet/?format=pdf&mlfbs=5ST3010&language=en', 'https://support.industry.siemens.com/teddatasheet/?format=pdf&mlfbs=5ST3010&language=en', 'VERIFIED-MFR', null, null, null, null, null, null, null, null),
('3VA1110-4EF32-0AA0', '3VA1110-4EF32-0AA0', 'LV Distribution', 'SENTRON 3VA1', 'IEC', 'Moulded case circuit breaker (MCCB)', 'MCCB 3VA1, IEC frame 160, 100 A, 3-pole, TM240 thermal-magnetic trip unit', '{"Icu @415 V": "36 kA", "Ics @415 V": "36 kA", "Ui": "800 V", "Ue": "AC 690 V", "Power loss": "max 25 W", "Connection": "Flat bar 12x1 to 17x6.5 mm (nut keeper kit)", "Ambient": "-25...+70 C"}', '["IEC 60947-2"]', '[]', '["Motor operator (optional, per datasheet)"]', 'https://support.industry.siemens.com/teddatasheet/?format=pdf&mlfbs=3VA1110-4EF32-0AA0&language=en', 'https://support.industry.siemens.com/teddatasheet/?format=pdf&mlfbs=3VA1110-4EF32-0AA0&language=en', 'VERIFIED-MFR', null, null, null, null, 25, null, null, null),
('3RV2011-1JA10', '3RV2011-1JA10', 'LV Distribution', 'SIRIUS 3RV2', 'IEC', 'Motor protection circuit breaker', 'Circuit breaker size S00 for motor protection, 7-10 A', '{"Setting range": "7-10 A", "Ue": "690 V", "Icu @400 V": "100 kA", "Power loss": "9.25 W", "Ambient": "-20...+60 C", "Dimensions": "97 x 45 x 97 mm", "B10 (high demand)": "5,000 cycles"}', '["IEC 60947-4-1 / -2", "IEC 61508 Type A"]', '["UL E47705", "UL E156943", "ATEX 2014/34/EU"]', '[]', 'https://support.industry.siemens.com/teddatasheet/?format=pdf&mlfbs=3RV2011-1JA10&language=en', 'https://support.industry.siemens.com/teddatasheet/?format=pdf&mlfbs=3RV2011-1JA10&language=en', 'VERIFIED-MFR', null, null, null, null, 9.25, null, null, null),
('7KM2112-0BA00-3AA0', 'SENTRON PAC3200', 'LV Distribution', 'SENTRON PAC', 'IEC', 'Power monitoring device', 'PAC3200, LCD, L-L 690 V / L-N 400 V, 5 A, 3-phase, Modbus TCP', '{"Aux supply": "95-240 V AC / 110-340 V DC", "Accuracy": "Class 0.5 (IEC 61557-12) / 0.5S (IEC 62053-22)", "Interface": "1 x Fast Ethernet, Modbus TCP", "Ambient": "-10...+55 C", "Protection": "IP65 front / IP54 rear"}', '["EN 61010-1", "IEC 61557-12", "IEC 62053-22"]', '[]', '[]', 'https://support.industry.siemens.com/teddatasheet/?format=pdf&mlfbs=7KM2112-0BA00-3AA0&language=en', 'https://support.industry.siemens.com/teddatasheet/?format=pdf&mlfbs=7KM2112-0BA00-3AA0&language=en', 'VERIFIED-MFR', 'Successor (PAC3220) not stated in TED datasheet - check SiePortal lifecycle before quoting.', null, null, null, null, null, null, null),
('6GK5208-0BA00-2AC2', 'SCALANCE XC208', 'Network', 'SCALANCE XC-200', 'IEC/UL', 'Managed Layer 2 industrial Ethernet switch', 'XC208 managed L2 IE switch; IEC 62443-4-2 certified; 8 x 10/100 RJ45; console; redundant PSU', '{"Supply": "24 V DC (9.6-31.2 V)", "Power loss": "4.2 W @24 V", "Max current": "0.35 A", "Ports": "8 x RJ45 10/100, 1 x RJ11 console, signalling contact", "Operating temperature": "-40...+70 C", "Protection": "IP20"}', '["IEC 62443-4-2:2019", "CE", "RoHS", "EN 50121-4"]', '["cULus", "KC", "RCM", "ATEX", "UKEX", "IECEx", "UL HazLoc", "CCC", "FM", "ABS", "DNV", "NK", "RINA"]', '[]', 'https://support.industry.siemens.com/teddatasheet/?format=pdf&mlfbs=6GK5208-0BA00-2AC2&language=en', 'https://support.industry.siemens.com/teddatasheet/?format=pdf&mlfbs=6GK5208-0BA00-2AC2&language=en', 'VERIFIED-MFR', null, '24 VDC', null, null, 4.2, null, null, null),
('6GK5206-2BD00-2AC2', 'SCALANCE XC206-2 (SC)', 'Network', 'SCALANCE XC-200', 'IEC/UL', 'Managed Layer 2 industrial Ethernet switch', 'XC206-2 managed L2 IE switch; IEC 62443-4-2; 6 x 10/100 RJ45; 2 x 100 Mbit/s SC multimode', '{"Supply": "24 V DC (9.6-31.2 V)", "Power loss": "6 W", "Max current": "0.5 A", "Ports": "6 x RJ45, 2 x SC MM, console", "Operating temperature": "-40...+70 C", "Protection": "IP20"}', '["IEC 62443-4-2:2019", "CE", "RoHS", "EN 50121-4"]', '["cULus", "KC", "RCM", "ATEX", "UKEX", "IECEx", "UL HazLoc", "DNV", "NK", "RINA"]', '[]', 'https://support.industry.siemens.com/teddatasheet/?format=pdf&mlfbs=6GK5206-2BD00-2AC2&language=en', 'https://support.industry.siemens.com/teddatasheet/?format=pdf&mlfbs=6GK5206-2BD00-2AC2&language=en', 'VERIFIED-MFR', null, '24 VDC', null, null, 6, null, null, null),
('6GK5208-0RA00-5AC2', 'SCALANCE XC208G PoE (54 V)', 'Network', 'SCALANCE XC-200', 'IEC/UL', 'Managed Layer 2 PoE switch', 'XC208G PoE managed L2 switch; IEC 62443-4-2; 8 x GbE RJ45 (4 x 802.3at + 2 x 802.3bt + 2 non-PoE)', '{"Supply": "54 V DC (52-57 V), max 5 A", "PoE": "4 x 802.3at 30 W, 2 x 802.3bt 60 W", "PoE budget": "240 W distributed across PoE ports (PSE total stated 260 W)", "Operating temperature": "-40...+60 C", "Protection": "IP20"}', '["IEC 62443-4-2", "CE", "RoHS", "EN 50121-4"]', '["KC", "RCM", "ATEX", "UKEX", "IECEx", "FM"]', '[]', 'https://support.industry.siemens.com/teddatasheet/?format=pdf&mlfbs=6GK5208-0RA00-5AC2&language=en', 'https://support.industry.siemens.com/teddatasheet/?format=pdf&mlfbs=6GK5208-0RA00-5AC2&language=en', 'VERIFIED-MFR', 'Budget uses the LOWER (240 W) of two stated figures. MIXED PORT CLASSES: Class 6 only on the 2 bt ports; the 4 at ports are max Class 4. calc_engine.poe_budget() takes a single max_port_class and cannot model this - see engine gap note.', '54 VDC', null, null, null, 240, 6, 6)) as t(part_number, model, family, product_line, market, category, description,
       specs, certs, approvals, accessories, datasheet_url, source_url,
       verification_status, capture_notes, supply_voltage, quiescent_current_ma,
       alarm_current_ma, power_w, poe_budget_w, poe_ports, poe_max_class);
$fn$;

create or replace function seed_siemens_catalogue(p_organization_id uuid)
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

  insert into public.manufacturers (organization_id, name)
  values (p_organization_id, 'Siemens')
  on conflict (organization_id, name) do nothing;

  -- One products row per (product_line, category); models hang off it.
  insert into public.products (manufacturer_id, product_family, category, description)
  select distinct m.id, s.family, s.category,
         s.product_line || ' - ' || s.category
  from public.siemens_seed() s
  join public.manufacturers m
    on m.organization_id = p_organization_id and m.name = 'Siemens'
  where not exists (
    select 1 from public.products p
    where p.manufacturer_id = m.id and p.product_family = s.family
      and p.category = s.category
      and p.description = s.product_line || ' - ' || s.category);

  insert into public.product_models (
    product_id, model, technical_specifications, part_number, market,
    product_line, verification_status, certifications, approvals,
    compatible_accessories, datasheet_url, source_url, captured_on,
    capture_notes, supply_voltage, quiescent_current_ma, alarm_current_ma,
    power_w, poe_budget_w, poe_ports, poe_max_class)
  select p.id, s.model, s.specs, s.part_number, s.market, s.product_line,
         s.verification_status, s.certs, s.approvals, s.accessories,
         nullif(s.datasheet_url, 'NOT CAPTURED'), s.source_url,
         date '2026-09-29', s.capture_notes, s.supply_voltage,
         s.quiescent_current_ma, s.alarm_current_ma, s.power_w,
         s.poe_budget_w, s.poe_ports, s.poe_max_class
  from public.siemens_seed() s
  join public.manufacturers m
    on m.organization_id = p_organization_id and m.name = 'Siemens'
  join public.products p
    on p.manufacturer_id = m.id and p.product_family = s.family
   and p.category = s.category
   and p.description = s.product_line || ' - ' || s.category
  where not exists (
    select 1 from public.product_models pm where pm.part_number = s.part_number);

  get diagnostics v_loaded = row_count;
  return v_loaded;
end $fn$;

comment on function seed_siemens_catalogue(uuid) is
  'Loads the Siemens capture. authorized_status stays not_authorized: a '
  'datasheet is not an authorization (spec 12.2).';

-- ---------------------------------------------------------------------------
-- Engine readiness
-- ---------------------------------------------------------------------------
-- Answers the question a designer actually has: "can I run this calculation
-- with the data I hold?" A null current is not a zero, and this view is what
-- stops it being treated as one.

create or replace view engine_readiness as
select
  pm.part_number, pm.model, p.product_family as family, pm.verification_status,
  'fire_alarm_battery' as calculator_module,
  (pm.quiescent_current_ma is not null and pm.alarm_current_ma is not null) as ready,
  array_remove(array[
    case when pm.quiescent_current_ma is null then 'quiescent_current_ma' end,
    case when pm.alarm_current_ma     is null then 'alarm_current_ma'     end
  ], null) as missing_fields
from public.product_models pm
join public.products p on p.id = pm.product_id
-- Only items that actually draw current. A detector base is passive and will
-- never have a standby figure, so listing it as "not ready" would be noise.
where p.product_family = 'Fire'
  and (p.category ilike '%detector%'
       or p.category ilike '%call point%'
       or p.category ilike '%panel%')
  and p.category not ilike '%base%'
union all
select
  pm.part_number, pm.model, p.product_family, pm.verification_status,
  'poe_budget',
  (pm.poe_budget_w is not null and pm.poe_ports is not null
     and pm.poe_max_class is not null),
  array_remove(array[
    case when pm.poe_budget_w  is null then 'poe_budget_w'  end,
    case when pm.poe_ports     is null then 'poe_ports'     end,
    case when pm.poe_max_class is null then 'poe_max_class' end
  ], null)
from public.product_models pm
join public.products p on p.id = pm.product_id
where p.category ilike '%PoE%';

comment on view engine_readiness is
  'Which catalogue items can feed which calc_engine module, and what is missing '
  'when they cannot. A null numeric means NOT CAPTURED, never zero.';

do $$
declare o record; n integer;
begin
  for o in select id, name from organizations loop
    select seed_siemens_catalogue(o.id) into n;
    raise notice 'Siemens catalogue: % model(s) loaded for %', n, o.name;
  end loop;
end $$;
