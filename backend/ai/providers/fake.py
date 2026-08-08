"""Deterministic provider for unit tests and offline demos."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable

from ai.domain.models import AgentTurn, ProviderStep, ProviderStepKind, TurnIntent
from ai.providers.base import GenerationRequest


class ScriptedLLMProvider:
    def __init__(
        self,
        scripted_results: Iterable[AgentTurn | ProviderStep | Exception],
    ) -> None:
        self._results = deque(scripted_results)
        self.requests: list[GenerationRequest] = []

    def generate_step(self, request: GenerationRequest) -> ProviderStep:
        self.requests.append(request)
        if not self._results:
            raise RuntimeError("scripted provider exhausted")
        result = self._results.popleft()
        if isinstance(result, Exception):
            raise result
        if isinstance(result, AgentTurn):
            return ProviderStep(
                kind=ProviderStepKind.TURN,
                turn=result.model_copy(deep=True),
            )
        return result.model_copy(deep=True)


class OfflineLLMProvider:
    """Small deterministic provider for local/dev environments without secrets."""

    model = "offline-demo"

    def generate_step(self, request: GenerationRequest) -> ProviderStep:
        if not request.transcript:
            turn = AgentTurn(
                public_message=(
                    f"Hola, {request.counterpart.display_name}. "
                    "¿Podemos revisar si nuestros objetivos son compatibles?"
                ),
                intent=TurnIntent.QUESTION,
            )
        else:
            turn = AgentTurn(
                public_message="Gracias por la información. Continuemos con los detalles.",
                intent=TurnIntent.QUESTION,
            )
        return ProviderStep(kind=ProviderStepKind.TURN, turn=turn)
