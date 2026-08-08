"""Deterministic provider for unit tests and offline demos."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable

from ai.domain.models import AgentTurn
from ai.providers.base import GenerationRequest


class ScriptedLLMProvider:
    def __init__(self, scripted_results: Iterable[AgentTurn | Exception]) -> None:
        self._results = deque(scripted_results)
        self.requests: list[GenerationRequest] = []

    def generate_turn(self, request: GenerationRequest) -> AgentTurn:
        self.requests.append(request)
        if not self._results:
            raise RuntimeError("scripted provider exhausted")
        result = self._results.popleft()
        if isinstance(result, Exception):
            raise result
        return result.model_copy(deep=True)
