-- 0012_seed_placeholders
--
-- Non-engineering placeholders only, per Prompt B.
--
-- Contents are exhaustively:
--   * the 7 roles from spec 6 and their permission codes
--   * 3 rows in `systems` — the initial systems named in spec 5.1
--
-- NOT here, and never to be added by an AI agent: manufacturers, products,
-- product models, authorizations, suppliers, price lists, prices, labour rates,
-- engineering rules, standards. Those are SmartPage data (Appendix A) and are
-- loaded from reviewed source material in knowledge/.

-- ---------------------------------------------------------------------------
-- Systems (spec 5.1). A table rather than an enum, so a fourth system is a row
-- rather than a migration.
-- ---------------------------------------------------------------------------
insert into systems (code, name) values
  ('fire_alarm', 'Fire Alarm'),
  ('cctv',       'CCTV'),
  ('acs',        'Access Control')
on conflict (code) do nothing;

-- ---------------------------------------------------------------------------
-- Roles (spec 6)
-- ---------------------------------------------------------------------------
insert into roles (code, name, description) values
  ('super_admin',         'Super Admin',         'Organization, users, system configuration, all data'),
  ('engineering_manager', 'Engineering Manager', 'Rules, engineering templates, review and approval'),
  ('pre_sales_engineer',  'Pre-Sales Engineer',  'Projects, system design, BOQ, quotation'),
  ('estimator',           'Estimator',           'BOQ, pricing, revisions'),
  ('procurement',         'Procurement',         'RFQs, suppliers, supplier responses'),
  ('supplier',            'Supplier',            'RFQ receipt and quotation response'),
  ('client',              'Client',              'View approved proposals and technical schedules')
on conflict (code) do nothing;

-- ---------------------------------------------------------------------------
-- Permissions
--
-- Stored rather than hard-coded so the permission set is inspectable and
-- auditable (ARCHITECTURE.md 6.2). Grouped by the resource they act on.
-- ---------------------------------------------------------------------------
insert into permissions (code, description) values
  ('organization.manage',      'Manage organization settings and members'),
  ('user.manage',              'Invite, suspend and assign roles to users'),

  ('project.create',           'Create projects'),
  ('project.read',             'View projects'),
  ('project.update',           'Edit project details'),
  ('project.archive',          'Archive projects'),

  ('document.upload',          'Upload project documents'),
  ('document.read',            'View and download documents'),

  ('building_model.edit',      'Create and edit buildings, floors, rooms and doors'),
  ('building_model.review',    'Confirm or reject extracted building-model objects'),

  ('system.select',            'Select systems for a project and set requirements'),

  ('rule.author',              'Create and edit engineering rules'),
  ('rule.approve',             'Approve a rule version for use'),
  ('rule.execute',             'Run engineering rules on a project'),

  ('design.generate',          'Generate system designs'),
  ('design.edit',              'Modify design devices and routes'),

  ('catalogue.manage',         'Manage manufacturers, products and models'),
  ('catalogue.authorize',      'Set product authorization status'),

  ('pricing.manage',           'Manage price lists, rates and pricing rules'),
  ('pricing.view_internal',    'View internal cost build-up and margin'),

  ('boq.generate',             'Generate a BOQ from a validated design'),
  ('boq.edit',                 'Edit BOQ line items'),
  ('boq.approve',              'Approve a BOQ'),

  ('quotation.generate',       'Generate a quotation from an approved BOQ'),
  ('quotation.edit',           'Edit quotation content'),
  ('quotation.approve',        'Approve a quotation revision'),
  ('quotation.issue',          'Issue a quotation to a client'),
  ('quotation.view_customer',  'View the customer-facing quotation'),

  ('validation.run',           'Run validation'),
  ('validation.resolve',       'Resolve or dismiss validation results'),
  ('review_task.resolve',      'Resolve review tasks'),

  ('rfq.manage',               'Create and send RFQs'),
  ('rfq.respond',              'Respond to an RFQ as a supplier'),

  ('audit.read',               'View audit history')
on conflict (code) do nothing;

-- ---------------------------------------------------------------------------
-- Role to permission mapping
--
-- Note what is deliberately absent: 'pricing.view_internal' is granted to no
-- role that faces a customer. Spec 13.3, 21.1 and 29.1 all require internal
-- cost and margin to stay invisible to client users, and the Client role below
-- holds only quotation.view_customer.
-- ---------------------------------------------------------------------------

-- Super Admin: everything.
insert into role_permissions (role_id, permission_id)
select r.id, p.id from roles r cross join permissions p
where r.code = 'super_admin'
on conflict do nothing;

insert into role_permissions (role_id, permission_id)
select r.id, p.id
from roles r
join permissions p on p.code in (
  'project.read','document.read',
  'rule.author','rule.approve','rule.execute',
  'building_model.review','design.generate','design.edit',
  'catalogue.manage','catalogue.authorize',
  'validation.run','validation.resolve','review_task.resolve',
  'boq.approve','audit.read'
)
where r.code = 'engineering_manager'
on conflict do nothing;

insert into role_permissions (role_id, permission_id)
select r.id, p.id
from roles r
join permissions p on p.code in (
  'project.create','project.read','project.update',
  'document.upload','document.read',
  'building_model.edit','building_model.review',
  'system.select','rule.execute',
  'design.generate','design.edit',
  'boq.generate','boq.edit',
  'quotation.generate','quotation.edit',
  'validation.run','review_task.resolve',
  'pricing.view_internal'
)
where r.code = 'pre_sales_engineer'
on conflict do nothing;

insert into role_permissions (role_id, permission_id)
select r.id, p.id
from roles r
join permissions p on p.code in (
  'project.read','document.read',
  'boq.generate','boq.edit',
  'quotation.generate','quotation.edit',
  'pricing.manage','pricing.view_internal',
  'validation.run'
)
where r.code = 'estimator'
on conflict do nothing;

insert into role_permissions (role_id, permission_id)
select r.id, p.id
from roles r
join permissions p on p.code in (
  'project.read','document.read','document.upload',
  'rfq.manage','pricing.manage','pricing.view_internal'
)
where r.code = 'procurement'
on conflict do nothing;

insert into role_permissions (role_id, permission_id)
select r.id, p.id
from roles r
join permissions p on p.code in ('rfq.respond')
where r.code = 'supplier'
on conflict do nothing;

insert into role_permissions (role_id, permission_id)
select r.id, p.id
from roles r
join permissions p on p.code in ('quotation.view_customer')
where r.code = 'client'
on conflict do nothing;
