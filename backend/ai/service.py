"""Composition root used by Backend API."""

from __future__ import annotations

from ai.config import AISettings
from ai.engine.graph import NegotiationEngine
from ai.providers.openai_provider import OpenAIProvider


def build_engine_from_env(settings: AISettings | None = None) -> NegotiationEngine:
    configured = settings or AISettings.from_env()
    provider = OpenAIProvider(
        model=configured.llm_model,
        timeout_seconds=configured.llm_timeout_seconds,
        max_retries=configured.llm_max_retries,
    )
    return NegotiationEngine(provider)
