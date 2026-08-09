"""OpenAI Responses API adapter with Pydantic Structured Outputs."""

from __future__ import annotations

import json

from openai import OpenAI

from ai.domain.models import (
    AgentProfile,
    ProviderStep,
    ToolFactVisibility,
    TranscriptMessage,
)
from ai.providers.base import GenerationRequest


SYSTEM_INSTRUCTIONS = """You represent one entity in a preliminary negotiation.
Return exactly one step using the supplied schema: either TOOL_CALL or TURN.
Stay faithful to the speaker objectives, personality, hard limits, and known facts.
Never invent contact details, addresses, locations, dates, prices, or tool results.
Use TOOL_CALL only for a capability listed in available_tools and supply only its
documented arguments. A tool request is internal and must not contain public speech.
After a tool result, use it as private context; never present simulated data as real.
Do not retry a rejected or denied tool call unless new conversation context requires it.
External writes can require human approval. Requesting a tool never authorizes it.
Every numeric proposal or commitment must also appear in numeric_terms.
When proposing or accepting a date, include it in commitments with kind DATE.
Use ACCEPT only when accepting explicit terms already present in the conversation.
Use data_requests only to ask the counterpart for a protected data category.
Data requests never contain value_ref because the requested data belongs to the counterpart.
Use proposed_disclosures only when the speaker intends to share its own protected data.
A proposed disclosure must use a value_ref from speaker_private_context.
Never reuse, copy, or invent a value_ref from another agent or a prior message.
Never place an opaque value_ref or an actual protected value in public_message.
For a proposed disclosure, say the information can be shared after authorization.
Use requested_actions only to ask the counterpart to perform a structured action.
Meeting, reservation, document, and email requests must never be hidden only in prose.
Do not claim that a requested action was approved unless human_action_authorizations
contains an approved record for that action_id.
If an authorization is rejected, acknowledge that outcome without executing the action.
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
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._model = model
        self._max_output_tokens = max_output_tokens
        if client is not None:
            self._client = client
        else:
            client_options: dict[str, object] = {
                "timeout": timeout_seconds,
                "max_retries": max_retries,
            }
            if api_key:
                client_options["api_key"] = api_key
            if base_url:
                client_options["base_url"] = base_url
            self._client = OpenAI(**client_options)

    @property
    def model(self) -> str:
        return self._model

    def generate_step(self, request: GenerationRequest) -> ProviderStep:
        prompt = self._build_prompt(request)
        schema = ProviderStep.model_json_schema()
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTIONS},
                {"role": "user", "content": prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "ProviderStep",
                    "schema": schema,
                },
            },
            max_tokens=self._max_output_tokens,
            temperature=0.2,
        )
        raw = response.choices[0].message.content
        if not raw:
            raise RuntimeError("model returned empty response")
        return ProviderStep.model_validate_json(raw)

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

    @staticmethod
    def _public_transcript_message(
        message: TranscriptMessage,
    ) -> dict[str, object]:
        """Serialize only fields safe to expose to the next model/agent."""

        return {
            "speaker_id": str(message.speaker_id),
            "turn_index": message.turn_index,
            "proposal_id": str(message.proposal_id),
            "proposal_revision": message.proposal_revision,
            "responds_to": (
                message.responds_to.model_dump(mode="json")
                if message.responds_to
                else None
            ),
            "public_message": message.public_message,
            "intent": message.intent.value,
            "numeric_terms": [
                term.model_dump(mode="json") for term in message.numeric_terms
            ],
            "data_requests": [
                request.model_dump(mode="json") for request in message.data_requests
            ],
            "disclosed_categories": [
                category.value for category in message.disclosed_categories
            ],
            "requested_actions": [
                action.model_dump(mode="json") for action in message.requested_actions
            ],
            "created_at": message.created_at.isoformat(),
            "approved_by_human": message.approved_by_human,
        }

    @classmethod
    def _build_prompt(cls, request: GenerationRequest) -> str:
        payload = {
            "speaker_private_context": cls._speaker_context(request.speaker),
            "counterpart_public_context": cls._counterpart_context(
                request.counterpart
            ),
            "recent_transcript": [
                cls._public_transcript_message(message)
                for message in request.transcript[-8:]
            ],
            "human_action_authorizations": [
                authorization.model_dump(mode="json")
                for authorization in request.action_authorizations
            ],
            "available_tools": [
                descriptor.model_dump(mode="json")
                for descriptor in request.available_tools
            ],
            "private_tool_results": [
                result.model_dump(mode="json") for result in request.tool_results
            ],
            "guardrail_feedback_from_rejected_candidate": list(
                request.guardrail_feedback
            ),
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
