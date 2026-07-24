begin;
select plan(10);

select has_table('public', 'inventory_snapshots', 'inventory snapshots table exists');
select has_table('public', 'software_inventory', 'software inventory table exists');
select has_table('public', 'software_change_events', 'software change history table exists');
select has_column('public', 'inventory_snapshots', 'payload_hash', 'snapshots have normalized hash');
select has_column('public', 'inventory_snapshots', 'payload', 'snapshots retain normalized payload');
select has_column('public', 'software_inventory', 'software_key', 'software uses normalized key');
select has_column('public', 'software_change_events', 'change_type', 'software changes are typed');
select policy_roles_are('public', 'inventory_member_read', ARRAY['authenticated']);
select policy_roles_are('public', 'software_member_read', ARRAY['authenticated']);
select policy_roles_are('public', 'software_changes_member_read', ARRAY['authenticated']);

select * from finish();
rollback;
