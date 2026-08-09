"""Verification tests for seed_demo_data.py — validates seeded entities."""

from uuid import UUID

import pytest
from sqlmodel import select

from persistence.database import init_db, get_session
from persistence.models import AgentProfileRow, NegotiationStateRow, AuditRecordRow
from ai.domain.models import NegotiationState, SessionStatus


@pytest.fixture(autouse=True)
def run_seed() -> None:
    """Run seeder before each test — idempotent by design."""
    init_db()
    from scripts.seed_demo_data import seed
    session = get_session()
    seed(session)
    session.close()


def test_b2b_vendor_profile_created() -> None:
    s = get_session()
    row = s.get(AgentProfileRow, UUID("b0000000-0000-0000-0000-000000000001"))
    assert row is not None
    assert row.display_name == "Agente Ventas SaaS TechCorp"
    assert row.entity_type == "company"
    assert "enterprise_saas" in row.interests
    s.close()


def test_p2p_seller_profile_created() -> None:
    s = get_session()
    row = s.get(AgentProfileRow, UUID("b0000000-0000-0000-0000-000000000002"))
    assert row is not None
    assert row.display_name == "Agente Venta Laptop Usada"
    assert row.entity_type == "person"
    assert "sell_laptop" in row.interests
    s.close()


def test_active_negotiation_has_transcript() -> None:
    s = get_session()
    row = s.get(NegotiationStateRow, UUID("c0000000-0000-0000-0000-000000000001"))
    assert row is not None
    assert row.status == SessionStatus.ACTIVE.value
    state = NegotiationState.model_validate(row.raw_state)
    assert len(state.transcript) >= 4
    assert state.turn_count == 4
    s.close()


def test_pending_negotiation_has_decision() -> None:
    s = get_session()
    row = s.get(NegotiationStateRow, UUID("c0000000-0000-0000-0000-000000000002"))
    assert row is not None
    assert row.status == SessionStatus.PENDING_HUMAN_APPROVAL.value
    state = NegotiationState.model_validate(row.raw_state)
    assert state.pending_decision is not None
    assert len(state.transcript) >= 3
    s.close()


def test_audit_records_exist() -> None:
    s = get_session()
    records = s.exec(select(AuditRecordRow)).all()
    assert len(records) >= 2
    actions = {r.action for r in records}
    assert "SESSION_CREATED" in actions
    assert "APPROVAL_REQUESTED" in actions
    s.close()


def test_seed_is_idempotent() -> None:
    """Running seed twice should not produce duplicates."""
    from scripts.seed_demo_data import seed
    s = get_session()
    # Count before
    agents_before = len(s.exec(select(AgentProfileRow)).all())
    # Seed again
    seed(s)
    # Count after
    agents_after = len(s.exec(select(AgentProfileRow)).all())
    assert agents_after == agents_before, f"{agents_before} -> {agents_after}"
    s.close()
