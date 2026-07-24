begin;
select plan(7);

select has_column('public', 'audit_log', 'previous_hash', 'audit records chain previous hash');
select has_column('public', 'audit_log', 'event_hash', 'audit records chain event hash');
select has_table('public', 'retention_policies', 'retention policies table exists');
select has_table('public', 'audit_exports', 'audit exports table exists');
select policy_roles_are('public', 'retention_owner_read', ARRAY['authenticated']);
select policy_roles_are('public', 'audit_exports_owner_read', ARRAY['authenticated']);
select has_index('public', 'audit_log_hash_idx', 'audit hash index exists');

select * from finish();
rollback;
