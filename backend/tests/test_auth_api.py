"""Tests for P0-4 real auth API & JWT/Argon2 security helpers."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from httpx import AsyncClient

from app.config import settings
from app.core.security import COOKIE_NAME, JWT_ALGORITHM


async def test_register_login_me_and_logout_flow(client: AsyncClient) -> None:
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "Owner@Example.com",
            "password": "StrongPassword123!",
            "full_name": "Ahmed Hassan",
            "company_name": "Cairo Kids",
        },
    )
    assert reg.status_code == 201, reg.text
    body = reg.json()
    assert body["user"]["email"] == "owner@example.com"
    assert body["user"]["role"] == "owner"
    assert body["tenant"]["name"] == "Cairo Kids"
    assert body["onboarding_completed"] is False

    # Verify httpOnly & SameSite=Lax cookie flags
    set_cookie = reg.headers.get("set-cookie", "").lower()
    assert f"{COOKIE_NAME}=" in set_cookie
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie

    me_res = await client.get("/api/v1/auth/me")
    assert me_res.status_code == 200
    assert me_res.json()["user"]["email"] == "owner@example.com"

    logout_res = await client.post("/api/v1/auth/logout")
    assert logout_res.status_code == 200
    assert await client.get("/api/v1/auth/me") is not None
    unauth = await client.get("/api/v1/auth/me")
    assert unauth.status_code == 401

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "StrongPassword123!"},
    )
    assert login_res.status_code == 200
    assert login_res.json()["tenant"]["name"] == "Cairo Kids"


async def test_register_duplicate_email_returns_409(client: AsyncClient) -> None:
    payload = {
        "email": "dup@example.com",
        "password": "StrongPassword123!",
        "full_name": "Dup User",
        "company_name": "Dup Co",
    }
    first = await client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "email_taken"


async def test_login_wrong_password_returns_401(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "wrongpw@example.com",
            "password": "CorrectPassword123!",
            "full_name": "User",
            "company_name": "Co",
        },
    )
    await client.post("/api/v1/auth/logout")

    bad = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpw@example.com", "password": "WrongPassword!"},
    )
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "invalid_credentials"


async def test_rejects_expired_and_forged_jwt_tokens(client: AsyncClient) -> None:
    expired = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "tid": str(uuid.uuid4()),
            "role": "owner",
            "exp": int((datetime.now(UTC) - timedelta(hours=1)).timestamp()),
        },
        settings.JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.set(COOKIE_NAME, expired)
    res_expired = await client.get("/api/v1/auth/me")
    assert res_expired.status_code == 401

    forged = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "tid": str(uuid.uuid4()),
            "role": "owner",
            "exp": int((datetime.now(UTC) + timedelta(days=1)).timestamp()),
        },
        "completely-wrong-secret",
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.set(COOKIE_NAME, forged)
    res_forged = await client.get("/api/v1/auth/me")
    assert res_forged.status_code == 401


async def test_forgot_password_returns_ok(client: AsyncClient) -> None:
    res = await client.post("/api/v1/auth/forgot-password", json={"email": "anyone@example.com"})
    assert res.status_code == 200
    assert res.json()["ok"] is True
