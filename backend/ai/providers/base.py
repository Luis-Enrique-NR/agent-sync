"""Provider port used by the negotiation engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ai.domain.models import AgentProfile, AgentTurn, TranscriptMessage


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    speaker: AgentProfile
    counterpart: AgentProfile
    transcript: tuple[TranscriptMessage, ...]
    guardrail_feedback: tuple[str, ...] = ()


class LLMProvider(Protocol):
    def generate_turn(self, request: GenerationRequest) -> AgentTurn:
        """Generate one schema-valid candidate turn without publishing it."""
