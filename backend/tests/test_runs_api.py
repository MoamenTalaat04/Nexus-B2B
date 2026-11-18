import uuid

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.tracing import agent_run, create_queued_run
from app.models.enums import AgentRunKind, StepType
from app.models.tenants import Tenant


def auth(tenant_id: uuid.UUID, secret: str | None = None) -> dict[str, str]:
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "tid": str(tenant_id), "role": "owner"},
        secret or settings.JWT_SECRET,
        algorithm="HS256",
    )
    return {"Cookie": f"access_token={token}"}


@pytest.fixture
async def tenants(session: AsyncSession) -> tuple[Tenant, Tenant]:
    a, b = Tenant(name="Factory A"), Tenant(name="Factory B")
    session.add_all([a, b])
    await session.flush()
    return a, b


async def make_run(tenant: Tenant, kind: AgentRunKind, *, fail: bool = False) -> uuid.UUID:
    try:
        async with agent_run(tenant.id, kind, trigger="manual", input={"k": kind.value}) as run:
            await run.step(StepType.LLM_CALL, "x.first", model="m", input_tokens=10, output_tokens=2)
            await run.step(StepType.DECISION, "x.second", output={"phone": "+201012345678"})
            if fail:
                raise RuntimeError("provider down")
    except RuntimeError:
        pass
    return run.run_id


async def test_list_is_tenant_scoped_newest_first_and_filterable(
    client: AsyncClient, session: AsyncSession, tenants: tuple[Tenant, Tenant]
) -> None:
    a, b = tenants
    first = await make_run(a, AgentRunKind.SCORING)
    second = await make_run(a, AgentRunKind.SOURCING, fail=True)
    queued = await create_queued_run(session, a.id, AgentRunKind.ICP_BUILD, trigger="manual", input={})
    await make_run(b, AgentRunKind.SCORING)

    resp = await client.get("/api/v1/runs", headers=auth(a.id))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    ids = [item["id"] for item in data["items"]]
    assert set(ids) == {str(first), str(second), str(queued)}
    assert ids.index(str(second)) < ids.index(str(first))  # newest first

    failed = next(i for i in data["items"] if i["id"] == str(second))
    assert failed["status"] == "failed"
    assert failed["error"] == "RuntimeError: provider down"
    assert failed["total_input_tokens"] == 10

    by_kind = (await client.get("/api/v1/runs?kind=scoring", headers=auth(a.id))).json()
    assert [i["id"] for i in by_kind["items"]] == [str(first)]
    by_status = (await client.get("/api/v1/runs?status=queued", headers=auth(a.id))).json()
    assert [i["id"] for i in by_status["items"]] == [str(queued)]
    paged = (await client.get("/api/v1/runs?page=2&page_size=2", headers=auth(a.id))).json()
    assert paged["total"] == 3 and len(paged["items"]) == 1


async def test_detail_returns_ordered_steps(client: AsyncClient, tenants: tuple[Tenant, Tenant]) -> None:
    a, _ = tenants
    run_id = await make_run(a, AgentRunKind.SCORING)
    resp = await client.get(f"/api/v1/runs/{run_id}", headers=auth(a.id))
    assert resp.status_code == 200
    run = resp.json()
    assert run["status"] == "succeeded"
    assert run["input"] == {"k": "scoring"}
    assert run["duration_ms"] is not None
    assert [s["seq"] for s in run["steps"]] == [1, 2]
    assert [s["name"] for s in run["steps"]] == ["x.first", "x.second"]
    assert run["steps"][0]["model"] == "m" and run["steps"][0]["input_tokens"] == 10
    assert run["steps"][1]["output"] == {"phone": "+*********678"}


async def test_other_tenants_run_is_not_found(client: AsyncClient, tenants: tuple[Tenant, Tenant]) -> None:
    a, b = tenants
    run_id = await make_run(b, AgentRunKind.SCORING)
    resp = await client.get(f"/api/v1/runs/{run_id}", headers=auth(a.id))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"
    assert (await client.get("/api/v1/runs", headers=auth(a.id))).json()["total"] == 0


async def test_requires_a_valid_session(client: AsyncClient, tenants: tuple[Tenant, Tenant]) -> None:
    a, _ = tenants
    resp = await client.get("/api/v1/runs")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"
    resp = await client.get("/api/v1/runs", headers=auth(a.id, secret="another-secret-of-32-bytes-length"))
    assert resp.status_code == 401


async def test_invalid_kind_is_a_validation_error(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    a, _ = tenants
    resp = await client.get("/api/v1/runs?kind=nope", headers=auth(a.id))
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"
