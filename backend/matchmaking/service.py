"""Matchmaking engine — evaluates agent compatibility and orchestrates sessions.

Operates on persisted ``AgentProfileRow`` and ``NegotiationStateRow``
records via SQLModel.  Does not import the AI engine or transport adapters.
"""

from __future__ import annotations

from uuid import UUID

from sqlmodel import Session, select

from persistence.models import AgentProfileRow, NegotiationStateRow


def find_matches(
    candidate_agent_id: UUID,
    *,
    session: Session,
    limit: int = 10,
) -> list[AgentProfileRow]:
    """Return available agents whose capabilities satisfy the candidate's interests.

    The candidate must have at least one ``interests`` tag that appears in
    the counterpart's ``capabilities``.  Excludes the candidate itself,
    agents that are not ``AVAILABLE``, and agents with an active
    negotiation against the candidate.
    """
    candidate = session.get(AgentProfileRow, candidate_agent_id)
    if candidate is None:
        raise ValueError(f"unknown agent: {candidate_agent_id}")
    if candidate.status != "AVAILABLE":
        return []

    interests = set(candidate.interests or [])
    if not interests:
        return []

    # Agents already negotiating with this candidate
    active_stmt = select(NegotiationStateRow.agent_1_id, NegotiationStateRow.agent_2_id).where(
        NegotiationStateRow.status.in_(["ACTIVE", "SEARCHING", "PENDING_HUMAN_APPROVAL"]),
    )
    active_rows = session.exec(active_stmt).all()
    excluded_ids: set[UUID] = {candidate_agent_id}
    for a1, a2 in active_rows:
        if a1 == candidate_agent_id:
            excluded_ids.add(a2)
        elif a2 == candidate_agent_id:
            excluded_ids.add(a1)

    # Collect available agents and filter in Python for tag intersection
    available_stmt = select(AgentProfileRow).where(
        AgentProfileRow.status == "AVAILABLE",
    )
    available = session.exec(available_stmt).all()

    matches: list[AgentProfileRow] = []
    for agent in available:
        if agent.agent_id in excluded_ids:
            continue
        caps = set(agent.capabilities or [])
        if interests & caps:
            matches.append(agent)
            if len(matches) >= limit:
                break

    return matches
