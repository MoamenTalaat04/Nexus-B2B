"""Comprehensive tests for the Mock API layer (USE_MOCK_API=true)."""

from __future__ import annotations

import io
from collections.abc import Generator

import openpyxl
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app
from app.mock_api.state import reset_store


@pytest.fixture
def mock_client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient]:
    monkeypatch.setattr(settings, "USE_MOCK_API", True)
    reset_store()
    app = create_app()
    with TestClient(app) as client:
        yield client


def _login(client: TestClient, email: str = "demo@littlestars.eg", password: str = "DemoPass123!") -> None:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text


def test_health_and_openapi(mock_client: TestClient) -> None:
    r1 = mock_client.get("/health")
    assert r1.status_code == 200
    assert r1.json()["mode"] == "mock"

    r2 = mock_client.get("/api/v1/health")
    assert r2.status_code == 200
    assert r2.json() == {"status": "ok", "db": "ok", "redis": "ok", "mode": "mock"}

    openapi = mock_client.get("/openapi.json")
    assert openapi.status_code == 200
    paths = openapi.json()["paths"]
    assert "/api/v1/leads" in paths
    assert "/api/v1/dashboard" in paths
    assert "/api/v1/outreach/queue" in paths

    docs = mock_client.get("/docs")
    assert docs.status_code == 200


def test_auth_lifecycle_and_unauthenticated(mock_client: TestClient) -> None:
    unauth = mock_client.get("/api/v1/auth/me")
    assert unauth.status_code == 401
    assert unauth.json()["error"]["code"] == "unauthorized"

    reg = mock_client.post(
        "/api/v1/auth/register",
        json={
            "email": "newowner@example.com",
            "password": "Password123!",
            "full_name": "Test Owner",
            "company_name": "New Co",
        },
    )
    assert reg.status_code == 201
    assert reg.json()["onboarding_completed"] is False

    dup = mock_client.post(
        "/api/v1/auth/register",
        json={
            "email": "newowner@example.com",
            "password": "Password123!",
            "full_name": "Test Owner",
            "company_name": "New Co",
        },
    )
    assert dup.status_code == 409

    me = mock_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "newowner@example.com"

    out = mock_client.post("/api/v1/auth/logout")
    assert out.status_code == 200
    assert mock_client.get("/api/v1/auth/me").status_code == 401

    _login(mock_client)
    me_demo = mock_client.get("/api/v1/auth/me")
    assert me_demo.status_code == 200
    assert me_demo.json()["tenant"]["name"] == "Little Stars Kids Wear"


def test_tenant_isolation(mock_client: TestClient) -> None:
    _login(mock_client, "demo@littlestars.eg", "DemoPass123!")
    t1_leads = mock_client.get("/api/v1/leads").json()
    assert t1_leads["total"] >= 30
    first_t1_lead_id = t1_leads["items"][0]["id"]

    # Switch to tenant 2
    _login(mock_client, "medtech@example.com", "MedTech123!")
    t2_leads = mock_client.get("/api/v1/leads").json()
    assert t2_leads["total"] == 1
    assert mock_client.get(f"/api/v1/leads/{first_t1_lead_id}").status_code == 404


def test_settings_and_geo(mock_client: TestClient) -> None:
    geo = mock_client.get("/api/v1/settings/geo")
    assert geo.status_code == 200
    assert any(g["name"] == "Cairo" for g in geo.json()["governorates"])

    _login(mock_client)
    s = mock_client.get("/api/v1/settings")
    assert s.status_code == 200
    assert s.json()["company_name"] == "Little Stars Kids Wear"

    upd = mock_client.put(
        "/api/v1/settings",
        json={"daily_send_cap": 35, "demo_whitelist": ["01012345678"]},
    )
    assert upd.status_code == 200
    assert upd.json()["daily_send_cap"] == 35
    assert upd.json()["demo_whitelist"] == ["+201012345678"]


def test_knowledge_crud(mock_client: TestClient) -> None:
    _login(mock_client)
    initial = mock_client.get("/api/v1/knowledge").json()
    assert initial["total"] == 2

    upload = mock_client.post(
        "/api/v1/knowledge",
        files={"file": ("notes.md", "# كتالوج جديد\nأسعار الجملة 2026".encode(), "text/markdown")},
    )
    assert upload.status_code == 201
    doc_id = upload.json()["id"]
    assert upload.json()["status"] == "ready"

    detail = mock_client.get(f"/api/v1/knowledge/{doc_id}")
    assert detail.status_code == 200
    assert "أسعار الجملة" in detail.json()["extracted_text"]

    delete = mock_client.delete(f"/api/v1/knowledge/{doc_id}")
    assert delete.status_code == 204


def test_icp_lifecycle(mock_client: TestClient) -> None:
    _login(mock_client)
    active = mock_client.get("/api/v1/icp/active")
    assert active.status_code == 200
    assert active.json()["version"] == 3

    gen = mock_client.post("/api/v1/icp/generate")
    assert gen.status_code == 202
    run_id = gen.json()["run_id"]

    # Poll run until succeeded
    for _ in range(3):
        r = mock_client.get(f"/api/v1/runs/{run_id}").json()
        if r["status"] == "succeeded":
            break
    assert r["status"] == "succeeded"

    new_active = mock_client.get("/api/v1/icp/active").json()
    assert new_active["version"] == 4

    put_resp = mock_client.put(
        "/api/v1/icp/active",
        json={
            "company_profile": new_active["company_profile"],
            "icp": new_active["icp"],
            "notes": "Edited by owner",
        },
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["version"] == 5
    assert put_resp.json()["source"] == "user"


def test_leads_filters_stats_and_export(mock_client: TestClient) -> None:
    _login(mock_client)
    stats = mock_client.get("/api/v1/leads/stats").json()
    assert stats["total"] == 36
    assert stats["counts"]["won"] == 2

    filtered = mock_client.get("/api/v1/leads?status=interested&status=won&min_score=8").json()
    assert filtered["total"] >= 3
    assert all(item["status"] in {"interested", "won"} for item in filtered["items"])

    search_ar = mock_client.get("/api/v1/leads?q=كيدز").json()
    assert search_ar["total"] >= 1

    xlsx = mock_client.get("/api/v1/leads/export.xlsx")
    assert xlsx.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(xlsx.content))
    assert wb.active is not None
    assert wb.active.max_row == 37


def test_sourcing_lifecycle(mock_client: TestClient) -> None:
    _login(mock_client)
    before_total = mock_client.get("/api/v1/leads/stats").json()["total"]

    trig = mock_client.post("/api/v1/runs/sourcing", json={"max_results": 20})
    assert trig.status_code == 202
    run_id = trig.json()["run_id"]

    # Duplicate trigger while running -> 409
    conflict = mock_client.post("/api/v1/runs/sourcing", json={"max_results": 20})
    assert conflict.status_code == 409

    for _ in range(3):
        r = mock_client.get(f"/api/v1/runs/{run_id}").json()
        if r["status"] == "succeeded":
            break
    assert r["status"] == "succeeded"
    assert len(r["steps"]) >= 3

    after_total = mock_client.get("/api/v1/leads/stats").json()["total"]
    assert after_total > before_total


def test_outreach_and_assisted(mock_client: TestClient) -> None:
    _login(mock_client)
    q = mock_client.get("/api/v1/outreach/queue").json()
    assert q["total"] == 3
    first_id = q["items"][0]["id"]
    second_id = q["items"][1]["id"]

    app_resp = mock_client.post(f"/api/v1/outreach/messages/{first_id}/approve", json={})
    assert app_resp.status_code == 200
    assert app_resp.json()["status"] == "sent"

    rej_resp = mock_client.post(f"/api/v1/outreach/messages/{second_id}/reject")
    assert rej_resp.status_code == 200
    assert rej_resp.json()["status"] == "rejected"

    assisted = mock_client.get("/api/v1/outreach/assisted").json()
    assert assisted["total"] == 2
    assert assisted["items"][0]["wa_link"].startswith("https://wa.me/")
    a_id = assisted["items"][0]["id"]

    sent_resp = mock_client.post(f"/api/v1/outreach/messages/{a_id}/mark-sent", json={})
    assert sent_resp.status_code == 200
    assert sent_resp.json()["status"] == "sent"


def test_crm_and_reply_simulation(mock_client: TestClient) -> None:
    _login(mock_client)
    leads = mock_client.get("/api/v1/leads?status=contacted").json()["items"]
    lead_id = leads[0]["id"]

    note = mock_client.post(f"/api/v1/leads/{lead_id}/notes", json={"body": "عميل مهم في الزمالك"})
    assert note.status_code == 201

    # No open 24h window yet -> 409 window_closed
    closed = mock_client.post(f"/api/v1/leads/{lead_id}/messages", json={"body": "مرحبا"})
    assert closed.status_code == 409
    assert closed.json()["error"]["code"] == "window_closed"

    # Simulate inbound reply -> opens 24h window + classifies + escalates
    sim = mock_client.post(
        "/api/v1/mock/simulate-inbound",
        json={"lead_id": lead_id, "text": "مهتم جداً، ابعتلي الأسعار لو سمحت"},
    )
    assert sim.status_code == 200
    assert sim.json()["intent"] == "interested"
    assert sim.json()["escalated"] is True

    # Now manual message inside 24h window succeeds
    open_msg = mock_client.post(f"/api/v1/leads/{lead_id}/messages", json={"body": "تم إرسال الكتالوج"})
    assert open_msg.status_code == 201

    # Record won outcome
    outcome = mock_client.post(
        f"/api/v1/leads/{lead_id}/outcome",
        json={"outcome": "won", "value_egp": 35000, "reason": "Confirmed order"},
    )
    assert outcome.status_code == 201
    assert mock_client.get(f"/api/v1/leads/{lead_id}").json()["status"] == "won"


def test_notifications_dashboard_reports_and_reset(mock_client: TestClient) -> None:
    _login(mock_client)
    notifs = mock_client.get("/api/v1/notifications").json()
    assert notifs["unread_count"] >= 1
    nid = notifs["items"][0]["id"]

    mock_client.post(f"/api/v1/notifications/{nid}/read")
    mock_client.post("/api/v1/notifications/read-all")
    assert mock_client.get("/api/v1/notifications").json()["unread_count"] == 0

    dash = mock_client.get("/api/v1/dashboard").json()
    assert dash["kpis"]["total_leads"] == 36
    assert dash["agent"]["enabled"] is True

    rep_summary = mock_client.get("/api/v1/reports/summary").json()
    assert rep_summary["current"]["sourced"] == 36

    assert mock_client.get("/api/v1/reports/funnel").status_code == 200
    assert mock_client.get("/api/v1/reports/segments?by=governorate").status_code == 200
    assert mock_client.get("/api/v1/reports/costs").status_code == 200
    assert mock_client.get("/api/v1/reports/timeseries?metric=sourced").status_code == 200

    ins = mock_client.get("/api/v1/insights").json()
    assert ins["active"]["version"] == 2

    run_ins = mock_client.post("/api/v1/insights/run")
    assert run_ins.status_code == 202
    assert run_ins.json()["version"] == 3

    reset = mock_client.post("/api/v1/mock/reset")
    assert reset.status_code == 200
    assert mock_client.get("/api/v1/insights").json()["active"]["version"] == 2
