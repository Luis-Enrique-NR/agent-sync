"""Portal E2E traceability — dumps all JSON payloads through the full lifecycle.

Registers agents, triggers matchmaking, runs the AI engine, and captures
every structured payload (agents, session, transcript, portal envelopes)
into a single JSON trace file.
"""

import os, sys, json, logging
from pathlib import Path
from dataclasses import dataclass, field
from uuid import UUID, uuid4
from datetime import datetime, timezone

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

os.environ["PORTAL_SECRET_KEY"] = "demo-secret"
os.environ["OPENAI_API_KEY"] = "demo-key"
os.environ["AGENTSYNC_LLM_PROVIDER"] = "fake"

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("trace")

from fastapi.testclient import TestClient
from api.app import create_app
from ai.providers.fake import ScriptedLLMProvider
from ai.engine.graph import NegotiationEngine
from ai.domain.models import AgentTurn, TurnIntent, AgentProfile, EntityType
from persistence.database import init_db, get_session
from persistence.models import AgentProfileRow, NegotiationStateRow, AuditRecordRow
from ai.domain.models import NegotiationState as DomainNegotiationState
from transport.models import TransportEnvelopeV1, MessageSnapshot
from transport.bus import EventDelivery
from sqlmodel import select

trace = {"events": [], "timestamp": datetime.now(timezone.utc).isoformat()}


@dataclass
class RecordingBus:
    accepted: list[TransportEnvelopeV1] = field(default_factory=list)
    async def accept(self, e): self.accepted.append(e)
    async def receive(self, c, l): return None
    async def ack(self, d): pass
    async def fail(self, d, c): pass


class FakeSecret:
    async def get_secret(self): return "t"


bus = RecordingBus()
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

logger.info("Starting E2E Portal traceability")

# ── EVENT 1: Register agents ───────────────────────────────────────────
buyer = c.post("/api/v1/agents", json={
    "display_name": "Trace Buyer", "entity_type": "person",
    "public_description": "Busca laptop", "personality": "Practico",
    "objectives": ["Comprar laptop"], "interests": ["buy_laptop"],
    "capabilities": ["cash_payment"],
})
seller = c.post("/api/v1/agents", json={
    "display_name": "Trace Seller", "entity_type": "person",
    "public_description": "Vende laptop", "personality": "Amable",
    "objectives": ["Vender laptop"], "interests": ["sell_laptop"],
    "capabilities": ["buy_laptop", "sell_electronics"],
})
buyer_id = buyer.json()["agent_id"]
seller_id = seller.json()["agent_id"]
buyer_uuid = UUID(buyer_id)
seller_uuid = UUID(seller_id)

trace["events"].append({
    "step": "agent_registration",
    "buyer": buyer.json(),
    "seller": seller.json(),
})

for i, env in enumerate(bus.accepted):
    trace["events"].append({
        "step": "bus_envelope",
        "index": i,
        "envelope": env.model_dump(mode="json"),
    })

# ── EVENT 2: Dispatch matchmaking ──────────────────────────────────────
import asyncio
from eda.handlers import NegotiationHandler

async def _dispatch():
    handler = NegotiationHandler(engine=app.state.engine, portal=None)
    for i, env in enumerate(bus.accepted):
        delivery = EventDelivery(message_id=f"msg_{i}", envelope=env)
        await handler.handle(delivery)
asyncio.run(_dispatch())

# ── EVENT 3: Capture session and transcript ────────────────────────────
s = get_session()
sessions = s.exec(
    select(NegotiationStateRow).where(
        (NegotiationStateRow.agent_1_id == buyer_uuid)
        | (NegotiationStateRow.agent_2_id == buyer_uuid)
    )
).all()

for sess in sessions:
    state = DomainNegotiationState.model_validate(sess.raw_state)
    trace["events"].append({
        "step": "session_created",
        "session_id": str(sess.session_id),
        "status": sess.status,
        "turn_count": sess.turn_count,
        "transcript": [
            {"speaker_id": str(t.speaker_id), "turn": t.turn_index, "text": t.public_message, "intent": t.intent.value}
            for t in state.transcript
        ] if hasattr(state, 'transcript') else [],
    })

# ── EVENT 4: Portal transport envelope simulation ──────────────────────
envelope = TransportEnvelopeV1(
    event_id=str(uuid4()),
    event_type="message.published",  # type: ignore[arg-type]
    event_time=datetime.now(timezone.utc),
    environment="production",
    channel=f"ch_trace_{buyer_id[:8]}",
    message=MessageSnapshot(
        id="msg_trace_1", text="Negotiation started successfully",
        author_id=buyer_id, seq=1,
    ),
    retracted=False,
)
trace["events"].append({
    "step": "portal_dispatch",
    "portal_secret_used": bool(os.getenv("PORTAL_SECRET_KEY")),
    "envelope": envelope.model_dump(mode="json"),
})

s.close()

# ── Write trace ────────────────────────────────────────────────────────
output = Path(__file__).resolve().parent.parent / "logs" / "portal_full_traceability.json"
output.write_text(json.dumps(trace, indent=2, default=str), encoding="utf-8")
logger.info("Trace written to %s (%d events)", output, len(trace["events"]))
print(json.dumps(trace, indent=2, default=str))
