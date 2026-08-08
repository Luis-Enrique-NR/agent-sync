"""Validated environment settings for the transport layer."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TransportSettings:
    """Server-side transport configuration read from environment variables."""

    portal_webhook_tolerance_seconds: int

    @classmethod
    def from_env(cls) -> "TransportSettings":
        raw = os.getenv("PORTAL_WEBHOOK_TOLERANCE_SECONDS", "300")
        try:
            tolerance = int(raw)
        except ValueError as exc:
            raise ValueError(
                "PORTAL_WEBHOOK_TOLERANCE_SECONDS must be an integer"
            ) from exc
        if tolerance <= 0:
            raise ValueError(
                "PORTAL_WEBHOOK_TOLERANCE_SECONDS must be greater than zero"
            )
        return cls(portal_webhook_tolerance_seconds=tolerance)
