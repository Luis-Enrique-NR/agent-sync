from __future__ import annotations

from ai.domain.models import (
    ActionType,
    AgentTurn,
    DataRequest,
    NumericTerm,
    ProposedDisclosure,
    RequestedAction,
    SensitiveDataCategory,
    TurnIntent,
)
from ai.policies.guardrails import GuardrailPipeline


def test_price_below_hard_minimum_is_blocked(p2p_agents) -> None:
    seller, _ = p2p_agents
    turn = AgentTurn(
        public_message="Puedo aceptar 250 USD.",
        intent=TurnIntent.OFFER,
        numeric_terms=[NumericTerm(key="price_usd", value=250, unit="USD")],
    )

    result = GuardrailPipeline().evaluate(seller, turn)

    assert not result.allowed
    assert "HARD_NUMERIC_LIMIT" in {item.code for item in result.violations}


def test_raw_phone_in_public_text_is_blocked(p2p_agents) -> None:
    seller, _ = p2p_agents
    turn = AgentTurn(
        public_message="Puedes llamarme al +57 300 123 4567.",
        intent=TurnIntent.QUESTION,
    )

    result = GuardrailPipeline().evaluate(seller, turn)

    assert not result.allowed
    assert "RAW_PHONE_IN_PUBLIC_TEXT" in {item.code for item in result.violations}


def test_known_reference_can_be_proposed_without_revealing_it(p2p_agents) -> None:
    seller, _ = p2p_agents
    turn = AgentTurn(
        public_message="Puedo compartir el contacto después de autorización.",
        intent=TurnIntent.QUESTION,
        proposed_disclosures=[
            ProposedDisclosure(
                category=SensitiveDataCategory.PHONE,
                value_ref="contact_ref_valentina_phone",
                purpose="coordinar la revisión",
            )
        ],
    )

    result = GuardrailPipeline().evaluate(seller, turn)

    assert result.allowed


def test_unknown_private_reference_is_blocked(p2p_agents) -> None:
    seller, _ = p2p_agents
    turn = AgentTurn(
        public_message="Puedo compartir un contacto después de autorización.",
        intent=TurnIntent.QUESTION,
        proposed_disclosures=[
            ProposedDisclosure(
                category=SensitiveDataCategory.PHONE,
                value_ref="invented_ref",
                purpose="coordinar",
            )
        ],
    )

    result = GuardrailPipeline().evaluate(seller, turn)

    assert not result.allowed
    assert "UNKNOWN_PRIVATE_REFERENCE" in {
        item.code for item in result.violations
    }


def test_requesting_counterpart_data_does_not_require_ownership(p2p_agents) -> None:
    _, buyer = p2p_agents
    turn = AgentTurn(
        public_message="¿Puedes compartir un teléfono después de autorización?",
        intent=TurnIntent.QUESTION,
        data_requests=[
            DataRequest(
                category=SensitiveDataCategory.PHONE,
                purpose="coordinar la revisión",
            )
        ],
    )

    result = GuardrailPipeline().evaluate(buyer, turn)

    assert result.allowed


def test_private_reference_in_data_request_purpose_is_blocked(p2p_agents) -> None:
    seller, _ = p2p_agents
    turn = AgentTurn(
        public_message="¿Puedes compartir un teléfono después de autorización?",
        intent=TurnIntent.QUESTION,
        data_requests=[
            DataRequest(
                category=SensitiveDataCategory.PHONE,
                purpose="coordinar con contact_ref_valentina_phone",
            )
        ],
    )

    result = GuardrailPipeline().evaluate(seller, turn)

    assert not result.allowed
    assert "PRIVATE_REFERENCE_IN_PUBLIC_TEXT" in {
        item.code for item in result.violations
    }


def test_raw_phone_in_data_request_purpose_is_blocked(p2p_agents) -> None:
    seller, _ = p2p_agents
    turn = AgentTurn(
        public_message="Solicito un teléfono para coordinar.",
        intent=TurnIntent.QUESTION,
        data_requests=[
            DataRequest(
                category=SensitiveDataCategory.PHONE,
                purpose="llamar al +57 300 123 4567",
            )
        ],
    )

    result = GuardrailPipeline().evaluate(seller, turn)

    assert not result.allowed
    assert "RAW_PHONE_IN_PUBLIC_TEXT" in {
        item.code for item in result.violations
    }


def test_sensitive_value_hidden_in_action_parameters_is_blocked(p2p_agents) -> None:
    seller, _ = p2p_agents
    turn = AgentTurn(
        public_message="Propongo coordinar una reunión.",
        intent=TurnIntent.QUESTION,
        requested_actions=[
            RequestedAction(
                action_type=ActionType.MEETING,
                purpose="coordinar la revisión",
                parameters={"contact": "+57 300 123 4567"},
            )
        ],
    )

    result = GuardrailPipeline().evaluate(seller, turn)

    assert not result.allowed
    assert "RAW_PHONE_IN_PUBLIC_TEXT" in {
        item.code for item in result.violations
    }


def test_meeting_request_hidden_only_in_prose_is_blocked(p2p_agents) -> None:
    seller, _ = p2p_agents
    turn = AgentTurn(
        public_message="¿Podemos reunirnos mañana para revisar la bicicleta?",
        intent=TurnIntent.QUESTION,
    )

    result = GuardrailPipeline().evaluate(seller, turn)

    assert not result.allowed
    assert "UNSTRUCTURED_MEETING_REQUEST" in {
        item.code for item in result.violations
    }


def test_structured_meeting_request_is_allowed(p2p_agents) -> None:
    seller, _ = p2p_agents
    turn = AgentTurn(
        public_message="¿Podemos reunirnos mañana para revisar la bicicleta?",
        intent=TurnIntent.QUESTION,
        requested_actions=[
            RequestedAction(
                action_type=ActionType.MEETING,
                purpose="revisar la bicicleta",
            )
        ],
    )

    result = GuardrailPipeline().evaluate(seller, turn)

    assert result.allowed


def test_currency_amount_without_structured_term_is_blocked(p2p_agents) -> None:
    seller, _ = p2p_agents
    turn = AgentTurn(
        public_message="Puedo aceptar 250 USD.",
        intent=TurnIntent.ACCEPT,
    )

    result = GuardrailPipeline().evaluate(seller, turn)

    assert not result.allowed
    assert "UNSTRUCTURED_CURRENCY_AMOUNT" in {
        item.code for item in result.violations
    }


def test_exact_address_in_public_text_is_blocked(p2p_agents) -> None:
    seller, _ = p2p_agents
    turn = AgentTurn(
        public_message="La entrega sería en Carrera 7 # 12-34.",
        intent=TurnIntent.QUESTION,
    )

    result = GuardrailPipeline().evaluate(seller, turn)

    assert not result.allowed
    assert "RAW_ADDRESS_IN_PUBLIC_TEXT" in {
        item.code for item in result.violations
    }
