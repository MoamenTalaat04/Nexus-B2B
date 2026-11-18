"""Authentication helpers (CONTRACTS section 1: JWT in the httpOnly cookie `access_token`).

Minimal stand-in written in P0-3 so that /runs can be tenant-scoped before P0-4 lands. It only *reads*
the token, following the P0-4 spec (HS256, settings.JWT_SECRET, claims sub=user_id, tid=tenant_id, role).
P0-4 owns this file: it adds password hashing, token creation and the cookie helpers, and may
rewrite this part.
"""

import uuid
from dataclasses import dataclass

import jwt
from fastapi import Request

from app.config import settings
from app.core.errors import AppError

COOKIE_NAME = "access_token"
JWT_ALGORITHM = "HS256"


@dataclass(frozen=True)
class CurrentUser:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: str


def _unauthorized(message: str = "Not authenticated") -> AppError:
    return AppError("unauthorized", message, status_code=401)


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
