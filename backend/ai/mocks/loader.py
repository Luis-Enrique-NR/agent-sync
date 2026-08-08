"""Load validated demo profiles without coupling the engine to a vertical."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import Field

from ai.domain.models import AgentProfile, StrictModel


class DemoScenario(StrictModel):
    scenario_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=160)
    agents: tuple[AgentProfile, AgentProfile]


def load_scenario(name: str) -> DemoScenario:
    if not name or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for character in name):
        raise ValueError("scenario name contains unsupported characters")
    path = Path(__file__).with_name(f"{name}.json")
    if not path.is_file():
        raise FileNotFoundError(f"unknown demo scenario: {name}")
    return DemoScenario.model_validate(json.loads(path.read_text(encoding="utf-8")))
