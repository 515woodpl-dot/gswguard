-- Make client roles read-only. Audit finding C2 (docs/audit-2026-07-29.md).
--
-- Problem
-- -------
-- Supabase grants `anon` and `authenticated` full DML on every table in
-- `public` by default. Verified on the live project:
--
--   devices  authenticated  DELETE,INSERT,REFERENCES,SELECT,TRIGGER,TRUNCATE,UPDATE
--
-- RLS was therefore the only control standing between a browser holding the
-- public anon key plus a user JWT and these tables. Three policies then opened
-- that door deliberately:
--
--   devices_admin_mutate              FOR ALL     (select+insert+update+delete)
--   jobs_admin_create                 FOR INSERT
--   jobs_admin_cancel                 FOR UPDATE  (no WITH CHECK)
--   compliance_policies_admin_mutate  FOR ALL
--   packages_admin_mutate             FOR ALL
--   approved_folders_owner_mutate     FOR ALL
--
-- Through PostgREST an administrator session - or a stolen one - could insert a
-- job with any action_type and action_payload with confirmation_at set and no
-- reason (bypassing JobRequest.validate_command and validate_payload), rewrite
-- a pending refresh_inventory job into restart or install_software, or
-- overwrite devices.credential_hash to mint a working device credential with no
-- enrollment token. None of those paths writes an audit row.
--
-- Fix
-- ---
-- 1. Drop the client-write policies. Every mutation already goes through the
--    API, which validates payloads, checks roles server-side, and appends a
--    hash-chained audit row in the same transaction.
-- 2. Revoke write privileges from anon/authenticated outright, so RLS is
--    defence in depth rather than the sole control. Adding a policy by mistake
--    can no longer grant write access on its own.
--
-- The API is unaffected: it connects as `postgres`, which owns these tables and
-- has rolbypassrls, so neither policies nor grants apply to it. The dashboard is
-- unaffected: it uses supabase-js only for auth (.auth.*) and never calls
-- .from()/.rpc(), reading all domain data through the API instead.

-- 1. Remove the client-write policies. Member/owner SELECT policies are kept.
drop policy if exists devices_admin_mutate on public.devices;
drop policy if exists jobs_admin_create on public.jobs;
drop policy if exists jobs_admin_cancel on public.jobs;
drop policy if exists compliance_policies_admin_mutate on public.compliance_policies;
drop policy if exists packages_admin_mutate on public.packages;
drop policy if exists approved_folders_owner_mutate on public.approved_folders;

-- 2. Revoke write privileges from the browser-facing roles on every table in
--    public, including tables added later by an unreviewed migration. SELECT is
--    left in place and remains scoped by the existing RLS read policies.
do $$
declare
  target record;
begin
  for target in
    select schemaname, tablename
    from pg_tables
    where schemaname = 'public'
  loop
    execute format(
      'revoke insert, update, delete, truncate, references, trigger on %I.%I from anon, authenticated',
      target.schemaname, target.tablename
    );
  end loop;
end
$$;

-- Stop the same default grants from reappearing on tables created later.
alter default privileges in schema public
  revoke insert, update, delete, truncate, references, trigger on tables from anon, authenticated;

-- Sequences: clients never need to advance one, because they never insert.
revoke usage, update on all sequences in schema public from anon, authenticated;

comment on table public.devices is
  'Device identity. Client roles have SELECT only (RLS-scoped); all writes go through the API, which audits them. See migration 0012.';
comment on table public.jobs is
  'Durable jobs. Client roles have SELECT only (RLS-scoped); action_type/action_payload validation and confirmation live in the API. See migration 0012.';
