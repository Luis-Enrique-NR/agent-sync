from __future__ import annotations

from ai.domain.models import (
    AgentTurn,
    DecisionReason,
    DisclosureRequest,
    NumericTerm,
    SensitiveDataCategory,
    TurnIntent,
)
from ai.policies.escalation import EscalationEvaluator


def test_final_agreement_matches_user_rule(b2b_agents) -> None:
    seller, _ = b2b_agents
    turn = AgentTurn(
        public_message="Acepto el acuerdo por 900 USD.",
        intent=TurnIntent.ACCEPT,
        numeric_terms=[NumericTerm(key="price_usd", value=900, unit="USD")],
    )

    result = EscalationEvaluator().evaluate(seller, turn)

    assert result.required
    assert DecisionReason.USER_RULE in result.reasons
    assert "approve-final-deal" in result.matched_rule_ids


def test_phone_always_requires_approval_even_without_matching_rule(p2p_agents) -> None:
    _, buyer = p2p_agents
    # The buyer has no SHARE_PERSONAL_DATA rule, but mandatory categories still apply.
    turn = AgentTurn(
        public_message="Puedo compartir el contacto tras autorización.",
        intent=TurnIntent.QUESTION,
        disclosure_requests=[
            DisclosureRequest(
                category=SensitiveDataCategory.PHONE,
                value_ref="some_ref",
                purpose="coordinar",
            )
        ],
    )

    result = EscalationEvaluator().evaluate(buyer, turn)

    assert result.required
    assert DecisionReason.MANDATORY_PERSONAL_DATA in result.reasons
