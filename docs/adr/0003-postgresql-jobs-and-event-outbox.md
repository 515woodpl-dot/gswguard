# ADR 0003: PostgreSQL-backed jobs and transactional event outbox

- Status: Proposed
- Date: 2026-07-24

## Context

The initial fleet is two Windows devices, growing potentially to four. A mandatory Redis or external broker adds cost and operational surface without being necessary for this scale. Important state changes still need reliable event publication and retryable work.

## Decision

Use Supabase PostgreSQL as the durable source of truth. Create a jobs table and claim work atomically with a lease using a short transaction and row locking (`FOR UPDATE SKIP LOCKED` where appropriate). Jobs contain organization/device scope, typed versioned action, idempotency key, expiration, attempt/lease timestamps, and sanitized result/error fields. A transactional `event_outbox` row is written in the same transaction as the domain mutation. A worker polls pending outbox rows, dispatches through an internal provider interface, records attempts, and retries with bounded backoff. Consumers use event IDs for idempotency.

The API remains a modular monolith. Provider interfaces isolate future Redis/queue, email, storage, and event-dispatch implementations. Default job expiry is configurable and initially 24 hours; sensitive actions may override it. Agent polling is the required transport; no broker is required between API and agent.

## Consequences

The design is inexpensive, transactional, inspectable, and sufficient for the expected fleet. Polling and database contention must be measured before scaling. Redis remains a deferred option, not a hidden dependency. Queue schema, lease behavior, retries, and failure recovery are validated in Phase 6.
