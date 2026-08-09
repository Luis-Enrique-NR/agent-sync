from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from ai.domain.models import (
    ActionAuthorization,
    ActionType,
    AgentTurn,
    DataRequest,
    ProviderStep,
    ProviderStepKind,
    RequestedAction,
    SensitiveDataCategory,
    ToolCallRequest,
    ToolDescriptor,
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolParameterDefinition,
    ToolRiskLevel,
    ToolValueType,
    TranscriptMessage,
    TurnIntent,
)
from ai.providers.base import GenerationRequest
from ai.providers.openai_provider import OpenAIProvider


class _FakeResponses:
    def __init__(self, step: ProviderStep) -> None:
        self.step = step
        self.calls: list[dict] = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_parsed=self.step)


def _turn_step(turn: AgentTurn) -> ProviderStep:
    return ProviderStep(kind=ProviderStepKind.TURN, turn=turn)


def test_openai_adapter_requests_structured_output_and_sanitizes_counterpart(
    p2p_agents,
) -> None:
    turn = AgentTurn(
        public_message="¿La bicicleta sigue disponible?",
        intent=TurnIntent.QUESTION,
    )
    responses = _FakeResponses(_turn_step(turn))
    client = SimpleNamespace(responses=responses)
    provider = OpenAIProvider(model="test-model", client=client)  # type: ignore[arg-type]
    seller, buyer = p2p_agents

    result = provider.generate_step(
        GenerationRequest(speaker=seller, counterpart=buyer, transcript=())
    )

    assert result.turn == turn
    call = responses.calls[0]
    assert call["text_format"] is ProviderStep
    assert call["store"] is False
    assert buyer.personality not in call["input"]
    assert buyer.objectives[0] not in call["input"]
    assert "contact_ref_valentina_phone" in call["input"]


def test_openai_prompt_never_exposes_counterpart_private_references(
    p2p_agents,
) -> None:
    seller, buyer = p2p_agents
    public_message = TranscriptMessage(
        speaker_id=seller.agent_id,
        turn_index=1,
        public_message="Puedo compartir el contacto después de autorización.",
        intent=TurnIntent.OFFER,
        data_requests=[
            DataRequest(
                category=SensitiveDataCategory.MEETING_POINT,
                purpose="coordinar en un lugar público",
            )
        ],
        disclosed_categories=[SensitiveDataCategory.PHONE],
        approved_by_human=True,
    )
    turn = AgentTurn(
        public_message="Gracias. Podemos seguir coordinando sin revelar datos aquí.",
        intent=TurnIntent.QUESTION,
    )
    responses = _FakeResponses(_turn_step(turn))
    client = SimpleNamespace(responses=responses)
    provider = OpenAIProvider(model="test-model", client=client)  # type: ignore[arg-type]

    provider.generate_step(
        GenerationRequest(
            speaker=buyer,
            counterpart=seller,
            transcript=(public_message,),
        )
    )

    prompt = responses.calls[0]["input"]
    assert "contact_ref_valentina_phone" not in prompt
    assert "location_ref_public_meeting_point" not in prompt
    assert '"disclosed_categories":["PHONE"]' in prompt
    assert '"category":"MEETING_POINT"' in prompt


def test_openai_prompt_includes_only_structured_human_action_authorization(
    p2p_agents,
) -> None:
    seller, buyer = p2p_agents
    requested_action = RequestedAction(
        action_type=ActionType.MEETING,
        purpose="revisar la bicicleta en un lugar público",
    )
    public_message = TranscriptMessage(
        speaker_id=seller.agent_id,
        turn_index=1,
        public_message="¿Podemos reunirnos para revisar la bicicleta?",
        intent=TurnIntent.QUESTION,
        requested_actions=[requested_action],
    )
    authorization = ActionAuthorization(
        action_id=requested_action.action_id,
        decision_id=uuid4(),
        owner_agent_id=buyer.agent_id,
        requester_agent_id=seller.agent_id,
        approved=True,
    )
    turn = AgentTurn(
        public_message="La reunión fue autorizada; confirmemos el horario.",
        intent=TurnIntent.QUESTION,
    )
    responses = _FakeResponses(_turn_step(turn))
    client = SimpleNamespace(responses=responses)
    provider = OpenAIProvider(model="test-model", client=client)  # type: ignore[arg-type]

    provider.generate_step(
        GenerationRequest(
            speaker=buyer,
            counterpart=seller,
            transcript=(public_message,),
            action_authorizations=(authorization,),
        )
    )

    prompt = responses.calls[0]["input"]
    assert str(requested_action.action_id) in prompt
    assert '"approved":true' in prompt
    assert "contact_ref_valentina_phone" not in prompt


def test_openai_prompt_includes_allowlisted_tools_and_private_results(
    p2p_agents,
) -> None:
    seller, buyer = p2p_agents
    call = ToolCallRequest(
        tool_name="web.search",
        purpose="consultar una referencia pública",
        arguments={"query": "precio bicicleta urbana usada"},
    )
    tool = ToolDescriptor(
        name="web.search",
        description="Search public sources.",
        risk_level=ToolRiskLevel.READ_ONLY,
        parameters=[
            ToolParameterDefinition(
                name="query",
                value_type=ToolValueType.STRING,
                description="Search query.",
            )
        ],
    )
    result = ToolExecutionResult(
        call_id=call.call_id,
        tool_name=call.tool_name,
        requested_by_agent_id=seller.agent_id,
        status=ToolExecutionStatus.SUCCEEDED,
        output={"mode": "SIMULATED", "answer": "referencia encontrada"},
    )
    turn = AgentTurn(
        public_message="Encontré una referencia pública útil.",
        intent=TurnIntent.QUESTION,
    )
    responses = _FakeResponses(_turn_step(turn))
    client = SimpleNamespace(responses=responses)
    provider = OpenAIProvider(model="test-model", client=client)  # type: ignore[arg-type]

    provider.generate_step(
        GenerationRequest(
            speaker=seller,
            counterpart=buyer,
            transcript=(),
            available_tools=(tool,),
            tool_results=(result,),
        )
    )

    prompt = responses.calls[0]["input"]
    assert '"name":"web.search"' in prompt
    assert '"mode":"SIMULATED"' in prompt
    assert "contact_ref_valentina_phone" in prompt
