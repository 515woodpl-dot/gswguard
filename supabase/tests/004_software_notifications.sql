begin;
select plan(5);

select has_table('public', 'notifications', 'notifications table exists');
select has_column('public', 'notifications', 'notification_key', 'notifications have deduplication key');
select has_column('public', 'notifications', 'software_change_event_id', 'notifications correlate software changes');
select policy_roles_are('public', 'notifications_member_read', ARRAY['authenticated']);
select has_index('public', 'notifications_pending_idx', 'pending notification index exists');

select * from finish();
rollback;
