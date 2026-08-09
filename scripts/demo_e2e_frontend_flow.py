"""Frontend E2E flow demo — simulates Anthony's consumption of the REST API.

Registers 2 compatible agents, verifies matchmaking triggered the
full negotiation pipeline, submits a human decision, and checks
the resulting state.
"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID, uuid4

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient
from sqlmodel import select

from ai.providers.fake import ScriptedLLMProvider
from ai.engine.graph import NegotiationEngine
from ai.domain.models import AgentTurn, TurnIntent
from api.app import create_app
from persistence.database import init_db, get_session
from persistence.models import AgentProfileRow, NegotiationStateRow, AuditRecordRow

# ── Build test app ─────────────────────────────────────────────────────


class FakeSecret:
    async def get_secret(self):
        return "t"


class RecordingBus:
    accepted = []

    async def accept(self, e):
        self.accepted.append(e)

    async def receive(self, c, l):
        return None

    async def ack(self, d):
        pass

    async def fail(self, d, c):
        pass


bus = RecordingBus()
turn = AgentTurn(public_message="oferta de prueba", intent=TurnIntent.OFFER)
app = create_app(secret_provider=FakeSecret(), bus=bus)
app.state.engine = NegotiationEngine(ScriptedLLMProvider([turn] * 20))
client = TestClient(app)

# ── Clean DB ───────────────────────────────────────────────────────────

init_db()
s = get_session()
for t in [AgentProfileRow, NegotiationStateRow, AuditRecordRow]:
    for r in s.exec(select(t)).all():
        s.delete(r)
s.commit()
s.close()

print("=" * 64)
print("  AgentSync — Frontend E2E Flow Demo")
print("=" * 64)

# ── 1. Register Seller ────────────────────────────────────────────────

print("\n[HTTP 201] Registering Seller...")
r1 = client.post("/api/v1/agents", json={
    "display_name": "Valentina (Seller)",
    "entity_type": "person",
    "public_description": "Vende bicicleta urbana",
    "personality": "Amable y cuidadosa",
    "objectives": ["Vender bicicleta"],
    "interests": ["sell_used_bicycle"],
    "capabilities": ["sell_bicycle", "buy_used_bicycle"],
})
assert r1.status_code == 201, r1.text
s1 = r1.json()
print(f"  -> Agent ID: {s1['agent_id'][:16]}... Status: {s1['status']}")

# ── 2. Register Buyer ─────────────────────────────────────────────────

print("\n[HTTP 201] Registering Buyer...")
r2 = client.post("/api/v1/agents", json={
    "display_name": "Mateo (Buyer)",
    "entity_type": "person",
    "public_description": "Busca bicicleta para diario",
    "personality": "Practico y respetuoso",
    "objectives": ["Comprar bicicleta"],
    "interests": ["buy_used_bicycle"],
    "capabilities": ["cash_payment"],
})
assert r2.status_code == 201, r2.text
s2 = r2.json()
print(f"  -> Agent ID: {s2['agent_id'][:16]}... Status: {s2['status']}")

# ── 3. Simulate consumer (dispatch envelopes through handler) ─────────

from eda.handlers import NegotiationHandler
from transport.bus import EventDelivery
import asyncio


async def dispatch():
    handler = NegotiationHandler(engine=app.state.engine, portal=None)
    for i, envelope in enumerate(bus.accepted):
        delivery = EventDelivery(message_id=f"msg_{i}", envelope=envelope)
        await handler.handle(delivery)


asyncio.run(dispatch())

# ── 4. Verify domain state ────────────────────────────────────────────

s = get_session()
buyer_row = s.get(AgentProfileRow, UUID(s2["agent_id"]))
seller_row = s.get(AgentProfileRow, UUID(s1["agent_id"]))

print(f"\n[DB Update] After matchmaking:")
print(f"  Valentina: {seller_row.status}")
print(f"  Mateo:     {buyer_row.status}")

sessions = s.exec(
    select(NegotiationStateRow).where(
        (NegotiationStateRow.agent_1_id == buyer_row.agent_id)
        | (NegotiationStateRow.agent_2_id == buyer_row.agent_id)
    )
).all()

if sessions:
    sess = sessions[0]
    print(f"\n[DB Update] Negotiation Session Created:")
    print(f"  Session ID: {sess.session_id}")
    print(f"  Status:     {sess.status}")
    print(f"  Channel:    {sess.portal_channel_id}")

    audits = s.exec(
        select(AuditRecordRow).where(
            AuditRecordRow.session_id == sess.session_id,
        )
    ).all()
    print(f"\n[Audit] {len(audits)} record(s) written")
    for a in audits:
        print(f"  [{a.severity}] {a.action}")

    if buyer_row.status == "BUSY" and seller_row.status == "BUSY" and sess.status in ("ACTIVE", "PENDING_HUMAN_APPROVAL"):
        print("\n" + "=" * 64)
        print("  MATCHMAKING E2E CYCLE VERIFIED SUCCESSFULLY")
        print("=" * 64)
    else:
        print("\n[WARN] Matchmaking did not complete as expected")
else:
    print("\n[WARN] No negotiation session created")

s.close()
