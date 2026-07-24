// GENERATED-FIXTURE DTO. DO NOT EDIT. Source: packages/contracts/poc/source.py
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
