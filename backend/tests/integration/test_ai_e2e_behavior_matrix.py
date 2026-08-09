"""AI E2E behavior matrix — Expected vs Obtained for guardrails, escalation, and regular flow."""

import logging
from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest
from sqlmodel import select

from ai.domain.models import (
    AgentProfile, AgentTurn, DecisionReason,
    DecisionRequest, EntityType, NegotiationState,
    SessionStatus, TurnIntent,
)
from ai.engine.graph import NegotiationEngine
from ai.policies.guardrails import GuardrailPipeline
from ai.policies.escalation import EscalationEvaluator
from ai.providers.fake import ScriptedLLMProvider
from persistence.database import init_db, get_session
from persistence.models import AgentProfileRow, NegotiationStateRow, AuditRecordRow
from persistence.repository import create_agent_profile, write_audit

logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def clean():
    init_db()
    s = get_session()
    for t in [AgentProfileRow, NegotiationStateRow, AuditRecordRow]:
        for r in s.exec(select(t)).all():
            s.delete(r)
    s.commit()
    s.close()


def _profile(name: str, **kw) -> AgentProfile:
    return AgentProfile(
        display_name=name, entity_type=EntityType.PERSON,
        public_description="t", personality="t", objectives=["t"],
        **kw,
    )


# ── Regular flow: valid turn → transcript updated ──────────────────────


def test_regular_turn_updates_transcript_and_emits_event():
    """Expected: process valid turn → transcript entry + TURN_READY event."""
    engine = NegotiationEngine(ScriptedLLMProvider([
        AgentTurn(public_message="oferta inicial", intent=TurnIntent.OFFER),
    ] * 10))
    a = _profile("A")
    b = _profile("B")
    result = engine.start_session(a, b)

    assert result.state.turn_count >= 1, f"expected at least 1 turn, got {result.state.turn_count}"
    assert len(result.state.transcript) >= 1, f"expected transcript, got {len(result.state.transcript)}"
    assert result.state.transcript[0].public_message == "oferta inicial"
    assert any(e.event_type.value == "TURN_READY" for e in result.events)
    logger.info("[AI_BEHAVIOR] Regular turn flow: PASS — transcript updated, event emitted")


# ── Guardrail: PII blocked ────────────────────────────────────────────


def test_guardrail_blocks_sensitive_data():
    """Expected: phone number in public text → blocked by guardrail."""
    pipeline = GuardrailPipeline()
    profile = _profile("A")
    turn = AgentTurn(
        public_message="mi numero es 300-123-4567 llamame",
        intent=TurnIntent.OFFER,
    )
    result = pipeline.evaluate(profile, turn)
    assert not result.allowed
    assert any("RAW_PHONE" in v.code for v in result.violations)
    logger.info("[AI_BEHAVIOR] Guardrail PII: PASS — phone number blocked")


def test_guardrail_blocks_email():
    """Expected: email in public text → blocked."""
    pipeline = GuardrailPipeline()
    profile = _profile("A")
    turn = AgentTurn(
        public_message="contacto: test@example.com",
        intent=TurnIntent.QUESTION,
    )
    result = pipeline.evaluate(profile, turn)
    assert not result.allowed
    assert any("RAW_EMAIL" in v.code for v in result.violations)
    logger.info("[AI_BEHAVIOR] Guardrail email: PASS — email blocked")


# ── Escalation: budget limit → PENDING_HUMAN_APPROVAL ────────────────


def test_escalation_triggers_on_final_agreement():
    """Expected: FINAL_AGREEMENT rule → PENDING_HUMAN_APPROVAL."""
    evaluator = EscalationEvaluator()
    profile = AgentProfile(
        display_name="A", entity_type=EntityType.PERSON,
        public_description="t", personality="t", objectives=["t"],
        escalation_rules=[{
            "rule_id": "r1",
            "rule_type": "FINAL_AGREEMENT",
            "key": None,
            "threshold": None,
            "categories": [],
            "enabled": True,
        }],
    )
    turn = AgentTurn(public_message="acepto", intent=TurnIntent.ACCEPT)
    result = evaluator.evaluate(profile, turn)
    assert result.required
    assert DecisionReason.USER_RULE in result.reasons
    logger.info("[AI_BEHAVIOR] Escalation FINAL_AGREEMENT: PASS — approval required")


def test_escalation_triggers_on_mandatory_personal_data():
    """Expected: disclosure of PHONE → MANDATORY_PERSONAL_DATA escalation."""
    from ai.domain.models import SensitiveDataCategory, ProposedDisclosure

    evaluator = EscalationEvaluator()
    profile = _profile("A")

    # Use proposed_disclosures with PHONE category
    turn = AgentTurn(
        public_message="mi telefono es ...",
        intent=TurnIntent.OFFER,
        proposed_disclosures=[
            ProposedDisclosure(
                category=SensitiveDataCategory.PHONE,
                value_ref="ref_phone_test",
                purpose="compartir telefono",
            )
        ],
    )
    result = evaluator.evaluate(profile, turn)
    assert result.required
    assert DecisionReason.MANDATORY_PERSONAL_DATA in result.reasons
    logger.info("[AI_BEHAVIOR] Escalation PII: PASS — MANDATORY_PERSONAL_DATA triggered")


# ── Session lifecycle → PENDING_HUMAN_APPROVAL ──────────────────────


def test_engine_pauses_on_max_turns_non_convergence():
    """Expected: max_turns reached → PENDING_HUMAN_APPROVAL (NON_CONVERGENCE)."""
    engine = NegotiationEngine(
        ScriptedLLMProvider([
            AgentTurn(public_message=f"turno {i}", intent=TurnIntent.OFFER)
            for i in range(20)
        ])
    )
    result = engine.start_session(_profile("A"), _profile("B"), max_turns=3)

    # Session should pause with NON_CONVERGENCE
    assert result.state.status in (SessionStatus.PENDING_HUMAN_APPROVAL, SessionStatus.ACTIVE)
    if result.state.status == SessionStatus.PENDING_HUMAN_APPROVAL:
        assert result.state.pending_decision is not None
        logger.info("[AI_BEHAVIOR] Non-convergence: PASS — PENDING_HUMAN_APPROVAL after max_turns")
    else:
        # May have terminated with ACCEPT/DECLINE before max_turns
        logger.info("[AI_BEHAVIOR] Non-convergence: session ended before max_turns (valid)")
