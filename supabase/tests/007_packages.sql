begin;
select plan(7);

select has_table('public', 'packages', 'packages table exists');
select has_column('public', 'packages', 'expected_sha256', 'packages pin exact hash');
select has_column('public', 'packages', 'expected_size_bytes', 'packages can bound size');
select has_column('public', 'packages', 'drive_shared_drive_id', 'packages retain shared drive metadata');
select has_column('public', 'packages', 'signature_required', 'packages retain signature policy');
select policy_roles_are('public', 'packages_member_read', ARRAY['authenticated']);
select policy_roles_are('public', 'packages_admin_mutate', ARRAY['authenticated']);

select * from finish();
rollback;
