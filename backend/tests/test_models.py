from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from ai.domain.models import (
    EscalationRule,
    EscalationRuleType,
    ExternalSessionEvent,
    ExternalSessionEventType,
    GoalCompletionMode,
    ProviderStep,
    ProviderStepKind,
    SensitiveDataCategory,
    ToolFact,
    ToolFactVisibility,
    ToolDescriptor,
    ToolRiskLevel,
)
from ai.mocks import load_scenario


def test_private_fact_cannot_contain_a_secret_value() -> None:
    with pytest.raises(ValidationError):
        ToolFact(
            key="phone",
            visibility=ToolFactVisibility.PRIVATE_REFERENCE,
            value="+57 300 123 4567",
            value_ref="phone_ref",
            category=SensitiveDataCategory.PHONE,
        )


def test_b2b_and_p2p_fixtures_share_the_same_schema() -> None:
    b2b = load_scenario("b2b")
    p2p = load_scenario("p2p")

    assert len(b2b.agents) == 2
    assert len(p2p.agents) == 2
    assert b2b.agents[0].entity_type.value == "company"
    assert p2p.agents[0].entity_type.value == "person"


def test_scenario_loader_rejects_path_traversal() -> None:
    with pytest.raises(ValueError):
        load_scenario("../p2p")


def test_request_action_rule_requires_explicit_action_types() -> None:
    with pytest.raises(ValidationError, match="REQUEST_ACTION"):
        EscalationRule(
            rule_id="approve-actions",
            rule_type=EscalationRuleType.REQUEST_ACTION,
        )


def test_quantity_goal_requires_remaining_units(p2p_agents) -> None:
    seller, _ = p2p_agents

    with pytest.raises(ValidationError, match="remaining_goal_units"):
        type(seller).model_validate(
            {
                **seller.model_dump(mode="json"),
                "goal_completion_mode": GoalCompletionMode.QUANTITY,
                "remaining_goal_units": None,
            }
        )


def test_external_event_requires_timezone_aware_timestamp(p2p_agents) -> None:
    seller, _ = p2p_agents

    with pytest.raises(ValidationError, match="timezone-aware"):
        ExternalSessionEvent(
            session_id=seller.agent_id,
            actor_agent_id=seller.agent_id,
            event_type=ExternalSessionEventType.COUNTERPART_WITHDREW,
            occurred_at=datetime(2026, 8, 8, 12, 0),
        )


def test_external_write_tool_cannot_disable_mandatory_approval() -> None:
    with pytest.raises(ValidationError, match="must require human approval"):
        ToolDescriptor(
            name="email.send_notification",
            description="Send an external notification.",
            risk_level=ToolRiskLevel.EXTERNAL_WRITE,
            requires_human_approval=False,
        )


def test_provider_step_requires_exactly_one_output_kind() -> None:
    with pytest.raises(ValidationError, match="TURN steps"):
        ProviderStep(kind=ProviderStepKind.TURN)


def test_agent_rejects_duplicate_tool_grants(p2p_agents) -> None:
    seller, _ = p2p_agents
    duplicate_grant = seller.tool_grants[0].model_dump(mode="json")

    with pytest.raises(ValidationError, match="tool grants must be unique"):
        type(seller).model_validate(
            {
                **seller.model_dump(mode="json"),
                "tool_grants": [
                    *seller.model_dump(mode="json")["tool_grants"],
                    duplicate_grant,
                ],
            }
        )
