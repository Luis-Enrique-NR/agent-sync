"""Minimal bearer authentication for a private, first-party MCP endpoint."""

from __future__ import annotations

import hmac
import os
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class BearerTokenMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, token_env: str | None, environ: dict[str, str] | None = None) -> None:
        super().__init__(app)
        self._token_env = token_env
        self._environ = os.environ if environ is None else environ

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if request.url.path == "/health" or not self._token_env:
            return await call_next(request)
        expected = self._environ.get(self._token_env)
        if not expected:
            return JSONResponse({"error": "MCP_AUTH_TOKEN_NOT_CONFIGURED"}, status_code=503)
        authorization = request.headers.get("authorization", "")
        scheme, _, provided = authorization.partition(" ")
        if scheme.lower() != "bearer" or not provided or not hmac.compare_digest(provided, expected):
            return JSONResponse({"error": "MCP_UNAUTHORIZED"}, status_code=401)
        return await call_next(request)
