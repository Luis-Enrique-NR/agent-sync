"""OpenAI Responses API adapter with Pydantic Structured Outputs."""

from __future__ import annotations

import json

from openai import OpenAI

from ai.domain.models import AgentProfile, AgentTurn, ToolFactVisibility
from ai.providers.base import GenerationRequest


SYSTEM_INSTRUCTIONS = """You represent one entity in a preliminary negotiation.
Return exactly one candidate turn using the supplied schema.
Stay faithful to the speaker objectives, personality, hard limits, and known facts.
Never invent contact details, addresses, locations, dates, prices, or tool results.
Every numeric proposal or commitment must also appear in numeric_terms.
When proposing or accepting a date, include it in commitments with kind DATE.
Use ACCEPT only when accepting explicit terms already present in the conversation.
For protected data, use only a supplied opaque value_ref in disclosure_requests.
Never place an opaque value_ref or an actual protected value in public_message.
Instead, say that the information can be shared after authorization.
Keep public_message concise and suitable to send to the counterpart.
Do not decide whether human approval is required; deterministic code does that.
"""


class OpenAIProvider:
    """Real provider kept behind the LLMProvider protocol."""

    def __init__(
        self,
        *,
        model: str,
        timeout_seconds: int = 25,
        max_retries: int = 1,
        max_output_tokens: int = 800,
        client: OpenAI | None = None,
    ) -> None:
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._client = client or OpenAI(
            timeout=timeout_seconds,
            max_retries=max_retries,
        )

    def generate_turn(self, request: GenerationRequest) -> AgentTurn:
        prompt = self._build_prompt(request)
        response = self._client.responses.parse(
            model=self._model,
            instructions=SYSTEM_INSTRUCTIONS,
            input=prompt,
            text_format=AgentTurn,
            max_output_tokens=self._max_output_tokens,
            store=False,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise RuntimeError("model returned no parsed AgentTurn")
        return parsed

    @staticmethod
    def _speaker_context(profile: AgentProfile) -> dict[str, object]:
        public_facts = []
        private_references = []
        for fact in profile.tool_facts:
            if fact.visibility is ToolFactVisibility.PUBLIC:
                public_facts.append({"key": fact.key, "value": fact.value})
            else:
                private_references.append(
                    {
                        "key": fact.key,
                        "category": fact.category.value if fact.category else None,
                        "value_ref": fact.value_ref,
                    }
                )
        return {
            "agent_id": str(profile.agent_id),
            "display_name": profile.display_name,
            "entity_type": profile.entity_type.value,
            "personality": profile.personality,
            "objectives": profile.objectives,
            "hard_limits": [
                limit.model_dump(mode="json") for limit in profile.hard_limits
            ],
            "never_disclose": sorted(item.value for item in profile.never_disclose),
            "public_tool_facts": public_facts,
            "private_reference_manifest": private_references,
        }

    @staticmethod
    def _counterpart_context(profile: AgentProfile) -> dict[str, object]:
        return {
            "agent_id": str(profile.agent_id),
            "display_name": profile.display_name,
            "entity_type": profile.entity_type.value,
            "public_description": profile.public_description,
            "public_tool_facts": [
                {"key": fact.key, "value": fact.value}
                for fact in profile.tool_facts
                if fact.visibility is ToolFactVisibility.PUBLIC
            ],
        }

    @classmethod
    def _build_prompt(cls, request: GenerationRequest) -> str:
        payload = {
            "speaker_private_context": cls._speaker_context(request.speaker),
            "counterpart_public_context": cls._counterpart_context(
                request.counterpart
            ),
            "recent_transcript": [
                message.model_dump(mode="json") for message in request.transcript[-8:]
            ],
            "guardrail_feedback_from_rejected_candidate": list(
                request.guardrail_feedback
            ),
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
