from __future__ import annotations

from ai.domain.models import (
    AgentTurn,
    DisclosureRequest,
    NumericTerm,
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


def test_known_reference_can_be_requested_without_revealing_it(p2p_agents) -> None:
    seller, _ = p2p_agents
    turn = AgentTurn(
        public_message="Puedo compartir el contacto después de autorización.",
        intent=TurnIntent.QUESTION,
        disclosure_requests=[
            DisclosureRequest(
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
        disclosure_requests=[
            DisclosureRequest(
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
