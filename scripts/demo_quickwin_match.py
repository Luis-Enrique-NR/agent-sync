"""Quick-win demo: registers two agents, triggers matchmaking, shows the trace.

Usage:  python scripts/demo_quickwin_match.py
"""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

from sqlmodel import Session, select

# Ensure backend is on the path
import sys
from pathlib import Path
BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from ai.domain.models import AgentProfile, AgentStatus, AuditAction, EntityType
from ai.engine.graph import NegotiationEngine
from ai.providers.fake import ScriptedLLMProvider
from ai.domain.models import AgentTurn, TurnIntent
from matchmaking.orchestrator import process_agent_matching
from persistence.database import init_db, get_session
from persistence.models import AgentProfileRow, AuditRecordRow, NegotiationStateRow
from persistence.repository import create_agent_profile


async def main() -> None:
    print("=" * 68)
    print("  AgentSync — Quick-Win Matchmaking Demo")
    print("=" * 68)

    init_db()
    session = get_session()

    # Clean slate
    for table in [AgentProfileRow, NegotiationStateRow, AuditRecordRow]:
        session.exec(table.__table__.delete())  # type: ignore[attr-defined]
    session.commit()

    # ── Register Seller ──────────────────────────────────────────────────
    seller_id = UUID("f0000000-0000-0000-0000-000000000001")
    seller = AgentProfile(
        agent_id=seller_id,
        display_name="Valentina (Vendedora)",
        entity_type=EntityType.PERSON,
        public_description="Vende bicicleta urbana usada en buen estado",
        personality="Amable, directa, cuidadosa con sus datos",
        objectives=["Vender la bicicleta"],
        interests=["sell_used_bicycle", "find_buyer_nearby"],
        capabilities=["sell_bicycle", "weekend_availability", "buy_used_bicycle"],
        status=AgentStatus.AVAILABLE,
    )
    create_agent_profile(seller, user_id=uuid4(), session=session)
    print(f"\n[REGISTER] {seller.display_name}")
    print(f"  interests:    {seller.interests}")
    print(f"  capabilities: {seller.capabilities}")
    print(f"  status:       {seller.status.value}")

    # ── Register Buyer ────────────────────────────────────────────────────
    buyer_id = UUID("f0000000-0000-0000-0000-000000000002")
    buyer = AgentProfile(
        agent_id=buyer_id,
        display_name="Mateo (Comprador)",
        entity_type=EntityType.PERSON,
        public_description="Busca bicicleta para transporte diario",
        personality="Respetuoso, práctico",
        objectives=["Comprar bicicleta sin superar presupuesto"],
        interests=["buy_used_bicycle", "urban_transport"],
        capabilities=["cash_payment", "weekday_pickup"],
        status=AgentStatus.AVAILABLE,
    )
    create_agent_profile(buyer, user_id=uuid4(), session=session)
    print(f"\n[REGISTER] {buyer.display_name}")
    print(f"  interests:    {buyer.interests}")
    print(f"  capabilities: {buyer.capabilities}")
    print(f"  status:       {buyer.status.value}")

    # ── Build engine with scripted (deterministic) provider ──────────────
    opening_turn = AgentTurn(
        public_message="Hola! Vi que buscas una bicicleta. La mia esta en buen estado, mantenimiento reciente. Te interesa?",
        intent=TurnIntent.OFFER,
    )
    # Provide enough turns for the negotiation loop (2 agents x 2 turns each)
    scripted = [opening_turn] * 10
    engine = NegotiationEngine(ScriptedLLMProvider(scripted))
    portal = None  # No real Portal in demo — trade is logged locally

    # ── Trigger matchmaking ──────────────────────────────────────────────
    print("\n[MATCHMAKING] Searching for compatible agents...")
    created = await process_agent_matching(
        buyer_id,
        session=session,
        engine=engine,
        portal=portal,
    )

    session.commit()

    if created:
        session_id = created[0]
        print(f"\n[MATCH FOUND] Session created: {session_id}")

        # Verify state
        buyer_row = session.get(AgentProfileRow, buyer_id)
        seller_row = session.get(AgentProfileRow, seller_id)
        print(f"  {buyer.display_name} status: {buyer_row.status}")
        print(f"  {seller.display_name} status: {seller_row.status}")

        state_row = session.get(NegotiationStateRow, session_id)
        print(f"  channel:  {state_row.portal_channel_id}")
        print(f"  status:   {state_row.status}")
        print(f"  turns:    {state_row.turn_count}")

        # Show audit
        audits = session.exec(
            select(AuditRecordRow).where(
                AuditRecordRow.session_id == session_id,
            )
        ).all()
        print(f"\n[AUDIT] {len(audits)} record(s):")
        for a in audits:
            print(f"  [{a.severity}] {a.action} -- {a.reason}")

        print("\n" + "=" * 68)
        print("  QUICK-WIN COMPLETE -- Matchmaking -> Negotiation -> Audit")
        print("=" * 68)
    else:
        print("\n[NO MATCH] No compatible agents found")
        print("  Check interests/capabilities alignment in AgentProfile")

    session.close()


if __name__ == "__main__":
    asyncio.run(main())
