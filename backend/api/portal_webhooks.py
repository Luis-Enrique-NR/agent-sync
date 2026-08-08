"""Portal webhook route: verify raw bytes first, then parse and enqueue."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse

from transport.bus import DurableEventBus
from transport.config import TransportSettings
from transport.portal import WebhookSecretProvider
from transport.webhooks import normalize_event, verify_portal_signature


def build_portal_webhook_router(
    settings: TransportSettings,
    secret_provider: WebhookSecretProvider,
    bus: DurableEventBus,
    clock: Callable[[], datetime],
) -> APIRouter:
    router = APIRouter()

    @router.post("/webhooks/portal")
    async def portal_webhook(request: Request) -> Response:
        raw_body = await request.body()
        secret = await secret_provider.get_secret()
        if secret is None:
            return JSONResponse(
                {"detail": "webhook secret unavailable"},
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if not verify_portal_signature(
            raw_body,
            request.headers.get("portal-signature"),
            secret,
            clock(),
            settings.portal_webhook_tolerance_seconds,
        ):
            return JSONResponse(
                {"detail": "invalid signature"},
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            return JSONResponse(
                {"detail": "malformed body"},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        try:
            envelope = normalize_event(payload)
        except ValueError as exc:
            return JSONResponse(
                {"detail": f"invalid event: {exc}"},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if envelope is None:
            return Response(status_code=status.HTTP_200_OK)
        try:
            await bus.accept(envelope)
        except Exception:
            return JSONResponse(
                {"detail": "durable bus unavailable"},
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(status_code=status.HTTP_200_OK)

    return router
