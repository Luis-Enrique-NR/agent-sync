"""Resolution store for private value references used during the demo.

In production this is replaced by an encrypted vault.  For the MVP the
fixtures are static data keyed by agent_id.
"""

from __future__ import annotations

from uuid import UUID

from sqlmodel import Session, select

from persistence.models import PrivateResolutionRow

PRIVATE_FIXTURES: dict[str, dict[str, tuple[str, str]]] = {
    "10000000-0000-0000-0000-000000000001": {
        "contact_ref_ecotextiles_sales": ("EMAIL", "ventas@ecotextiles.com"),
    },
    "20000000-0000-0000-0000-000000000001": {
        "contact_ref_valentina_phone": ("PHONE", "+57 300 123 4567"),
        "location_ref_public_meeting_point": (
            "MEETING_POINT",
            "Parque Principal, frente a la fuente",
        ),
    },
}


def resolve_private(agent_id: str, value_ref: str) -> str | None:
    agent_store = PRIVATE_FIXTURES.get(agent_id)
    if agent_store is None:
        return None
    entry = agent_store.get(value_ref)
    if entry is None:
        return None
    _category, real_value = entry
    return real_value


def seed_private_resolutions(session: Session) -> int:
    """Populate ``private_resolutions`` from the static fixture data.

    Existing rows are skipped so the seeder is safe to call on every
    ``init_db()``.  Returns the number of newly inserted rows.
    """
    inserted = 0
    for agent_id_str, refs in PRIVATE_FIXTURES.items():
        agent_id = UUID(agent_id_str)
        for value_ref, (category, real_value) in refs.items():
            existing = session.exec(
                select(PrivateResolutionRow).where(
                    PrivateResolutionRow.agent_id == agent_id,
                    PrivateResolutionRow.value_ref == value_ref,
                )
            ).first()
            if existing is not None:
                continue
            session.add(
                PrivateResolutionRow(
                    agent_id=agent_id,
                    value_ref=value_ref,
                    category=category,
                    real_value=real_value,
                )
            )
            inserted += 1
    if inserted:
        session.commit()
    return inserted
