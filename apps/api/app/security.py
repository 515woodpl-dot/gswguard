from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from typing import Protocol

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cache-Control": "no-store",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response


class RateLimiter(Protocol):
    def allow(self, key: str, now: float) -> bool: ...


class InProcessSlidingWindowLimiter:
    """Small-instance abuse brake; not a cross-worker security control."""

    def __init__(self, requests_per_minute: int = 120):
        self.limit = requests_per_minute
        self._requests: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, now: float) -> bool:
        with self._lock:
            window = self._requests[key]
            while window and now - window[0] >= 60:
                window.popleft()
            if len(window) >= self.limit:
                return False
            window.append(now)
            return True


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply a replaceable limiter and resolve client identity safely."""

    def __init__(self, app, requests_per_minute: int = 120, trusted_proxy_hops: int = 0, limiter: RateLimiter | None = None):
        super().__init__(app)
        self.trusted_proxy_hops = trusted_proxy_hops
        self.limiter = limiter or InProcessSlidingWindowLimiter(requests_per_minute)

    def _client_key(self, request: Request) -> str:
        peer = request.client.host if request.client else "unknown"
        if self.trusted_proxy_hops <= 0:
            return peer
        forwarded = request.headers.get("x-forwarded-for", "")
        hops = [item.strip() for item in forwarded.split(",") if item.strip()]
        if not hops:
            return peer
        index = len(hops) - self.trusted_proxy_hops
        return peer if index < 0 else hops[index]

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path.endswith("/health/live"):
            return await call_next(request)
        if not self.limiter.allow(self._client_key(request), monotonic()):
            return JSONResponse(status_code=429, content={"error": "rate_limit_exceeded"})
        return await call_next(request)
