-- pgTAP checks for the Phase 2 migration. Run with Supabase's pgTAP harness.
begin;
select plan(10);

select has_table('public', 'organizations', 'organizations table exists');
select has_table('public', 'profiles', 'profiles table exists');
select has_table('public', 'organization_memberships', 'memberships table exists');
select has_table('public', 'bootstrap_state', 'bootstrap state table exists');
select has_table('public', 'audit_log', 'audit log table exists');
select has_function('public', 'is_org_member', ARRAY['uuid'], 'organization membership helper exists');
select has_function('public', 'has_org_role', ARRAY['uuid', 'public.app_role[]'], 'role helper exists');
select policy_roles_are('public', 'organizations_member_read', ARRAY['authenticated']);
select policy_roles_are('public', 'audit_member_read', ARRAY['authenticated']);
select has_trigger('public', 'audit_log', 'audit_log_immutable', 'audit log immutability trigger exists');

select * from finish();
rollback;
