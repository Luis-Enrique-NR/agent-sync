"""Configurable SQLModel engine and session factory."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from sqlmodel import Session, SQLModel, create_engine

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "agentsync.db"


def build_engine(database_url: str | None = None) -> Any:
    url = database_url or os.getenv(
        "AGENTSYNC_DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}"
    )
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, echo=False, connect_args=connect_args)


engine = build_engine()


def get_session() -> Session:
    return Session(engine)


def init_db() -> None:
    # Importing models registers all tables before create_all.
    from persistence import models as _models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    from persistence.fixtures import seed_private_resolutions

    with Session(engine) as session:
        seed_private_resolutions(session)
