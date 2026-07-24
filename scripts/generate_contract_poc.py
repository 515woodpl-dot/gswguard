"""Generate and check the Phase 1C contract proof-of-concept artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.contracts.poc.source import ApiError, HealthResponse  # noqa: E402


OUTPUTS = {
    "openapi": ROOT / "packages/contracts/generated/openapi.json",
    "typescript": ROOT / "packages/contracts/generated/typescript/health.ts",
    "csharp": ROOT / "packages/contracts/generated/csharp/HealthContracts.cs",
    "health_fixture": ROOT / "packages/contracts/fixtures/health-response.json",
    "error_fixture": ROOT / "packages/contracts/fixtures/api-error.json",
}


def schema(model: type[Any]) -> dict[str, Any]:
    return model.model_json_schema(mode="serialization", ref_template="#/components/schemas/{model}")


def build_openapi() -> dict[str, Any]:
    health = schema(HealthResponse)
    error = schema(ApiError)
    definitions = {**health.pop("$defs", {}), **error.pop("$defs", {})}
    return {
        "openapi": "3.1.0",
        "info": {"title": "GSWGuard API contract POC", "version": "0.1.0"},
        "paths": {
            "/api/v1/health/live": {
                "get": {"responses": {"200": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/HealthResponse"}}}}}}
            },
            "/api/v1/health/ready": {
                "get": {"responses": {"200": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/HealthResponse"}}}}}}
            },
        },
        "components": {
            "schemas": {"HealthResponse": health, "ApiError": error, **definitions},
        },
    }


def render_typescript() -> str:
    return """// GENERATED FILE. DO NOT EDIT. Source: packages/contracts/poc/source.py
export type HealthStatus = 'healthy' | 'degraded';

export interface HealthResponse {
  status: HealthStatus;
  service: string;
  version: string;
  checked_at: string;
  request_id: string;
  detail?: string | null;
}

export interface ApiError {
  code: string;
  message: string;
  request_id: string;
  details?: Record<string, unknown> | null;
}
"""


def render_csharp() -> str:
    return """// GENERATED-FIXTURE DTO. DO NOT EDIT. Source: packages/contracts/poc/source.py
#nullable enable
using System;
using System.Collections.Generic;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace GswGuard.Contracts;

public enum HealthStatus
{
    [JsonPropertyName("healthy")] Healthy,
    [JsonPropertyName("degraded")] Degraded
}

public sealed record HealthResponse(
    HealthStatus Status,
    string Service,
    string Version,
    DateTimeOffset CheckedAt,
    Guid RequestId,
    string? Detail);

public sealed record ApiError(
    string Code,
    string Message,
    Guid RequestId,
    Dictionary<string, JsonElement>? Details);
"""


def outputs() -> dict[Path, str]:
    health_fixture = HealthResponse(
        status="healthy",
        service="gswguard-api",
        version="0.1.0",
        checked_at="2026-07-24T12:00:00Z",
        request_id="00000000-0000-0000-0000-000000000001",
    )
    error_fixture = ApiError(
        code="device_offline",
        message="The device is offline.",
        request_id="00000000-0000-0000-0000-000000000002",
    )
    return {
        OUTPUTS["openapi"]: json.dumps(build_openapi(), indent=2, sort_keys=True) + "\n",
        OUTPUTS["typescript"]: render_typescript(),
        OUTPUTS["csharp"]: render_csharp(),
        OUTPUTS["health_fixture"]: health_fixture.model_dump_json(indent=2) + "\n",
        OUTPUTS["error_fixture"]: error_fixture.model_dump_json(indent=2) + "\n",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    mismatches = []
    for path, expected in outputs().items():
        actual = path.read_text() if path.exists() else None
        if args.check:
            if actual != expected:
                mismatches.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(expected)
    if mismatches:
        print("Contract artifacts are stale:")
        print("\n".join(f"- {path}" for path in mismatches))
        return 1
    if not args.check:
        print("Generated contract POC artifacts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
