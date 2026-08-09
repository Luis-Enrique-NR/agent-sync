"""Diagnose matchmaking E2E using TestClient (no server needed).

Registers 2 compatible agents and inspects whether matchmaking
creates a negotiation session behind the scenes.
"""

import os, sys, time
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

os.environ["PORTAL_SECRET_KEY"] = "demo-secret"
os.environ["OPENAI_API_KEY"] = "demo-key"
os.environ["AGENTSYNC_LLM_PROVIDER"] = "fake"

from fastapi.testclient import TestClient
from api.app import create_app
from ai.providers.fake import ScriptedLLMProvider
from ai.engine.graph import NegotiationEngine
from ai.domain.models import AgentTurn, TurnIntent
from persistence.database import init_db, get_session
from persistence.models import AgentProfileRow, NegotiationStateRow, AuditRecordRow
from sqlmodel import select
from dataclasses import dataclass, field
from transport.models import TransportEnvelopeV1


@dataclass
class RecordingBus:
    accepted: list[TransportEnvelopeV1] = field(default_factory=list)
    async def accept(self, e): self.accepted.append(e)
    async def receive(self, c, l): return None
    async def ack(self, d): pass
    async def fail(self, d, c): pass


class FakeSecret:
    async def get_secret(self): return "t"


# Build app with recording bus
bus = RecordingBus()
turn = AgentTurn(public_message="oferta de prueba", intent=TurnIntent.OFFER)
app = create_app(secret_provider=FakeSecret(), bus=bus)
app.state.engine = NegotiationEngine(ScriptedLLMProvider([turn] * 20))
c = TestClient(app)

# Clean DB
init_db()
s = get_session()
for t in [AgentProfileRow, NegotiationStateRow, AuditRecordRow]:
    for r in s.exec(select(t)).all():
        s.delete(r)
s.commit()
s.close()

print("=" * 64)
print("  MATCHMAKING E2E DIAGNOSTIC — Commit 6ea898e")
print("=" * 64)

# ── Step 1: Register Buyer ──────────────────────────────────────────────
print("\n[STEP 1] Registering Buyer...")
r1 = c.post("/api/v1/agents", json={
    "display_name": "Diagnostic Buyer",
    "entity_type": "person",
    "public_description": "Busca MacBook Pro",
    "personality": "Practico",
    "objectives": ["Comprar laptop"],
    "interests": ["buy_laptop"],
    "capabilities": ["cash_payment"],
})
print(f"  Status: {r1.status_code}")
buyer = r1.json() if r1.status_code in (200, 201) else None
buyer_id = buyer["agent_id"] if buyer else None
print(f"  Buyer ID: {buyer_id}")

# ── Step 2: Register Seller ─────────────────────────────────────────────
print("\n[STEP 2] Registering Seller...")
r2 = c.post("/api/v1/agents", json={
    "display_name": "Diagnostic Seller",
    "entity_type": "person",
    "public_description": "Vende MacBook Pro",
    "personality": "Amable",
    "objectives": ["Vender laptop"],
    "interests": ["sell_laptop"],
    "capabilities": ["buy_laptop", "sell_electronics"],
})
print(f"  Status: {r2.status_code}")
seller = r2.json() if r2.status_code in (200, 201) else None
seller_id = seller["agent_id"] if seller else None
print(f"  Seller ID: {seller_id}")

# ── Step 3: Dispatch envelopes through handler ─────────────────────────
print("\n[STEP 3] Dispatching agent.registered events through EDA handler...")
if bus.accepted:
    from eda.handlers import NegotiationHandler
    from transport.bus import EventDelivery
    import asyncio

    async def _dispatch():
        handler = NegotiationHandler(engine=app.state.engine, portal=None)
        for i, env in enumerate(bus.accepted):
            delivery = EventDelivery(message_id=f"msg_{i}", envelope=env)
            await handler.handle(delivery)

    asyncio.run(_dispatch())
    print(f"  Dispatched {len(bus.accepted)} events")
else:
    print("  No events recorded on bus — matchmaking cannot trigger")

# ── Step 4: Check negotiations ──────────────────────────────────────────
print("\n[STEP 3] Checking negotiations for buyer...")
r3 = c.get("/api/v1/negotiations", params={"agent_id": buyer_id})
print(f"  Status: {r3.status_code}")
data = r3.json()
neg = data.get("negotiations", [])
print(f"  Negotiations found: {len(neg)}")
for n in neg:
    print(f"    Session: {n['session_id'][:16]}... Status: {n['status']}")

# ── Step 4: Verify agent states ─────────────────────────────────────────
print("\n[STEP 4] Verifying agent states...")
rb = c.get(f"/api/v1/agents/{buyer_id}")
rs = c.get(f"/api/v1/agents/{seller_id}")
print(f"  Buyer status:  {rb.json().get('status', 'N/A')}")
print(f"  Seller status: {rs.json().get('status', 'N/A')}")

# ── VERDICT ─────────────────────────────────────────────────────────────
print("\n" + "=" * 64)
if len(neg) > 0:
    print("  [MATCH FOUND] Negotiation session created")
elif rb.json().get("status") == "BUSY":
    print("  [PARTIAL] Agents BUSY but no session visible via API")
else:
    print("  [NO MATCH] Agents created but no negotiation — matchmaking not triggered")
    print("  Root cause: agent.registered event may not reach EDA handler")
print("=" * 64)
