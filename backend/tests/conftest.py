from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ai.mocks import load_scenario


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def b2b_agents():
    return load_scenario("b2b").agents


@pytest.fixture
def p2p_agents():
    return load_scenario("p2p").agents
