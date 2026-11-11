from fastapi import APIRouter
from httpx import ASGITransport, AsyncClient

from app.core.errors import AppError
from app.main import create_app
from app.workers.main import WorkerSettings, discover_jobs


async def test_health_reports_db_and_redis(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "db": "ok", "redis": "ok"}


async def test_unknown_route_uses_error_shape(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


async def test_app_error_and_validation_error_shapes() -> None:
    application = create_app()
    extra = APIRouter()

    @extra.get("/boom")
    async def boom() -> None:
        raise AppError("window_closed", "closed", status_code=409)

    @extra.get("/needs-int")
    async def needs_int(n: int) -> int:
        return n

    application.include_router(extra)
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://t") as ac:
        r = await ac.get("/boom")
        assert r.status_code == 409
        assert r.json() == {"error": {"code": "window_closed", "message": "closed"}}

        r = await ac.get("/needs-int", params={"n": "x"})
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "validation_error"


def test_job_functions_are_discovered() -> None:
    functions, _ = discover_jobs()
    names = {f.__name__ for f in functions}
    assert "job_ping" in names
    assert all(name.startswith("job_") for name in names)


def test_worker_uses_cairo_time() -> None:
    assert str(WorkerSettings.timezone) == "Africa/Cairo"
