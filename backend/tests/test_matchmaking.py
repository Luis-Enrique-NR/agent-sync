"""TDD suite for the matchmaking engine."""

from uuid import UUID, uuid4

import pytest
from sqlmodel import Session, select

from ai.domain.models import AgentProfile, EntityType
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


def _create_agent(
    session: Session,
    agent_id: UUID,
    name: str,
    entity: str = "person",
    status: str = "AVAILABLE",
    interests: list[str] | None = None,
    capabilities: list[str] | None = None,
) -> AgentProfileRow:
    profile = AgentProfile(
        agent_id=agent_id,
        display_name=name,
        entity_type=EntityType(entity),
        public_description=f"test {name}",
        personality="test",
        objectives=["test"],
        interests=interests or [],
        capabilities=capabilities or [],
        status=status,  # type: ignore[arg-type]
    )
    row = AgentProfileRow(
        agent_id=agent_id,
        user_id=uuid4(),
        display_name=name,
        entity_type=entity,
        status=status,
        public_description=f"test {name}",
        interests=interests or [],
        capabilities=capabilities or [],
        raw_profile=profile.model_dump(mode="json"),
    )
    session.add(row)
    session.commit()
    return row


def _create_session(
    session: Session,
    session_id: UUID,
    agent_1: UUID,
    agent_2: UUID,
    status: str = "ACTIVE",
) -> NegotiationStateRow:
    row = NegotiationStateRow(
        session_id=session_id,
        agent_1_id=agent_1,
        agent_2_id=agent_2,
        initiator_id=agent_1,
        status=status,
        raw_state={"session_id": str(session_id), "status": status},
    )
    session.add(row)
    session.commit()
    return row


# ── CASE 1: exact tag match ────────────────────────────────────────────


def test_exact_tag_match() -> None:
    session = get_session()
    buyer = _create_agent(
        session, UUID("a0000000-0000-0000-0000-000000000001"),
        "Buyer", interests=["buy_used_bicycle", "urban_transport"],
        capabilities=["cash_payment"],
    )
    seller = _create_agent(
        session, UUID("a0000000-0000-0000-0000-000000000002"),
        "Seller", interests=["sell_used_bicycle"],
        capabilities=["sell_bicycle", "weekend_availability", "buy_used_bicycle"],
    )
    _create_agent(
        session, UUID("a0000000-0000-0000-0000-000000000003"),
        "Unrelated", interests=["find_roomie"],
        capabilities=["has_spare_room"],
    )

    matches = find_matches(buyer.agent_id, session=session)
    session.close()

    match_ids = {m.agent_id for m in matches}
    assert seller.agent_id in match_ids, f"seller {seller.agent_id} should match"
    assert len(matches) == 1, f"expected 1 match, got {len(matches)}"


# ── CASE 2: ignore BUSY/PAUSED agents ─────────────────────────────────


def test_ignore_busy_agents() -> None:
    session = get_session()
    buyer = _create_agent(
        session, UUID("b0000000-0000-0000-0000-000000000001"),
        "Buyer", interests=["buy_used_bicycle"],
    )
    _create_agent(
        session, UUID("b0000000-0000-0000-0000-000000000002"),
        "BusySeller", status="BUSY",
        capabilities=["buy_used_bicycle"],
    )
    _create_agent(
        session, UUID("b0000000-0000-0000-0000-000000000003"),
        "PausedSeller", status="PAUSED",
        capabilities=["buy_used_bicycle"],
    )
    available_seller = _create_agent(
        session, UUID("b0000000-0000-0000-0000-000000000004"),
        "AvailableSeller", status="AVAILABLE",
        capabilities=["buy_used_bicycle"],
    )

    matches = find_matches(buyer.agent_id, session=session)
    session.close()

    match_ids = {m.agent_id for m in matches}
    assert len(matches) == 1
    assert available_seller.agent_id in match_ids


# ── CASE 3: prevent duplicate negotiations ─────────────────────────────


def test_prevent_duplicate_negotiations() -> None:
    session = get_session()
    buyer = _create_agent(
        session, UUID("c0000000-0000-0000-0000-000000000001"),
        "Buyer", interests=["buy_used_bicycle"],
    )
    seller_active = _create_agent(
        session, UUID("c0000000-0000-0000-0000-000000000002"),
        "ActiveSeller", capabilities=["buy_used_bicycle"],
    )
    seller_free = _create_agent(
        session, UUID("c0000000-0000-0000-0000-000000000003"),
        "FreeSeller", capabilities=["buy_used_bicycle"],
    )
    # Existing active session between buyer and seller_active
    _create_session(
        session, UUID("c0000000-0000-0000-0000-000000000100"),
        buyer.agent_id, seller_active.agent_id, status="ACTIVE",
    )

    matches = find_matches(buyer.agent_id, session=session)
    session.close()

    match_ids = {m.agent_id for m in matches}
    assert seller_active.agent_id not in match_ids, "active negotiation should exclude seller"
    assert seller_free.agent_id in match_ids, "free seller should still match"
    assert len(matches) == 1


# ── CASE 4: candidate not available ───────────────────────────────────


def test_candidate_not_available_returns_empty() -> None:
    session = get_session()
    buyer = _create_agent(
        session, UUID("d0000000-0000-0000-0000-000000000001"),
        "Buyer", status="BUSY", interests=["buy_used_bicycle"],
    )
    _create_agent(
        session, UUID("d0000000-0000-0000-0000-000000000002"),
        "Seller", capabilities=["buy_used_bicycle"],
    )

    matches = find_matches(buyer.agent_id, session=session)
    session.close()

    assert matches == []


# ── CASE 5: empty interests → no matches ──────────────────────────────


def test_empty_interests_returns_empty() -> None:
    session = get_session()
    buyer = _create_agent(
        session, UUID("e0000000-0000-0000-0000-000000000001"),
        "Buyer", interests=[],
    )
    _create_agent(
        session, UUID("e0000000-0000-0000-0000-000000000002"),
        "Seller", capabilities=["buy_used_bicycle"],
    )

    matches = find_matches(buyer.agent_id, session=session)
    session.close()

    assert matches == []
