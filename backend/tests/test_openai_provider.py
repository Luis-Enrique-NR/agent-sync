from __future__ import annotations

from types import SimpleNamespace

from ai.domain.models import AgentTurn, TurnIntent
from ai.providers.base import GenerationRequest
from ai.providers.openai_provider import OpenAIProvider


class _FakeResponses:
    def __init__(self, turn: AgentTurn) -> None:
        self.turn = turn
        self.calls: list[dict] = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_parsed=self.turn)


def test_openai_adapter_requests_structured_output_and_sanitizes_counterpart(
    p2p_agents,
) -> None:
    turn = AgentTurn(
        public_message="¿La bicicleta sigue disponible?",
        intent=TurnIntent.QUESTION,
    )
    responses = _FakeResponses(turn)
    client = SimpleNamespace(responses=responses)
    provider = OpenAIProvider(model="test-model", client=client)  # type: ignore[arg-type]
    seller, buyer = p2p_agents

    result = provider.generate_turn(
        GenerationRequest(speaker=seller, counterpart=buyer, transcript=())
    )

    assert result == turn
    call = responses.calls[0]
    assert call["text_format"] is AgentTurn
    assert call["store"] is False
    assert buyer.personality not in call["input"]
    assert buyer.objectives[0] not in call["input"]
    assert "contact_ref_valentina_phone" in call["input"]
