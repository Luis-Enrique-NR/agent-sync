"""SQLite engine and session factory for AgentSync persistence."""

from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "agentsync.db"
DATABASE_URL = f"sqlite:///{DEFAULT_DB_PATH}"

engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})


def get_session() -> Session:
    return Session(engine)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    from persistence.fixtures import seed_private_resolutions

    with Session(engine) as session:
        seed_private_resolutions(session)
