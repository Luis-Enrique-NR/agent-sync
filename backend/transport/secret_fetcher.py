"""Concrete WebhookSecretFetcher — fetches and caches Portal webhook signing secret."""

from __future__ import annotations

import logging
import time

import httpx

from transport.portal import WebhookSecretProvider

logger = logging.getLogger(__name__)

_PORTAL_API_BASE = "https://api.useportal.co"
_SECRET_PATH = "/v1/webhooks/secret"


class WebhookSecretFetcher(WebhookSecretProvider):
    """Fetches the Portal webhook signing secret from the Portal API.

    Implements the ``WebhookSecretProvider`` protocol:
    - Lazy-init: first ``get_secret()`` triggers the HTTP fetch.
    - Caches the secret until explicitly invalidated.
    - On ``invalidate()``, applies a cooldown window during which the
      last known secret is returned (prevents hammering the Portal API).
      After the cooldown, the next ``get_secret()`` re-fetches.
    - On fetch failure, returns ``None`` (fail closed).
    """

    def __init__(
        self,
        secret_key: str,
        client: httpx.AsyncClient | None = None,
        *,
        cooldown_seconds: float = 60.0,
    ) -> None:
        self._secret_key = secret_key
        self._client = client
        self._owns_client = False
        self._cooldown = cooldown_seconds
        self._secret: str | None = None
        self._invalidated_at: float | None = None

    async def get_secret(self) -> str | None:
        if self._secret is not None:
            if self._invalidated_at is None:
                return self._secret
            # Cooldown active: return stale value, don't re-fetch yet
            elapsed = time.monotonic() - self._invalidated_at
            if elapsed < self._cooldown:
                return self._secret
            # Cooldown expired: clear stale and re-fetch below
            self._secret = None
            self._invalidated_at = None

        try:
            client: httpx.AsyncClient
            if self._client is not None:
                client = self._client
            else:
                client = httpx.AsyncClient(base_url=_PORTAL_API_BASE)
                self._owns_client = True

            url = _SECRET_PATH if self._owns_client else f"{_PORTAL_API_BASE}{_SECRET_PATH}"
            headers = {"Authorization": f"Bearer {self._secret_key}"}
            response = await client.get(url, headers=headers)

            if response.status_code != 200:
                logger.warning(
                    "WebhookSecretFetcher: Portal API returned %d — cannot fetch secret",
                    response.status_code,
                )
                return None

            payload = response.json()
            secret = payload.get("secret")
            if not isinstance(secret, str) or not secret:
                logger.warning(
                    "WebhookSecretFetcher: unexpected response shape %s", payload
                )
                return None

            self._secret = secret
            return self._secret

        except httpx.HTTPError:
            logger.exception("WebhookSecretFetcher: HTTP error fetching secret")
            return None
        finally:
            if self._owns_client:
                await client.aclose()
                self._owns_client = False

    def invalidate(self) -> None:
        """Mark the cached secret as invalid.

        The next ``get_secret()`` after the cooldown window will re-fetch
        from the Portal API.  Within the cooldown, the stale cached value
        is returned to prevent hammering the API.
        """
        if self._secret is not None:
            self._invalidated_at = time.monotonic()
            logger.info("WebhookSecretFetcher: cache invalidated (cooldown=%.1fs)", self._cooldown)
