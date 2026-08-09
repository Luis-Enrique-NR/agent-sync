"""AgentSync backend entry point.

Loads environment, wires transport + AI dependencies, starts the FastAPI
application with an EDA consumer running in the same event loop.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os

import redis.asyncio as redis
import uvicorn
from dotenv import load_dotenv

from ai.service import build_engine_from_env
from api.app import create_app
from api.v1.endpoints.sse import SessionQueueManager
from eda.consumer import consume_forever
from eda.handlers import NegotiationHandler
from transport.config import TransportSettings
from transport.portal import HttpPortalClient
from transport.redis_bus import RedisStreamsEventBus
from transport.secret_fetcher import WebhookSecretFetcher

logger = logging.getLogger(__name__)
_CONSUMER_NAME = "eda-consumer"


def _build_app() -> "FastAPI":  # noqa: F821
    """Wire all dependencies and return the application."""

    load_dotenv(override=False)

    from persistence.database import init_db
    init_db()
    _seed_startup_agents()

    settings = TransportSettings.from_env()

    secret_key = os.getenv("PORTAL_SECRET_KEY")
    if not secret_key:
        raise RuntimeError(
            "PORTAL_SECRET_KEY is required — set it in .env or the environment"
        )

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_conn = redis.from_url(redis_url)

    # Lazy webhook secret fetcher (implements WebhookSecretProvider)
    secret_provider = WebhookSecretFetcher(secret_key=secret_key)

    # Durable event bus backed by Redis Streams
    bus = RedisStreamsEventBus(redis_conn)

    # AI negotiation engine (reads AI_* env vars from .env)
    engine = build_engine_from_env()

    # Portal mutation client (uses the same secret key as Bearer token)
    portal_client = HttpPortalClient(secret=secret_key)

    # ── SSE broadcaster shared between handler and API ──────────────
    sse_broadcaster = SessionQueueManager()

    # Handler bridges bus deliveries → engine + Portal + SSE
    handler = NegotiationHandler(
        engine=engine, portal=portal_client, sse_broadcaster=sse_broadcaster,
    )

    # FastAPI application with injected transport deps
    app = create_app(
        settings=settings,
        secret_provider=secret_provider,
        bus=bus,
        portal_secret=secret_key,
        sse_broadcaster=sse_broadcaster,
    )
    app.state.engine = engine

    @contextlib.asynccontextmanager
    async def _lifespan(app: "FastAPI") -> "AsyncIterator[None]":  # noqa: F821
        task = asyncio.create_task(
            consume_forever(bus, _CONSUMER_NAME, handler)
        )
        logger.info("EDA consumer %r started", _CONSUMER_NAME)
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.info("EDA consumer %r shut down gracefully", _CONSUMER_NAME)

    app.router.lifespan_context = _lifespan  # type: ignore[assignment]
    return app


def _seed_startup_agents() -> None:
    """Create guaranteed demo agents if they do not already exist."""
    from persistence.database import get_session
    from persistence.repository import create_agent_profile
    from persistence.models import AgentProfileRow
    from ai.domain.models import AgentProfile, EntityType, AgentStatus
    from sqlmodel import select
    from uuid import UUID, uuid4

    session = get_session()
    try:
        names = {
            r.display_name
            for r in session.exec(select(AgentProfileRow)).all()
        }
        seeded = 0

        # Agent 1: Furniture Seller
        if "Muebles & Diseno Corp" not in names:
            a1 = AgentProfile(
                agent_id=UUID("e0000000-0000-0000-0000-000000000001"),
                display_name="Muebles & Diseno Corp",
                entity_type=EntityType.COMPANY,
                public_description="Proveedor mayorista y minorista de mobiliario ergonomico de oficina y hogar.",
                personality="Profesional, orientado a ventas corporativas.",
                objectives=["Vender mobiliario de oficina", "Equipar empresas"],
                interests=["VENTAS_CORPORATIVAS", "EQUIPAMIENTO_OFICINA"],
                capabilities=["MUEBLES_OFICINA", "ESCRITORIOS_ELEVABLES", "SILLAS_ERGONOMICAS",
                              "ESTANTERIA", "ENVIO_NACIONAL"],
                status=AgentStatus.AVAILABLE,
            )
            create_agent_profile(a1, user_id=uuid4(), session=session)
            seeded += 1

        # Agent 2: Tech Recruiter
        if "TechTalent - Reclutamiento IT" not in names:
            a2 = AgentProfile(
                agent_id=UUID("e0000000-0000-0000-0000-000000000002"),
                display_name="TechTalent - Reclutamiento IT",
                entity_type=EntityType.COMPANY,
                public_description="Busqueda activa de Ingeniero Full Stack Senior para incorporacion inmediata.",
                personality="Reclutador tecnico, directo y eficiente.",
                objectives=["Contratar Senior Full Stack", "Cubrir vacante urgente"],
                interests=["PYTHON", "FASTAPI", "REACT", "NEXTJS", "TYPESCRIPT",
                           "POSTGRESQL", "REDIS", "DOCKER", "AWS", "TAILWIND"],
                capabilities=["CONTRATACION_INMEDIATA", "TRABAJO_REMOTO_100",
                              "PAGO_USD", "BENEFICIOS_SALUD"],
                status=AgentStatus.AVAILABLE,
            )
            create_agent_profile(a2, user_id=uuid4(), session=session)
            seeded += 1

        # Agent 3: TechCorp recruiter — matches SEARCH JOB
        if "TechCorp - Oferta Laboral Fullstack" not in names:
            a3 = AgentProfile(
                agent_id=UUID("e0000000-0000-0000-0000-000000000003"),
                display_name="TechCorp - Oferta Laboral Fullstack",
                entity_type=EntityType.COMPANY,
                public_description="Empresa de software buscando Ingeniero Cloud / Fullstack en planilla.",
                personality="Reclutador corporativo, ofrece estabilidad laboral.",
                objectives=["Contratar Ingeniero Cloud Fullstack", "Posicion en planilla con beneficios"],
                interests=["AZURE", "AWS", "TYPESCRIPT", "CLOUD", ".NET", "JAVA"],
                capabilities=["CONTRATO PLANILLA", "CLOUD", "TRABAJO_REMOTO_100",
                              "SEGURO_SALUD", "BONO_ANUAL"],
                status=AgentStatus.AVAILABLE,
            )
            create_agent_profile(a3, user_id=uuid4(), session=session)
            seeded += 1

        if seeded:
            session.commit()
            logger.info("[SEED] %d startup agents created", seeded)
    finally:
        session.close()


app = _build_app()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
