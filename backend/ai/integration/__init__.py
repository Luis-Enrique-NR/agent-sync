"""Stable seams used by EDA, Portal, and other integration adapters."""

from ai.integration.events import (
    IntegrationEventType,
    SUPPORTED_INTEGRATION_EVENTS,
)
from ai.integration.portal import (
    PortalMessageIntent,
    public_portal_messages,
    to_public_portal_message,
)

__all__ = [
    "IntegrationEventType",
    "SUPPORTED_INTEGRATION_EVENTS",
    "PortalMessageIntent",
    "public_portal_messages",
    "to_public_portal_message",
]
