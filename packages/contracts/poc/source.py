"""Phase 1C transport-contract source.

This deliberately small Pydantic model is the temporary source used to prove
schema, fixture, TypeScript, and C# compatibility before the FastAPI app exists.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class HealthStatus(StrEnum):
    healthy = "healthy"
    degraded = "degraded"


class ApiError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=500)
    request_id: UUID
    details: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: HealthStatus
    service: str = Field(min_length=1, max_length=80)
    version: str = Field(min_length=1, max_length=40)
    checked_at: datetime
    request_id: UUID
    detail: str | None = None
