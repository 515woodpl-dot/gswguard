begin;
select plan(10);

select has_table('public', 'jobs', 'jobs table exists');
select has_table('public', 'event_outbox', 'event outbox table exists');
select has_column('public', 'jobs', 'idempotency_key', 'jobs have idempotency keys');
select has_column('public', 'jobs', 'claim_expires_at', 'jobs have claim leases');
select has_column('public', 'jobs', 'expires_at', 'jobs have expiration');
select has_column('public', 'jobs', 'action_payload', 'jobs have typed action payload');
select has_column('public', 'event_outbox', 'processed_at', 'outbox tracks processing');
select policy_roles_are('public', 'jobs_member_read', ARRAY['authenticated']);
select policy_roles_are('public', 'jobs_admin_create', ARRAY['authenticated']);
select has_index('public', 'jobs_device_poll_idx', 'job polling index exists');

select * from finish();
rollback;
