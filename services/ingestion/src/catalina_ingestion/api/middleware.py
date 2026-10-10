import asyncio
import re
from collections import defaultdict, deque
from collections.abc import Callable
from time import monotonic
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import (
    BaseHTTPMiddleware,
)
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next,
    ) -> Response:
        request_id = request.headers.get("X-Request-ID")

        if not request_id:
            request_id = str(uuid4())

        response = await call_next(request)

        response.headers["X-Request-ID"] = request_id

        response.headers["X-Content-Type-Options"] = "nosniff"

        response.headers["X-Frame-Options"] = "DENY"

        response.headers["Referrer-Policy"] = "no-referrer"

        response.headers["Cache-Control"] = "no-store"

        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        window_seconds: int,
        login_limit: int,
        answers_limit: int,
        uploads_limit: int,
    ) -> None:
        super().__init__(app)

        self.window_seconds = window_seconds

        self.login_limit = login_limit
        self.answers_limit = answers_limit
        self.uploads_limit = uploads_limit

        self._requests: dict[
            tuple[str, str],
            deque[float],
        ] = defaultdict(deque)

        self._lock = asyncio.Lock()

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        rule = self._resolve_rule(request)

        if rule is None:
            return await call_next(request)

        bucket, limit = rule

        client_ip = request.client.host if request.client else "unknown"

        key = (
            bucket,
            client_ip,
        )

        now = monotonic()

        retry_after = await self._consume(
            key=key,
            now=now,
            limit=limit,
        )

        if retry_after is not None:
            request_id = request.headers.get("X-Request-ID") or str(uuid4())

            return JSONResponse(
                status_code=429,
                headers={
                    "X-Request-ID": request_id,
                    "Retry-After": str(retry_after),
                },
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": ("Se excedió el límite temporal de solicitudes."),
                        "retryable": True,
                        "request_id": request_id,
                    }
                },
            )

        return await call_next(request)

    async def _consume(
        self,
        *,
        key: tuple[str, str],
        now: float,
        limit: int,
    ) -> int | None:
        async with self._lock:
            history = self._requests[key]

            cutoff = now - self.window_seconds

            while history and history[0] <= cutoff:
                history.popleft()

            if len(history) >= limit:
                remaining = self.window_seconds - (now - history[0])

                return max(
                    1,
                    int(remaining) + 1,
                )

            history.append(now)

            return None

    def _resolve_rule(
        self,
        request: Request,
    ) -> tuple[str, int] | None:
        if request.method != "POST":
            return None

        path = request.url.path

        if path == "/api/v1/auth/login":
            return (
                "login",
                self.login_limit,
            )

        if path == "/api/v1/answers":
            return (
                "answers",
                self.answers_limit,
            )

        if path == ("/api/v1/admin/documents"):
            return (
                "uploads",
                self.uploads_limit,
            )

        if re.fullmatch(
            (
                r"/api/v1/admin/documents/"
                r"\d+/versions"
            ),
            path,
        ):
            return (
                "uploads",
                self.uploads_limit,
            )

        return None
