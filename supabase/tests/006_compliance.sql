begin;
select plan(10);

select has_table('public', 'compliance_policies', 'compliance policies table exists');
select has_table('public', 'compliance_evaluations', 'compliance evaluations table exists');
select has_table('public', 'compliance_results', 'compliance results table exists');
select has_table('public', 'remediation_attempts', 'remediation attempts table exists');
select has_column('public', 'compliance_policies', 'automatic_remediation', 'auto remediation is explicit');
select has_column('public', 'compliance_results', 'evidence', 'results retain evidence');
select has_column('public', 'compliance_evaluations', 'score', 'evaluations retain score');
select policy_roles_are('public', 'compliance_policies_member_read', ARRAY['authenticated']);
select policy_roles_are('public', 'compliance_policies_admin_mutate', ARRAY['authenticated']);
select policy_roles_are('public', 'compliance_results_member_read', ARRAY['authenticated']);

select * from finish();
rollback;
