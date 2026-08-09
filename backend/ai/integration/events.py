"""Canonical event names exchanged by Portal, EDA, and the AI engine."""

from enum import StrEnum


class IntegrationEventType(StrEnum):
    MESSAGE_PUBLISHED = "message.published"
    MESSAGE_RETRACTED = "message.retracted"
    AGENT_REGISTERED = "agent.registered"
    INTENT_PUBLISHED = "intent.published"
    NEGOTIATION_FAILED = "negotiation.failed"
    NEGOTIATION_REJECTED = "negotiation.rejected"


SUPPORTED_INTEGRATION_EVENTS = frozenset(item.value for item in IntegrationEventType)

__all__ = ["IntegrationEventType", "SUPPORTED_INTEGRATION_EVENTS"]
