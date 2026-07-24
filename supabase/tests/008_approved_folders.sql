begin;
select plan(10);

select has_table('public', 'approved_folders', 'approved folders table exists');
select has_table('public', 'file_objects', 'file objects table exists');
select has_table('public', 'file_operations', 'file operations audit table exists');
select has_column('public', 'approved_folders', 'allowed_extensions', 'folder extension policy exists');
select has_column('public', 'approved_folders', 'quarantine_enabled', 'folder quarantine policy exists');
select has_column('public', 'file_objects', 'relative_path', 'objects store relative path only');
select has_column('public', 'file_objects', 'provider_version', 'objects pin provider version');
select policy_roles_are('public', 'approved_folders_member_read', ARRAY['authenticated']);
select policy_roles_are('public', 'approved_folders_owner_mutate', ARRAY['authenticated']);
select policy_roles_are('public', 'file_operations_member_read', ARRAY['authenticated']);

select * from finish();
rollback;
