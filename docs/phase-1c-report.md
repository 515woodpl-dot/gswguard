# Phase 1C report — shared contracts proof of concept

## Implemented

- Added a small Pydantic contract source for `HealthResponse`, `ApiError`, and `HealthStatus`.
- Generated an OpenAPI 3.1 document with `/api/v1/health/live` and `/api/v1/health/ready` response schemas.
- Generated TypeScript types and C# transport DTO fixtures.
- Added JSON fixtures covering enum, required fields, optional/nullable fields, UUIDs, and date-time values.
- Added regeneration drift checking through `npm run contracts:check`.
- Added a dependency-free Python compatibility runner through `npm run contracts:test`.
- Recorded the Phase 1C C# strategy in [ADR 0010](adr/0010-csharp-contract-validation.md).

## Source and generated files

- Source: `packages/contracts/poc/source.py`
- Generator: `scripts/generate_contract_poc.py`
- OpenAPI: `packages/contracts/generated/openapi.json`
- TypeScript: `packages/contracts/generated/typescript/health.ts`
- C#: `packages/contracts/generated/csharp/HealthContracts.cs`
- Fixtures: `packages/contracts/fixtures/`

Generated contract artifacts are committed and are never manually edited. CI can regenerate and fail on drift.

## Validation

- `python3 scripts/generate_contract_poc.py --check` — passed.
- `npm run contracts:test` — passed.
- `python3 -m json.tool packages/contracts/generated/openapi.json` — passed.
- `npm run validate` — passed.
- `node --check scripts/validate-docs.mjs` — passed.

## Environment limitations

- FastAPI is not installed locally, so this POC uses Pydantic schema output. Phase 1B must revalidate the contract against the FastAPI-generated OpenAPI document before health endpoints depend on it.
- .NET is not installed locally, so C# compilation and serialization execution were not performed. Windows CI must compile and deserialize the fixtures in Phase 1B.
- `pytest` is not installed locally; the dependency-free compatibility runner was used instead.

## Deferred decisions

- Final FastAPI/OpenAPI generator versions and TypeScript client generator: Phase 1B contract integration.
- Kiota/NSwag versus the accepted C# fixture strategy: after Windows CI evaluates maintainability.
- API breaking-change/versioning policy beyond the initial `/api/v1/` boundary: before the first production API release.

## Review gate

Stop after Phase 1C. Explicit owner approval is required before Phase 1B creates the dashboard, API, or Windows-agent skeletons.
