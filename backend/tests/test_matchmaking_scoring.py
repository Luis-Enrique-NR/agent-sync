"""TDD suite for matchmaking scoring and ranking."""

from uuid import UUID, uuid4

import pytest
from sqlmodel import Session

from ai.domain.models import AgentProfile, EntityType
from matchmaking.evaluator import (
    calculate_match_score,
    price_ranges_conflict,
)
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
    status: str = "AVAILABLE",
    interests: list[str] | None = None,
    capabilities: list[str] | None = None,
    price_range: dict | None = None,
    logistics: list[str] | None = None,
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
        status=status,  # type: ignore[arg-type]
        price_range=price_range,
        logistics_preferences=logistics or [],
    )
    row = AgentProfileRow(
        agent_id=agent_id,
        user_id=uuid4(),
        display_name=name,
        entity_type="person",
        status=status,
        public_description=f"test {name}",
        interests=interests or [],
        capabilities=capabilities or [],
        raw_profile=profile.model_dump(mode="json"),
    )
    session.add(row)
    session.commit()
    return row


# ── Price conflict ──────────────────────────────────────────────────────


def test_price_mismatch_returns_zero_score() -> None:
    """Agents with non-overlapping price ranges score 0."""
    a = AgentProfile(
        display_name="Buyer", entity_type=EntityType.PERSON,
        public_description="t", personality="t", objectives=["t"],
        interests=["buy_bike"], capabilities=["cash"],
        price_range={"min": 100, "max": 200},
    )
    b = AgentProfile(
        display_name="Seller", entity_type=EntityType.PERSON,
        public_description="t", personality="t", objectives=["t"],
        interests=["sell_bike"], capabilities=["buy_bike"],
        price_range={"min": 300, "max": 500},
    )
    assert price_ranges_conflict(a, b) is True
    assert calculate_match_score(a, b) == 0.0


def test_no_price_info_allows_match() -> None:
    """Agents without price ranges should not be penalized."""
    a = AgentProfile(
        display_name="A", entity_type=EntityType.PERSON,
        public_description="t", personality="t", objectives=["t"],
        interests=["buy_bike"], capabilities=["cash"],
    )
    b = AgentProfile(
        display_name="B", entity_type=EntityType.PERSON,
        public_description="t", personality="t", objectives=["t"],
        interests=["sell_bike"], capabilities=["buy_bike", "sell_bike"],
    )
    assert price_ranges_conflict(a, b) is False
    assert calculate_match_score(a, b) > 0.0


def test_overlapping_price_ranges_not_conflict() -> None:
    """Overlapping ranges allow the match."""
    a = AgentProfile(
        display_name="Buyer", entity_type=EntityType.PERSON,
        public_description="t", personality="t", objectives=["t"],
        interests=["buy_bike"], capabilities=["cash"],
        price_range={"min": 100, "max": 400},
    )
    b = AgentProfile(
        display_name="Seller", entity_type=EntityType.PERSON,
        public_description="t", personality="t", objectives=["t"],
        interests=["sell_bike"], capabilities=["buy_bike"],
        price_range={"min": 300, "max": 500},
    )
    assert price_ranges_conflict(a, b) is False


# ── Ranking ─────────────────────────────────────────────────────────────


def test_candidates_ranked_by_score() -> None:
    """Agent with higher logistics overlap ranks first."""
    session = get_session()

    buyer = _create(
        session, UUID("e0000000-0000-0000-0000-000000000001"),
        "Buyer",
        interests=["buy_bike"],
        capabilities=["cash"],
        logistics=["weekend", "cash_payment", "public_meeting"],
    )
    # Seller A: fewer logistics matches
    _create(
        session, UUID("e0000000-0000-0000-0000-000000000002"),
        "SellerLow",
        interests=["sell_bike"],
        capabilities=["buy_bike"],
        logistics=["weekend"],
    )
    # Seller B: more logistics matches → should rank higher
    seller_high = _create(
        session, UUID("e0000000-0000-0000-0000-000000000003"),
        "SellerHigh",
        interests=["sell_bike"],
        capabilities=["buy_bike"],
        logistics=["weekend", "cash_payment", "public_meeting"],
    )

    matches = find_matches(buyer.agent_id, session=session)
    session.close()

    assert len(matches) >= 2
    # SellerHigh should be first (higher logistics overlap with buyer)
    assert matches[0].agent_id == seller_high.agent_id


def test_price_filter_excludes_in_range() -> None:
    """Agents excluded by price filter don't appear in matches."""
    session = get_session()

    buyer = _create(
        session, UUID("f0000000-0000-0000-0000-000000000001"),
        "Buyer",
        interests=["buy_bike"],
        capabilities=["cash"],
        price_range={"min": 100, "max": 200},
    )
    # Seller out of buyer's range
    _create(
        session, UUID("f0000000-0000-0000-0000-000000000002"),
        "ExpensiveSeller",
        interests=["sell_bike"],
        capabilities=["buy_bike"],
        price_range={"min": 500, "max": 800},
    )
    # Seller within range
    good = _create(
        session, UUID("f0000000-0000-0000-0000-000000000003"),
        "GoodSeller",
        interests=["sell_bike"],
        capabilities=["buy_bike"],
        price_range={"min": 50, "max": 250},
    )

    matches = find_matches(buyer.agent_id, session=session)
    session.close()

    match_ids = {m.agent_id for m in matches}
    assert good.agent_id in match_ids
    assert len(matches) == 1, f"expected 1 match, got {len(matches)}"
