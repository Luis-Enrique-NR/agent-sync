"""Provider port used by the negotiation engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ai.domain.models import (
    ActionAuthorization,
    AgentProfile,
    ProviderStep,
    ToolDescriptor,
    ToolExecutionResult,
    TranscriptMessage,
)


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    speaker: AgentProfile
    counterpart: AgentProfile
    transcript: tuple[TranscriptMessage, ...]
    action_authorizations: tuple[ActionAuthorization, ...] = ()
    available_tools: tuple[ToolDescriptor, ...] = ()
    tool_results: tuple[ToolExecutionResult, ...] = ()
    guardrail_feedback: tuple[str, ...] = ()


class LLMProvider(Protocol):
    def generate_step(self, request: GenerationRequest) -> ProviderStep:
        """Generate either one internal tool request or one public turn."""
