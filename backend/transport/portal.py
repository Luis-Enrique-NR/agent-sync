"""Server-side webhook secret seam."""

from __future__ import annotations

from typing import Protocol

class WebhookSecretProvider(Protocol):
    async def get_secret(self) -> str | None:
        """Return a server-side secret, or None to fail closed."""
