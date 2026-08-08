"""Matchmaking engine — evaluates agent compatibility and orchestrates sessions.

Operates on persisted ``AgentProfileRow`` and ``NegotiationStateRow``
records via SQLModel.  Does not import the AI engine or transport adapters.
"""

from __future__ import annotations

from uuid import UUID

from sqlmodel import Session, select

from ai.domain.models import AgentProfile
from matchmaking.evaluator import calculate_match_score
from persistence.models import AgentProfileRow, NegotiationStateRow


def find_matches(
    candidate_agent_id: UUID,
    *,
    session: Session,
    limit: int = 10,
) -> list[AgentProfileRow]:
    """Return available agents ranked by bidirectional compatibility score.

    Candidates are filtered by:
    - Status ``AVAILABLE``
    - Score > 0.0 (no hard-filter conflicts, at least one tag intersection)
    - No active negotiation against the candidate

    Results are ordered from highest to lowest score.
    """
    candidate_row = session.get(AgentProfileRow, candidate_agent_id)
    if candidate_row is None:
        raise ValueError(f"unknown agent: {candidate_agent_id}")
    if candidate_row.status != "AVAILABLE":
        return []

    candidate = AgentProfile.model_validate(candidate_row.raw_profile)

    # Agents already negotiating with this candidate
    active_stmt = select(
        NegotiationStateRow.agent_1_id, NegotiationStateRow.agent_2_id
    ).where(
        NegotiationStateRow.status.in_(["ACTIVE", "SEARCHING", "PENDING_HUMAN_APPROVAL"]),
    )
    active_rows = session.exec(active_stmt).all()
    excluded_ids: set[UUID] = {candidate_agent_id}
    for a1, a2 in active_rows:
        if a1 == candidate_agent_id:
            excluded_ids.add(a2)
        elif a2 == candidate_agent_id:
            excluded_ids.add(a1)

    # Collect all available agents
    available_stmt = select(AgentProfileRow).where(
        AgentProfileRow.status == "AVAILABLE",
    )
    available = session.exec(available_stmt).all()

    # Score and rank
    scored: list[tuple[float, AgentProfileRow]] = []
    for row in available:
        if row.agent_id in excluded_ids:
            continue
        counterpart = AgentProfile.model_validate(row.raw_profile)
        score = calculate_match_score(candidate, counterpart)
        if score > 0.0:
            scored.append((score, row))

    # Sort by score descending, then by agent_id for determinism
    scored.sort(key=lambda item: (-item[0], str(item[1].agent_id)))

    return [row for _score, row in scored[:limit]]
