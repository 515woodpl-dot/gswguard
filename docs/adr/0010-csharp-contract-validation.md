# ADR 0010: C# contract validation strategy for the proof of concept

- Status: Accepted for Phase 1C proof of concept
- Date: 2026-07-24

## Context

The current macOS environment has no .NET SDK, and a stable OpenAPI C# generator is not yet selected. The contract strategy must still prove nullable/reference, enum, date-time, UUID, and JSON compatibility before the Windows agent is built.

## Decision

Use hand-written-looking but generator-emitted C# transport DTO fixtures for Phase 1C, with the Pydantic/OpenAPI source remaining authoritative. The generated C# file is never manually edited. JSON fixtures are the compatibility boundary and will be deserialized and tested on `windows-latest` once the agent project exists. A later generator may replace this output only through a superseding ADR after evaluating Kiota or NSwag for nullable reference types, required properties, enum mapping, date-time, UUID, and regeneration stability.

## Consequences

The proof is deterministic and does not block on unavailable .NET tooling. It does not claim C# compilation yet. Phase 1B must add Windows CI serialization tests, and any production C# generator choice must include drift detection and a documented version.
