"""Resilience tests — cooldown and re-match after failure."""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlmodel import Session

from ai.domain.models import AgentProfile, EntityType
from matchmaking.evaluator import is_in_cooldown
from matchmaking.service import find_matches
from persistence.database import init_db, get_session
from persistence.models import AgentProfileRow, NegotiationStateRow


@pytest.fixture(autouse=True)
def clean_db() -> None:
    init_db()
    session = get_session()
    for table in [AgentProfileRow, NegotiationStateRow]:
        session.exec(table.__table__.delete())  # type: ignore[attr-defined]
    session.commit()
    session.close()


def _create(
    session: Session,
    agent_id: UUID,
    name: str,
    *,
    interests: list[str] | None = None,
    capabilities: list[str] | None = None,
) -> AgentProfileRow:
    profile = AgentProfile(
        agent_id=agent_id,
        display_name=name,
        entity_type=EntityType.PERSON,
        public_description=f"test {name}",
        personality="test",
        objectives=["test"],
        interests=interests or [],
        capabilities=capabilities or [],
    )
    row = AgentProfileRow(
        agent_id=agent_id,
        user_id=uuid4(),
        display_name=name,
        entity_type="person",
        status="AVAILABLE",
        public_description=f"test {name}",
        interests=interests or [],
        capabilities=capabilities or [],
        raw_profile=profile.model_dump(mode="json"),
    )
    session.add(row)
    session.commit()
    return row


def _create_closed_session(
    session: Session,
    session_id: UUID,
    agent_1: UUID,
    agent_2: UUID,
    status: str = "FAILED",
    minutes_ago: int = 10,
) -> NegotiationStateRow:
    closed_at = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    row = NegotiationStateRow(
        session_id=session_id,
        agent_1_id=agent_1,
        agent_2_id=agent_2,
        initiator_id=agent_1,
        status=status,
        closed_at=closed_at,
        raw_state={"session_id": str(session_id), "status": status},
    )
    session.add(row)
    session.commit()
    return row


# ── Cooldown prevents recent failed match ────────────────────────────


def test_cooldown_prevents_recent_failed_match() -> None:
    session = get_session()
    buyer = _create(session, UUID("a1000000-0000-0000-0000-000000000001"), "Buyer",
                    interests=["buy_bike"], capabilities=["cash"])
    seller = _create(session, UUID("a1000000-0000-0000-0000-000000000002"), "Seller",
                     interests=["sell_bike"], capabilities=["buy_bike"])

    # Recent failed session (10 min ago)
    _create_closed_session(
        session, UUID("a1000000-0000-0000-0000-000000000100"),
        buyer.agent_id, seller.agent_id, status="FAILED", minutes_ago=10,
    )

    # Cooldown check
    assert is_in_cooldown(buyer.agent_id, seller.agent_id, session=session, cooldown_minutes=60)

    # They should NOT match
    matches = find_matches(buyer.agent_id, session=session)
    match_ids = {m.agent_id for m in matches}
    assert seller.agent_id not in match_ids, "cooldown should block recent failed pair"
    session.close()


def test_old_failed_does_not_trigger_cooldown() -> None:
    """A session older than the cooldown window should not block matching."""
    session = get_session()
    buyer = _create(session, UUID("a2000000-0000-0000-0000-000000000001"), "Buyer",
                    interests=["buy_bike"], capabilities=["cash"])
    seller = _create(session, UUID("a2000000-0000-0000-0000-000000000002"), "Seller",
                     interests=["sell_bike"], capabilities=["buy_bike"])

    # Old failed session (90 min ago)
    _create_closed_session(
        session, UUID("a2000000-0000-0000-0000-000000000100"),
        buyer.agent_id, seller.agent_id, status="FAILED", minutes_ago=90,
    )

    assert not is_in_cooldown(buyer.agent_id, seller.agent_id, session=session, cooldown_minutes=60)

    matches = find_matches(buyer.agent_id, session=session)
    match_ids = {m.agent_id for m in matches}
    assert seller.agent_id in match_ids, "old failure should not block match"
    session.close()


def test_cooldown_only_for_same_pair() -> None:
    """Cooldown between A-B does NOT affect A-C."""
    session = get_session()
    buyer = _create(session, UUID("a3000000-0000-0000-0000-000000000001"), "Buyer",
                    interests=["buy_bike"], capabilities=["cash"])
    bad_seller = _create(session, UUID("a3000000-0000-0000-0000-000000000002"), "BadSeller",
                         interests=["sell_bike"], capabilities=["buy_bike"])
    good_seller = _create(session, UUID("a3000000-0000-0000-0000-000000000003"), "GoodSeller",
                          interests=["sell_bike"], capabilities=["buy_bike"])

    _create_closed_session(
        session, UUID("a3000000-0000-0000-0000-000000000100"),
        buyer.agent_id, bad_seller.agent_id, status="FAILED", minutes_ago=10,
    )

    matches = find_matches(buyer.agent_id, session=session)
    match_ids = {m.agent_id for m in matches}
    assert bad_seller.agent_id not in match_ids, "cooldown blocks A-B"
    assert good_seller.agent_id in match_ids, "cooldown does NOT affect A-C"
    session.close()
