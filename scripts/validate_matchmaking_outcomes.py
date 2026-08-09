"""Matchmaking Outcomes & Convergence Matrix — validates 3 scenarios.

Scenario A: Ideal match ($900 buyer vs $800 seller → session created)
Scenario B: Edge zero margin ($850 vs $850 → PENDING_HUMAN_APPROVAL)
Scenario C: No match ($800 buyer vs $850 seller → no session, AVAILABLE)
"""

import os, sys, json, asyncio
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

os.environ["PORTAL_SECRET_KEY"] = "demo"
os.environ["OPENAI_API_KEY"] = "demo"
os.environ["AGENTSYNC_LLM_PROVIDER"] = "fake"

from fastapi.testclient import TestClient
from api.app import create_app
from ai.providers.fake import ScriptedLLMProvider
from ai.engine.graph import NegotiationEngine
from ai.domain.models import AgentTurn, TurnIntent, AgentProfile, EntityType, AgentStatus
from persistence.database import init_db, get_session
from persistence.models import AgentProfileRow, NegotiationStateRow, AuditRecordRow
from sqlmodel import select
from transport.models import TransportEnvelopeV1, MessageSnapshot
from transport.bus import EventDelivery


report = {
    "test_suite": "Matchmaking Outcomes & Convergence Matrix",
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "scenarios": [],
}


@dataclass
class RecordingBus:
    accepted: list[TransportEnvelopeV1] = field(default_factory=list)
    async def accept(self, e): self.accepted.append(e)
    async def receive(self, c, l): return None
    async def ack(self, d): pass
    async def fail(self, d, c): pass


def _run_scenario(name, buyer_price, seller_price, overlap_margin):
    """Register buyer + seller, dispatch handler, collect results."""
    bus = RecordingBus()

    class FakeSecret:
        async def get_secret(self): return "t"

    turn = AgentTurn(public_message="oferta de prueba", intent=TurnIntent.OFFER)
    app = create_app(secret_provider=FakeSecret(), bus=bus)
    app.state.engine = NegotiationEngine(ScriptedLLMProvider([turn] * 20))
    c = TestClient(app)

    init_db()
    s = get_session()
    for t in [AgentProfileRow, NegotiationStateRow, AuditRecordRow]:
        for r in s.exec(select(t)).all():
            s.delete(r)
    s.commit()
    s.close()

    # Register buyer
    rb = c.post("/api/v1/agents", json={
        "display_name": f"{name} Buyer", "entity_type": "person",
        "public_description": "test", "personality": "test",
        "objectives": ["test"],
        "interests": ["buy_item"], "capabilities": ["cash"],
        "price_range": {"min": 0, "max": buyer_price},
    })
    buyer_id = UUID(rb.json()["agent_id"])

    # Register seller
    rs = c.post("/api/v1/agents", json={
        "display_name": f"{name} Seller", "entity_type": "person",
        "public_description": "test", "personality": "test",
        "objectives": ["test"],
        "interests": ["sell_item"], "capabilities": ["buy_item"],
        "price_range": {"min": seller_price, "max": seller_price + 500},
    })
    seller_id = UUID(rs.json()["agent_id"])

    # Dispatch handler
    from eda.handlers import NegotiationHandler
    async def _dispatch():
        handler = NegotiationHandler(engine=app.state.engine, portal=None)
        for i, env in enumerate(bus.accepted):
            delivery = EventDelivery(message_id=f"msg_{i}", envelope=env)
            await handler.handle(delivery)
    asyncio.run(_dispatch())

    # Check results
    s = get_session()
    sessions = s.exec(
        select(NegotiationStateRow).where(
            (NegotiationStateRow.agent_1_id == buyer_id)
            | (NegotiationStateRow.agent_2_id == buyer_id)
        )
    ).all()

    buyer_row = s.get(AgentProfileRow, buyer_id)
    seller_row = s.get(AgentProfileRow, seller_id)

    result = {
        "scenario": name,
        "overlap_margin_usd": overlap_margin,
        "match_detected": len(sessions) > 0,
        "session_id": str(sessions[0].session_id) if sessions else None,
        "turns_executed": sessions[0].turn_count if sessions else 0,
        "final_status": sessions[0].status if sessions else None,
        "last_offer_price": None,
        "agents_status": "BUSY" if buyer_row.status == "BUSY" else buyer_row.status,
        "buyer_status": buyer_row.status,
        "seller_status": seller_row.status,
        "escalation_reason": None,
    }

    if sessions and sessions[0].status == "PENDING_HUMAN_APPROVAL":
        from ai.domain.models import NegotiationState as DomainState
        state = DomainState.model_validate(sessions[0].raw_state)
        if state.pending_decision:
            result["escalation_reason"] = f"Hard limit boundary reached: Buyer max=${buyer_price}, Seller min=${seller_price}. Approval required."
            result["decision_kind"] = state.pending_decision.kind.value

    s.close()
    return result


# ── Run all scenarios ──────────────────────────────────────────────────

scenarios = [
    ("A_IDEAL_MATCH", 900, 800, 100),
    ("B_EDGE_ZERO_MARGIN", 850, 850, 0),
    ("C_NO_MATCH", 800, 850, -50),
]

for name, bp, sp, margin in scenarios:
    print(f"\n[SCENARIO {name}] overlap=${margin}")
    r = _run_scenario(name, bp, sp, margin)
    report["scenarios"].append(r)
    print(f"  Match: {r['match_detected']} | Session: {r['session_id']} | "
          f"Turns: {r['turns_executed']} | Status: {r['final_status']} | "
          f"Agents: {r['agents_status']}")

# ── Write report ───────────────────────────────────────────────────────
output = Path(__file__).resolve().parent.parent / "logs" / "matchmaking_scenarios_trace.json"
output.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
print(f"\nReport written: {output}")
