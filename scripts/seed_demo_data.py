"""Idempotent demo data seeder for Anthony's frontend development.

Usage:  python scripts/seed_demo_data.py

Populates the database with pre-built agent profiles, active negotiations
with transcripts, and a pending human approval session.  Safe to run
multiple times — existing rows are deleted first, then re-created.
"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID, uuid4

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from ai.domain.models import (
    AgentProfile, AgentStatus, AgentTurn, AuditAction,
    DecisionKind, DecisionReason, DecisionRequest,
    EntityType, NegotiationState, SessionStatus,
    TranscriptMessage, TurnIntent,
)
from persistence.database import init_db, get_session
from persistence.models import AgentProfileRow, NegotiationStateRow, AuditRecordRow
from persistence.repository import create_agent_profile, write_audit
from sqlmodel import select, delete


def seed(session):
    """Seed all demo entities.  Existing data is cleared first."""
    # Clean slate
    for table in [AuditRecordRow, NegotiationStateRow, AgentProfileRow]:
        session.exec(delete(table))
    session.commit()
    print("[SEED] Cleared existing data")

    # ── Agent 1: B2B Vendor ──────────────────────────────────────────
    b2b_id = UUID("b0000000-0000-0000-0000-000000000001")
    b2b = AgentProfile(
        agent_id=b2b_id,
        display_name="Agente Ventas SaaS TechCorp",
        entity_type=EntityType.COMPANY,
        public_description="Proveedor enterprise de software SaaS con descuentos por volumen.",
        personality="Negociador corporativo firme pero abierto a descuentos por volumen.",
        objectives=["Cerrar contratos enterprise", "Mantener margen sobre 15%"],
        hard_limits=[{"key": "min_price", "operator": "gte", "value": 5000, "unit": "USD"}],
        never_disclose={"PHONE", "EMAIL"},
        escalation_rules=[
            {"rule_id": "r1", "rule_type": "ANY_FINAL_PRICE", "enabled": True, "categories": []},
        ],
        interests=["enterprise_saas", "bulk_deals"],
        capabilities=["saas_platform", "volume_discount", "api_access"],
        status=AgentStatus.AVAILABLE,
    )
    create_agent_profile(b2b, user_id=uuid4(), session=session)
    print(f"[SEED] Created B2B Vendor: {b2b.display_name} ({b2b_id})")

    # ── Agent 2: P2P Seller ─────────────────────────────────────────
    p2p_id = UUID("b0000000-0000-0000-0000-000000000002")
    p2p = AgentProfile(
        agent_id=p2p_id,
        display_name="Agente Venta Laptop Usada",
        entity_type=EntityType.PERSON,
        public_description="Vendedor de MacBook Pro 2022 en buen estado.",
        personality="Vendedor amigable buscando vender rapido.",
        objectives=["Vender laptop sobre $800 USD"],
        hard_limits=[{"key": "min_price", "operator": "gte", "value": 800, "unit": "USD"}],
        never_disclose={"EXACT_ADDRESS", "PHONE"},
        escalation_rules=[
            {"rule_id": "r2", "rule_type": "AMOUNT_ABOVE", "key": "price", "threshold": 800, "enabled": True, "categories": []},
        ],
        interests=["sell_laptop", "quick_sale"],
        capabilities=["sell_electronics", "weekend_delivery"],
        status=AgentStatus.AVAILABLE,
    )
    create_agent_profile(p2p, user_id=uuid4(), session=session)
    print(f"[SEED] Created P2P Seller: {p2p.display_name} ({p2p_id})")

    # ── Agent 3: B2B Buyer (counterpart for negotiation) ────────────
    buyer_id = UUID("b0000000-0000-0000-0000-000000000003")
    buyer = AgentProfile(
        agent_id=buyer_id,
        display_name="Agente Compras RetailCorp",
        entity_type=EntityType.COMPANY,
        public_description="Comprador enterprise buscando soluciones SaaS.",
        personality="Analitico, busca el mejor precio.",
        objectives=["Adquirir SaaS platform", "Negociar bajo presupuesto"],
        interests=["enterprise_saas", "bulk_deals"],
        capabilities=["corporate_budget", "fast_approval"],
        status=AgentStatus.AVAILABLE,
    )
    create_agent_profile(buyer, user_id=uuid4(), session=session)

    # ── Agent 4: P2P Buyer ──────────────────────────────────────────
    p2p_buyer_id = UUID("b0000000-0000-0000-0000-000000000004")
    p2p_buyer = AgentProfile(
        agent_id=p2p_buyer_id,
        display_name="Comprador Particular Laptop",
        entity_type=EntityType.PERSON,
        public_description="Busca laptop para trabajo remoto.",
        personality="Practico, busca buen precio.",
        objectives=["Comprar laptop bajo $750 USD"],
        interests=["buy_laptop", "used_electronics"],
        capabilities=["cash_payment", "local_pickup"],
        status=AgentStatus.AVAILABLE,
    )
    create_agent_profile(p2p_buyer, user_id=uuid4(), session=session)

    # ── Active B2B Negotiation (4 turns) ────────────────────────────
    active_sid = UUID("c0000000-0000-0000-0000-000000000001")
    active_transcript = [
        TranscriptMessage(
            speaker_id=b2b_id, turn_index=1,
            public_message="Buenos dias. Tenemos disponibilidad para integrar nuestra plataforma SaaS con 500+ seats. Precio base: $6,000 USD/mes.",
            intent=TurnIntent.OFFER, approved_by_human=False,
        ),
        TranscriptMessage(
            speaker_id=buyer_id, turn_index=2,
            public_message="Interesante. Nuestro presupuesto es $5,200/mes. Podrian ajustar el precio?",
            intent=TurnIntent.COUNTER_OFFER, approved_by_human=False,
        ),
        TranscriptMessage(
            speaker_id=b2b_id, turn_index=3,
            public_message="Podemos ofrecer $5,500/mes con contrato anual y soporte premium incluido. Es nuestra mejor oferta.",
            intent=TurnIntent.COUNTER_OFFER, approved_by_human=False,
        ),
        TranscriptMessage(
            speaker_id=buyer_id, turn_index=4,
            public_message="$5,500 con anual y soporte premium... dejeme revisarlo con el equipo financiero.",
            intent=TurnIntent.QUESTION, approved_by_human=False,
        ),
    ]
    active_state = NegotiationState(
        session_id=active_sid,
        agents=(b2b, buyer),
        current_speaker_id=b2b_id,
        status=SessionStatus.ACTIVE,
        transcript=active_transcript,
        turn_count=4, max_turns=8,
        deadline_at="2099-01-01T00:00:00Z",  # type: ignore[arg-type]
    )
    row = NegotiationStateRow(
        session_id=active_sid,
        agent_1_id=b2b_id, agent_2_id=buyer_id, initiator_id=b2b_id,
        current_speaker_id=b2b_id,
        status=SessionStatus.ACTIVE.value,
        turn_count=4, max_turns=8,
        portal_channel_id="ch_demo_b2b_active",
        raw_state=active_state.model_dump(mode="json"),
    )
    session.add(row)
    write_audit(
        session_id=active_sid, actor_type="SYSTEM", actor_id="seed",
        action=AuditAction.SESSION_CREATED, severity="INFO",
        reason="Demo: B2B active negotiation",
        session=session,
    )
    print(f"[SEED] Active B2B negotiation: {active_sid} (4 turns)")

    # ── Pending P2P Negotiation ─────────────────────────────────────
    pending_sid = UUID("c0000000-0000-0000-0000-000000000002")
    pending_transcript = [
        TranscriptMessage(
            speaker_id=p2p_id, turn_index=1,
            public_message="Vendo MacBook Pro 2022, 16GB RAM, 512GB SSD. Precio: $900 USD. Entrega en Lima Centro.",
            intent=TurnIntent.OFFER, approved_by_human=False,
        ),
        TranscriptMessage(
            speaker_id=p2p_buyer_id, turn_index=2,
            public_message="Me interesa. Podrias aceptar $750 USD? Pago en efectivo, recojo hoy.",
            intent=TurnIntent.COUNTER_OFFER, approved_by_human=False,
        ),
        TranscriptMessage(
            speaker_id=p2p_id, turn_index=3,
            public_message="$750 esta por debajo de mi minimo. Puedo bajar a $850 pero es lo minimo que acepto.",
            intent=TurnIntent.COUNTER_OFFER, approved_by_human=False,
        ),
    ]
    pending_decision = DecisionRequest(
        session_id=pending_sid, owner_agent_id=p2p_id, requester_agent_id=p2p_buyer_id,
        kind=DecisionKind.OUTBOUND_TURN,
        reasons=[DecisionReason.USER_RULE],
        matched_rule_ids=["r2"],
        candidate_turn=AgentTurn(
            public_message="Acepto vender la laptop por $750 USD con entrega en Lima Centro.",
            intent=TurnIntent.ACCEPT,
        ),
    )
    pending_state = NegotiationState(
        session_id=pending_sid,
        agents=(p2p, p2p_buyer),
        current_speaker_id=p2p_id,
        status=SessionStatus.PENDING_HUMAN_APPROVAL,
        transcript=pending_transcript,
        turn_count=3, max_turns=8,
        deadline_at="2099-01-01T00:00:00Z",  # type: ignore[arg-type]
        pending_decision=pending_decision,
    )
    row2 = NegotiationStateRow(
        session_id=pending_sid,
        agent_1_id=p2p_id, agent_2_id=p2p_buyer_id, initiator_id=p2p_id,
        current_speaker_id=p2p_id,
        status=SessionStatus.PENDING_HUMAN_APPROVAL.value,
        turn_count=3, max_turns=8,
        portal_channel_id="ch_demo_p2p_pending",
        raw_state=pending_state.model_dump(mode="json"),
    )
    session.add(row2)
    write_audit(
        session_id=pending_sid, actor_type="SYSTEM", actor_id="seed",
        action=AuditAction.APPROVAL_REQUESTED, severity="WARNING",
        reason="Demo: P2P negotiation pending approval — offer below hard limit",
        session=session,
    )
    print(f"[SEED] Pending P2P negotiation: {pending_sid} (3 turns, PENDING_HUMAN_APPROVAL)")

    session.commit()
    print("[SEED] All demo data seeded successfully")


if __name__ == "__main__":
    init_db()
    session = get_session()
    try:
        seed(session)
    finally:
        session.close()
