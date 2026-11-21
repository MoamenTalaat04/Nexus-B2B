"""Authentication & security helpers (CONTRACTS section 1: JWT in httpOnly cookie `access_token`)."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Request, Response

from app.config import settings
from app.core.errors import AppError

COOKIE_NAME = "access_token"
JWT_ALGORITHM = "HS256"
TOKEN_TTL_DAYS = 7

_ph = PasswordHasher()


@dataclass(frozen=True)
class CurrentUser:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: str


def _unauthorized(message: str = "Not authenticated") -> AppError:
    return AppError("unauthorized", message, status_code=401)


def hash_password(password: str) -> str:
    """Hash a password with Argon2id."""
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against an Argon2id hash."""
    try:
        return _ph.verify(password_hash, password)
    except (VerifyMismatchError, Exception):
        return False


def create_access_token(*, user_id: uuid.UUID, tenant_id: uuid.UUID, role: str) -> str:
    """Create a 7-day HS256 JWT with sub, tid, role claims."""
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "tid": str(tenant_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=TOKEN_TTL_DAYS)).timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=JWT_ALGORITHM)


def is_cookie_secure() -> bool:
    origin = settings.FRONTEND_ORIGIN.lower()
    return not (origin.startswith("http://localhost") or origin.startswith("http://127.0.0.1"))


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=is_cookie_secure(),
        max_age=TOKEN_TTL_DAYS * 24 * 60 * 60,
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=COOKIE_NAME,
        httponly=True,
        samesite="lax",
        secure=is_cookie_secure(),
        path="/",
    )


async def get_current_user(request: Request) -> CurrentUser:
    """FastAPI dependency: the user from the access_token cookie, or a 401 in the contract's error shape."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise _unauthorized()
    try:
        claims = jwt.decode(token, settings.JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return CurrentUser(
            user_id=uuid.UUID(str(claims["sub"])),
            tenant_id=uuid.UUID(str(claims["tid"])),
            role=str(claims.get("role", "member")),
        )
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise _unauthorized("Invalid or expired session") from exc


def is_auth0_configured() -> bool:
    return bool(settings.AUTH0_DOMAIN and settings.AUTH0_CLIENT_ID and settings.AUTH0_CLIENT_SECRET)


async def auth0_signup(*, email: str, password: str, full_name: str) -> dict[str, Any]:
    """Create user in Auth0 database connection without leaving NEXUS UI."""
    url = f"https://{settings.AUTH0_DOMAIN}/dbconnections/signup"
    payload = {
        "client_id": settings.AUTH0_CLIENT_ID,
        "email": email,
        "password": password,
        "connection": settings.AUTH0_CONNECTION,
        "name": full_name,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(url, json=payload)
    if res.status_code >= 400:
        data = res.json()
        raw_desc = data.get("description") or data.get("message") or "Auth0 registration failed"
        if isinstance(raw_desc, dict) and isinstance(raw_desc.get("rules"), list):
            unmet = [
                str(r.get("message", "")).replace("%d", str((r.get("format") or [""])[0]))
                for r in raw_desc["rules"]
                if isinstance(r, dict) and not r.get("verified", True)
            ]
            msg = "; ".join(m for m in unmet if m) or "Password does not meet security requirements."
        else:
            msg = str(raw_desc)
        status = 409 if "exists" in msg.lower() else 400
        raise AppError("auth0_signup_failed", msg, status_code=status)
    return dict(res.json())


async def auth0_password_login(*, email: str, password: str) -> dict[str, Any]:
    """Authenticate email/password via Auth0 Resource Owner Password Grant."""
    url = f"https://{settings.AUTH0_DOMAIN}/oauth/token"
    payload: dict[str, Any] = {
        "grant_type": "http://auth0.com/oauth/grant-type/password-realm",
        "username": email,
        "password": password,
        "client_id": settings.AUTH0_CLIENT_ID,
        "client_secret": settings.AUTH0_CLIENT_SECRET,
        "realm": settings.AUTH0_CONNECTION,
        "scope": "openid profile email",
    }
    if settings.AUTH0_AUDIENCE:
        payload["audience"] = settings.AUTH0_AUDIENCE
    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(url, json=payload)
    if res.status_code >= 400:
        data = res.json()
        if data.get("error") == "mfa_required":
            raise AppError("mfa_required", "Multi-factor authentication code required", status_code=403)
        raise AppError("invalid_credentials", "Invalid email or password", status_code=401)
    return dict(res.json())


async def auth0_forgot_password(*, email: str) -> None:
    """Trigger Auth0 password-reset email."""
    url = f"https://{settings.AUTH0_DOMAIN}/dbconnections/change_password"
    payload = {
        "client_id": settings.AUTH0_CLIENT_ID,
        "email": email,
        "connection": settings.AUTH0_CONNECTION,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        await client.post(url, json=payload)


async def auth0_send_email_otp(*, email: str) -> None:
    """Send a 6-digit email OTP via Auth0 Passwordless Email."""
    url = f"https://{settings.AUTH0_DOMAIN}/passwordless/start"
    payload = {
        "client_id": settings.AUTH0_CLIENT_ID,
        "client_secret": settings.AUTH0_CLIENT_SECRET,
        "connection": "email",
        "email": email,
        "send": "code",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(url, json=payload)
    if res.status_code >= 400:
        data = res.json() if res.content else {}
        msg = str(
            data.get("error_description")
            or data.get("description")
            or data.get("message")
            or "Could not send verification code."
        )
        raise AppError("otp_send_failed", msg, status_code=400)


async def auth0_verify_email_otp(*, email: str, otp: str) -> dict[str, Any]:
    """Verify a 6-digit email OTP via Auth0 Passwordless OTP grant."""
    url = f"https://{settings.AUTH0_DOMAIN}/oauth/token"
    payload = {
        "grant_type": "http://auth0.com/oauth/grant-type/passwordless/otp",
        "client_id": settings.AUTH0_CLIENT_ID,
        "client_secret": settings.AUTH0_CLIENT_SECRET,
        "username": email,
        "otp": otp,
        "realm": "email",
        "scope": "openid profile email",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(url, json=payload)
    if res.status_code >= 400:
        data = res.json() if res.content else {}
        msg = str(
            data.get("error_description")
            or data.get("message")
            or "Invalid or expired verification code."
        )
        raise AppError("invalid_otp", msg, status_code=400)
    return dict(res.json())


async def auth0_exchange_code(*, code: str, redirect_uri: str) -> dict[str, Any]:
    """Exchange OAuth authorization code for tokens and fetch Auth0 userinfo."""
    token_url = f"https://{settings.AUTH0_DOMAIN}/oauth/token"
    async with httpx.AsyncClient(timeout=15.0) as client:
        token_res = await client.post(
            token_url,
            json={
                "grant_type": "authorization_code",
                "client_id": settings.AUTH0_CLIENT_ID,
                "client_secret": settings.AUTH0_CLIENT_SECRET,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        if token_res.status_code >= 400:
            raise AppError("oauth_failed", "Could not exchange OAuth authorization code", status_code=401)
        tokens = token_res.json()
        userinfo_res = await client.get(
            f"https://{settings.AUTH0_DOMAIN}/userinfo",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        if userinfo_res.status_code >= 400:
            raise AppError("oauth_failed", "Could not fetch Auth0 user profile", status_code=401)
        return dict(userinfo_res.json())
