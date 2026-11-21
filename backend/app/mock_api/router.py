"""Main router for the Mock API mode, mounted under /api/v1 when USE_MOCK_API=true."""

from fastapi import APIRouter

from app.mock_api.routes import (
    auth,
    channels,
    dashboard,
    icp,
    knowledge,
    leads,
    notifications,
    outreach,
    reports,
    runs,
    settings,
)
from app.mock_api.state import get_store


def build_mock_router() -> APIRouter:
    # Ensure deterministic seed data is initialized
    get_store()

    api = APIRouter(prefix="/api/v1")

    @api.get("/health", tags=["health"])
    async def mock_health() -> dict[str, str]:
        return {"status": "ok", "db": "ok", "redis": "ok", "mode": "mock"}

    api.include_router(auth.router)
    api.include_router(settings.router)
    api.include_router(knowledge.router)
    api.include_router(icp.router)
    api.include_router(runs.router)
    api.include_router(leads.router)
    api.include_router(outreach.router)
    api.include_router(channels.router)
    api.include_router(notifications.router)
    api.include_router(dashboard.router)
    api.include_router(reports.router)

    return api
