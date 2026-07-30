-- Keep audit actors immutable. Audit finding H6 (docs/audit-2026-07-29.md).
--
-- Problem
-- -------
-- audit_log.actor_user_id (0001) and audit_log.actor_device_id (0011) were
-- declared ON DELETE SET NULL, but audit_log_immutable (0001) is a
-- BEFORE UPDATE OR DELETE trigger that raises unconditionally. Deleting the
-- referenced row makes the foreign key issue an UPDATE against audit_log, which
-- fires the trigger. Reproduced on the live database:
--
--   delete from public.devices where id = <device with an audit row>;
--   ERROR:  audit_log is append-only
--
-- So any device or Supabase auth user that had ever emitted an audit event
-- could no longer be deleted, which blocks device decommissioning, re-enrolment
-- after a serial-number collision, and user offboarding.
--
-- Fix
-- ---
-- Drop the cascading foreign keys and keep the columns as plain uuid. This is
-- also the semantically correct choice for an audit log: the record of *who*
-- acted must survive the deletion of the actor, and nulling it would rewrite
-- history and break the hash chain, since actor_user_id/actor_device_id are
-- both part of the hashed payload in append_audit_in_transaction.
--
-- Referential integrity is not lost in practice: both columns are written only
-- by append_audit_in_transaction, from an id it has just read or inserted
-- inside the same transaction. Readers must treat an actor id with no matching
-- row as "actor since deleted" rather than assuming a dangling write.

alter table public.audit_log
  drop constraint if exists audit_log_actor_user_id_fkey;

alter table public.audit_log
  drop constraint if exists audit_log_actor_device_id_fkey;

comment on column public.audit_log.actor_user_id is
  'Supabase auth user that acted. Intentionally not a foreign key: the audit record outlives the actor. May reference a deleted user. See migration 0013.';

comment on column public.audit_log.actor_device_id is
  'Device that acted. Intentionally not a foreign key: the audit record outlives the actor. May reference a deleted device. See migration 0013.';
