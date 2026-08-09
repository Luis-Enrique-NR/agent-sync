"""API v1 router — aggregates all endpoint routers."""

from fastapi import APIRouter

from api.v1.endpoints.agents import router as agents_router
from api.v1.endpoints.negotiations import router as negotiations_router
from api.v1.endpoints.sse import router as sse_router

router = APIRouter(prefix="/api/v1")
router.include_router(agents_router)
router.include_router(negotiations_router)
router.include_router(sse_router)
