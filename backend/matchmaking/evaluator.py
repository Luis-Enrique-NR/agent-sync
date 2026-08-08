"""Bidirectional compatibility scoring for agent matchmaking.

Evaluates hard filters (price range conflicts, logistics incompatibility,
cooldown windows), then computes a 0.0–1.0 score based on tag intersection
and mutual fit.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlmodel import Session, select

from ai.domain.models import AgentProfile
from persistence.models import NegotiationStateRow

_CLOSED_STATES = {"REJECTED", "FAILED"}


def is_in_cooldown(
    agent_a_id: UUID,
    agent_b_id: UUID,
    *,
    session: Session,
    cooldown_minutes: int = 60,
) -> bool:
    """True if agents A and B had a closed session within the cooldown window."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=cooldown_minutes)
    stmt = select(NegotiationStateRow).where(
        NegotiationStateRow.status.in_(_CLOSED_STATES),
        NegotiationStateRow.closed_at >= cutoff,
    )
    closed = session.exec(stmt).all()
    for row in closed:
        participants = {row.agent_1_id, row.agent_2_id}
        if participants == {agent_a_id, agent_b_id}:
            return True
    return False


def price_ranges_conflict(a: AgentProfile, b: AgentProfile) -> bool:
    """True if A and B have mutually exclusive price ranges."""
    pr_a = a.price_range
    pr_b = b.price_range
    if pr_a is None or pr_b is None:
        return False  # No price info → no conflict
    a_min = pr_a.get("min", 0)
    a_max = pr_a.get("max", float("inf"))
    b_min = pr_b.get("min", 0)
    b_max = pr_b.get("max", float("inf"))
    # Conflict when ranges do not overlap
    return a_max < b_min or b_max < a_min


def logistics_score(a: AgentProfile, b: AgentProfile) -> float:
    """Jaccard-like score for shared logistics preferences."""
    set_a = set(a.logistics_preferences or [])
    set_b = set(b.logistics_preferences or [])
    if not set_a and not set_b:
        return 0.5  # Neutral — neither specified logistics
    if not set_a or not set_b:
        return 0.3  # One side has preferences, other doesn't
    intersection = set_a & set_b
    union = set_a | set_b
    if not union:
        return 0.5
    return len(intersection) / len(union)


def interests_capabilities_score(a: AgentProfile, b: AgentProfile) -> float:
    """How well A's interests match B's capabilities, and vice versa."""
    a_interests = set(a.interests or [])
    a_caps = set(a.capabilities or [])
    b_interests = set(b.interests or [])
    b_caps = set(b.capabilities or [])

    if not a_interests and not b_interests:
        return 0.0

    # A → B: A's interests found in B's capabilities
    a_to_b = len(a_interests & b_caps) / max(len(a_interests), 1)
    # B → A: B's interests found in A's capabilities
    b_to_a = len(b_interests & a_caps) / max(len(b_interests), 1)

    if a_to_b == 0.0 and b_to_a == 0.0:
        return 0.0

    # Average: at least one direction must match to get a positive score.
    # Both matching gives the highest score.
    return (a_to_b + b_to_a) / 2.0


def calculate_match_score(a: AgentProfile, b: AgentProfile) -> float:
    """Compute a 0.0–1.0 compatibility score between two agents.

    Returns 0.0 immediately if hard filters fail (price conflict).
    Combines interest-capability overlap with logistics preference
    similarity.
    """
    # Hard filter: price range conflict
    if price_ranges_conflict(a, b):
        return 0.0

    ic_score = interests_capabilities_score(a, b)
    if ic_score == 0.0:
        return 0.0  # No tag intersection → no match

    log_score = logistics_score(a, b)

    # Weighted combination: interests/capabilities dominate
    return 0.7 * ic_score + 0.3 * log_score
