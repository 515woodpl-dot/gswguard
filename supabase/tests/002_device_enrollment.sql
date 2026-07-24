begin;
select plan(9);

select has_table('public', 'devices', 'devices table exists');
select has_table('public', 'enrollment_tokens', 'enrollment tokens table exists');
select has_column('public', 'devices', 'credential_hash', 'device credentials are stored as hashes');
select has_column('public', 'devices', 'revoked_at', 'device revocation is modeled');
select has_column('public', 'devices', 'last_heartbeat_at', 'heartbeat timestamp is modeled');
select has_column('public', 'enrollment_tokens', 'consumed_at', 'single-use consumption is modeled');
select has_column('public', 'enrollment_tokens', 'expires_at', 'enrollment expiry is modeled');
select policy_roles_are('public', 'devices_member_read', ARRAY['authenticated']);
select policy_roles_are('public', 'enrollment_tokens_admin_read', ARRAY['authenticated']);

select * from finish();
rollback;
