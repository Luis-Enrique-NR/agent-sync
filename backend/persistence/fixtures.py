"""Safe, repeatable private-reference fixtures for local demonstrations."""

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


def seed_private_resolutions(session: Session) -> int:
    inserted = 0
    for agent_id_text, references in PRIVATE_FIXTURES.items():
        agent_id = UUID(agent_id_text)
        for value_ref, (category, real_value) in references.items():
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
