-- 0027_super_admin_all_permissions
--
-- 0012 grants Super Admin every permission, but only those that existed then.
-- 0023 added craft.preview and craft.commit and granted them to the
-- engineering roles alone, so Super Admin -- documented as "all data" -- could
-- not run an engine. This restores the stated rule for every permission that
-- exists now, and a trigger keeps it true for permissions added later, so the
-- next migration that adds one cannot repeat the gap.

insert into role_permissions (role_id, permission_id)
select r.id, p.id from roles r cross join permissions p
where r.code = 'super_admin'
on conflict do nothing;

create or replace function grant_new_permission_to_super_admin()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into role_permissions (role_id, permission_id)
  select r.id, new.id from roles r where r.code = 'super_admin'
  on conflict do nothing;
  return new;
end;
$$;

drop trigger if exists trg_permissions_super_admin on permissions;
create trigger trg_permissions_super_admin
  after insert on permissions
  for each row execute function grant_new_permission_to_super_admin();
