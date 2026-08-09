from __future__ import annotations

from ai.domain.models import (
    ActionType,
    AgentTurn,
    DecisionReason,
    EscalationRule,
    EscalationRuleType,
    NumericTerm,
    ProposedDisclosure,
    RequestedAction,
    SensitiveDataCategory,
    TurnIntent,
)
from ai.policies.escalation import EscalationEvaluator, InboundEscalationEvaluator


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
    seller, _ = p2p_agents
    turn = AgentTurn(
        public_message="Puedo compartir el contacto tras autorización.",
        intent=TurnIntent.QUESTION,
        proposed_disclosures=[
            ProposedDisclosure(
                category=SensitiveDataCategory.PHONE,
                value_ref="contact_ref_valentina_phone",
                purpose="coordinar",
            )
        ],
    )

    result = EscalationEvaluator().evaluate(seller, turn)

    assert result.required
    assert DecisionReason.MANDATORY_PERSONAL_DATA in result.reasons


def test_meeting_request_matches_only_the_receivers_inbound_rule(
    p2p_agents,
) -> None:
    seller, buyer = p2p_agents
    buyer = buyer.model_copy(
        update={
            "escalation_rules": [
                EscalationRule(
                    rule_id="approve-meetings",
                    rule_type=EscalationRuleType.REQUEST_ACTION,
                    action_types={ActionType.MEETING},
                )
            ]
        },
        deep=True,
    )
    turn = AgentTurn(
        public_message="¿Podemos reunirnos para revisar la bicicleta?",
        intent=TurnIntent.QUESTION,
        requested_actions=[
            RequestedAction(
                action_type=ActionType.MEETING,
                purpose="revisar la bicicleta",
            )
        ],
    )

    outbound = EscalationEvaluator().evaluate(seller, turn)
    inbound = InboundEscalationEvaluator().evaluate(buyer, turn)

    assert not outbound.required
    assert inbound.required
    assert DecisionReason.INBOUND_ACTION in inbound.reasons
    assert "approve-meetings" in inbound.matched_rule_ids
