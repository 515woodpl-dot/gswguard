# ADR 0002: HTTP contracts source of truth

- Status: Proposed
- Date: 2026-07-24

## Context

The dashboard, API, and agent must agree on request, response, error, UUID, enum, nullable, and date-time representations. Independently hand-maintained DTOs would drift.

## Decision

Use FastAPI Pydantic models as the source for HTTP transport schemas. FastAPI generates OpenAPI; a pinned generator produces TypeScript types/client code under `packages/contracts/generated/typescript/`. C# generation is evaluated in Phase 1C. If generated C# is unstable or misleading, use hand-written transport DTOs with fixtures generated from OpenAPI and compatibility tests, documented by a superseding ADR or an amendment to this proposed decision before acceptance.

Generated code is never manually edited. CI regenerates and fails on a diff. Domain models remain separate from transport models. HTTP routes are versioned under `/api/v1/`; breaking changes require a new version or explicit compatibility decision.

## Mapping rules

OpenAPI `date-time` maps to timezone-aware Python `datetime`, TypeScript `string` with generated format metadata, and C# `DateTimeOffset`. UUID maps to Python `UUID`, TypeScript `string` with generated format metadata, and C# `Guid`. Optional means omitted; nullable means explicitly `null`; requiredness comes from the schema. Enums are string enums unless a generator limitation is documented.

## Consequences

The API owns schema generation and contract drift is testable. Generator versions and commands must be pinned during Phase 1C; no permanent generated-code paths are created in Phase 0A.
