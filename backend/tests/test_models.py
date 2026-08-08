from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai.domain.models import SensitiveDataCategory, ToolFact, ToolFactVisibility
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
