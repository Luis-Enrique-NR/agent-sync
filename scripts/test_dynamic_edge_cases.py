"""Dynamic Edge Cases — 5 matchmaking scenarios including recruitment domain."""

import os, sys, json, asyncio
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field
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
from ai.domain.models import AgentTurn, TurnIntent
from persistence.database import init_db, get_session
from persistence.models import AgentProfileRow, NegotiationStateRow, AuditRecordRow
from sqlmodel import select
from transport.models import TransportEnvelopeV1
from transport.bus import EventDelivery

results = []


@dataclass
class RecordingBus:
    accepted: list = field(default_factory=list)
    async def accept(self, e): self.accepted.append(e)
    async def receive(self, c, l): return None
    async def ack(self, d): pass
    async def fail(self, d, c): pass


class FakeSecret:
    async def get_secret(self): return "t"


def run_scenario(name, domain, condition, agents_data, scripted_turns, expected_match):
    bus = RecordingBus()
    app = create_app(secret_provider=FakeSecret(), bus=bus)
    app.state.engine = NegotiationEngine(ScriptedLLMProvider(scripted_turns))
    c = TestClient(app)

    init_db()
    s = get_session()
    for t in [AgentProfileRow, NegotiationStateRow, AuditRecordRow]:
        for r in s.exec(select(t)).all(): s.delete(r)
    s.commit()
    s.close()

    agent_ids = []
    for ad in agents_data:
        r = c.post("/api/v1/agents", json=ad)
        agent_ids.append(r.json()["agent_id"] if r.status_code in (200, 201) else None)

    from eda.handlers import NegotiationHandler
    async def dispatch():
        h = NegotiationHandler(engine=app.state.engine, portal=None)
        for i, env in enumerate(bus.accepted):
            await h.handle(EventDelivery(message_id=f"msg_{i}", envelope=env))
    asyncio.run(dispatch())

    s = get_session()
    sessions = s.exec(select(NegotiationStateRow)).all()
    agents = s.exec(select(AgentProfileRow)).all()
    agent_statuses = {a.agent_id: a.status for a in agents}
    s.close()

    match = len(sessions) > 0
    transcript_texts = []
    for sess in sessions:
        for t in sess.raw_state.get("transcript", []):
            transcript_texts.append(t.get("public_message", ""))

    all_text = " ".join(transcript_texts).lower()

    # Watermark checks
    has_ecommerce = any(w in all_text for w in ["laptop", "producto", "vendedor", "comprador", "bicicleta"])
    has_recruitment = any(w in all_text for w in ["rust", "salary", "remote", "fintech", "engineer", "web3"])

    result = {
        "scenario": name,
        "domain": domain,
        "condition": condition,
        "match_detected": match,
        "session_count": len(sessions),
        "agent_statuses": {str(k)[:8]: v for k, v in agent_statuses.items()},
        "expected_match": expected_match,
        "pass": match == expected_match,
        "transcript_sample": transcript_texts[:4],
        "has_ecommerce_terms": has_ecommerce,
        "has_recruitment_terms": has_recruitment,
    }
    results.append(result)
    status = "PASS" if result["pass"] else "FAIL"
    print(f"  {name:40s} | match={str(match):5s} | sessions={len(sessions)} | {status}")
    return result


# ── Define all 5 scenarios ─────────────────────────────────────────────

generic_turn = AgentTurn(public_message="oferta de prueba", intent=TurnIntent.OFFER)
recruitment_turns = [
    AgentTurn(public_message="Buscamos un Senior Rust Engineer para Fintech Web3. Presupuesto: $120K/year remoto.", intent=TurnIntent.OFFER),
    AgentTurn(public_message="Me interesa. Mi expectativa es $100K minimo. Tengo 5 años en Rust y Solidity.", intent=TurnIntent.COUNTER_OFFER),
    AgentTurn(public_message="Ofrecemos $110K + equity. Trabajo 100% remoto con horario flexible.", intent=TurnIntent.COUNTER_OFFER),
    AgentTurn(public_message="$115K y trato hecho. Puedo empezar en 2 semanas.", intent=TurnIntent.OFFER),
    AgentTurn(public_message="Acepto $115K. Bienvenido al equipo!", intent=TurnIntent.ACCEPT),
]

print("=" * 72)
print("  DYNAMIC EDGE CASES — 5 Scenarios")
print("=" * 72)

# 1: Buyer vs Buyer
run_scenario("1_Buyer_vs_Buyer", "E-Commerce", "Rol Invalido",
    [
        {"display_name":"BuyerA","entity_type":"person","public_description":"t","personality":"t","objectives":["t"],"interests":["buy_item"],"capabilities":["cash"],"price_range":{"min":0,"max":900}},
        {"display_name":"BuyerB","entity_type":"person","public_description":"t","personality":"t","objectives":["t"],"interests":["buy_item"],"capabilities":["cash"],"price_range":{"min":0,"max":850}},
    ],
    [generic_turn] * 10, False)

# 2: Exact boundary
run_scenario("2_Exact_Boundary", "E-Commerce", "$850 vs $850",
    [
        {"display_name":"Buyer","entity_type":"person","public_description":"t","personality":"t","objectives":["t"],"interests":["buy_item"],"capabilities":["cash"],"price_range":{"min":0,"max":850}},
        {"display_name":"Seller","entity_type":"person","public_description":"t","personality":"t","objectives":["t"],"interests":["sell_item"],"capabilities":["buy_item"],"price_range":{"min":850,"max":1300}},
    ],
    [generic_turn] * 10, True)

# 3: Negative $1 gap
run_scenario("3_Negative_Gap", "E-Commerce", "$849 vs $850",
    [
        {"display_name":"Buyer","entity_type":"person","public_description":"t","personality":"t","objectives":["t"],"interests":["buy_item"],"capabilities":["cash"],"price_range":{"min":0,"max":849}},
        {"display_name":"Seller","entity_type":"person","public_description":"t","personality":"t","objectives":["t"],"interests":["sell_item"],"capabilities":["buy_item"],"price_range":{"min":850,"max":1300}},
    ],
    [generic_turn] * 10, False)

# 4: Multi-agent competition
run_scenario("4_Multi_Agent", "E-Commerce", "2 Buyers vs 1 Seller",
    [
        {"display_name":"Seller","entity_type":"person","public_description":"t","personality":"t","objectives":["t"],"interests":["sell_item"],"capabilities":["buy_item"],"price_range":{"min":800,"max":1300}},
        {"display_name":"BuyerA","entity_type":"person","public_description":"t","personality":"t","objectives":["t"],"interests":["buy_item"],"capabilities":["cash"],"price_range":{"min":0,"max":900}},
        {"display_name":"BuyerB","entity_type":"person","public_description":"t","personality":"t","objectives":["t"],"interests":["buy_item"],"capabilities":["cash"],"price_range":{"min":0,"max":880}},
    ],
    [generic_turn] * 10, True)

# 5: Recruitment domain
run_scenario("5_Recruitment", "Laboral", "Startup vs Dev Rust",
    [
        {"display_name":"Web3 Startup Recruiter","entity_type":"company","public_description":"Fintech Web3 startup","personality":"Profesional","objectives":["Contratar Senior Rust Engineer"],"interests":["hire_rust_engineer"],"capabilities":["equity_compensation","remote_work"],"price_range":{"min":0,"max":120000}},
        {"display_name":"Rust Senior Dev","entity_type":"person","public_description":"Senior Rust dev","personality":"Tecnico","objectives":["Buscar trabajo Senior Rust remoto"],"interests":["find_rust_job"],"capabilities":["rust","solidity","web3","hire_rust_engineer"],"price_range":{"min":100000,"max":200000}},
    ],
    recruitment_turns, True)

# ── Write report ───────────────────────────────────────────────────────
report = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "scenarios": results,
    "summary": {
        "total": len(results),
        "passed": sum(1 for r in results if r["pass"]),
        "failed": sum(1 for r in results if not r["pass"]),
    }
}

output = Path(__file__).resolve().parent.parent / "logs" / "dynamic_matchmaking_edgecases_trace.json"
output.write_text(json.dumps(report, indent=2, default=str, ensure_ascii=False), encoding="utf-8")

print(f"\n{'='*72}")
print(f"  SUMMARY: {report['summary']['passed']}/{report['summary']['total']} passed")
print(f"  Report: {output}")
print(f"{'='*72}")
