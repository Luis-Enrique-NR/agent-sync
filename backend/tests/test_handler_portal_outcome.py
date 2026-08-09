"""Tests for NegotiationHandler PortalOutcome decision logic.

RED phase: tests reference production code that does not exist yet.
"""

from __future__ import annotations

import pytest

from eda.handlers import _decide_outcome_action  # RED: doesn't exist yet
from transport.portal import (
    PortalRejected,
    PortalRetryable,
    PortalUncertain,
    PublishedMessage,
)


def test_published_message_should_ack_normally() -> None:
    """PublishedMessage → handler continues without re-raise → bus.ack()."""
    outcome = PublishedMessage(id="msg_1", seq=1, timestamp=123)
    assert _decide_outcome_action(outcome) == "ack"


def test_portal_retryable_rate_limited_should_fail() -> None:
    """PortalRetryable (rate_limited) → re-raise → bus.fail()."""
    outcome = PortalRetryable(code="rate_limited")
    assert _decide_outcome_action(outcome) == "fail"


def test_portal_retryable_transient_should_fail() -> None:
    """PortalRetryable (transient) → re-raise → bus.fail()."""
    outcome = PortalRetryable(code="transient")
    assert _decide_outcome_action(outcome) == "fail"


def test_portal_uncertain_timeout_should_fail() -> None:
    """PortalUncertain (timeout) → re-raise → bus.fail()."""
    outcome = PortalUncertain()
    assert _decide_outcome_action(outcome) == "fail"


def test_portal_rejected_should_ack_silently() -> None:
    """PortalRejected (non-transient) → log + continue → bus.ack()."""
    outcome = PortalRejected(code="forbidden", reason="not allowed")
    assert _decide_outcome_action(outcome) == "ack"


def test_portal_rejected_no_reason_should_ack_silently() -> None:
    """PortalRejected without reason → still ack (non-transient)."""
    outcome = PortalRejected(code="unknown")
    assert _decide_outcome_action(outcome) == "ack"
