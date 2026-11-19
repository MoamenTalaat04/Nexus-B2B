"""Mock Auth routes: /auth/register, /auth/login, /auth/logout, /auth/me."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field, field_validator

from app.core.errors import AppError
from app.core.security import CurrentUser
from app.mock_api.helpers import (
    clear_auth_cookie,
    create_access_token,
    get_mock_current_user,
    get_tenant_settings,
    set_auth_cookie,
)
from app.mock_api.state import MockBusinessSettings, MockTenant, MockUser, get_store

router = APIRouter(prefix="/auth", tags=["auth"])


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=120)
    company_name: str = Field(min_length=1, max_length=160)

    @field_validator("email")
    @classmethod
    def _validate_email(cls, v: str) -> str:
        val = v.strip().lower()
        if not _EMAIL_RE.match(val):
            raise ValueError("Invalid email address")
        return val


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1)

    @field_validator("email")
    @classmethod
    def _validate_email(cls, v: str) -> str:
        val = v.strip().lower()
        if not _EMAIL_RE.match(val):
            raise ValueError("Invalid email address")
        return val


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str


class TenantOut(BaseModel):
    id: uuid.UUID
    name: str


class AuthResponse(BaseModel):
    user: UserOut
    tenant: TenantOut
    onboarding_completed: bool
    access_token: str | None = None


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(body: RegisterIn, response: Response) -> AuthResponse:
    store = get_store()
    email_lower = body.email.lower().strip()
    if any(u.email.lower() == email_lower for u in store.users.values()):
        raise AppError("email_taken", "An account with this email already exists.", status_code=409)

    now = datetime.now(UTC)
    tenant = MockTenant(id=uuid.uuid4(), name=body.company_name.strip(), created_at=now)
    user = MockUser(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=email_lower,
        password=body.password,
        full_name=body.full_name.strip(),
        role="owner",
        created_at=now,
    )
    settings_obj = MockBusinessSettings(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        company_name=body.company_name.strip(),
        onboarding_completed=False,
        updated_at=now,
    )
    store.tenants[tenant.id] = tenant
    store.users[user.id] = user
    store.settings[settings_obj.id] = settings_obj

    token = create_access_token(user)
    set_auth_cookie(response, token)
    return AuthResponse(
        user=UserOut(id=user.id, email=user.email, full_name=user.full_name, role=user.role),
        tenant=TenantOut(id=tenant.id, name=tenant.name),
        onboarding_completed=settings_obj.onboarding_completed,
        access_token=token,
    )


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginIn, response: Response) -> AuthResponse:
    store = get_store()
    email_lower = body.email.lower().strip()
    user = next((u for u in store.users.values() if u.email.lower() == email_lower), None)
    if user is None or user.password != body.password:
        raise AppError("invalid_credentials", "Invalid email or password.", status_code=401)

    tenant = store.tenants[user.tenant_id]
    settings_obj = get_tenant_settings(store, user.tenant_id)
    token = create_access_token(user)
    set_auth_cookie(response, token)
    return AuthResponse(
        user=UserOut(id=user.id, email=user.email, full_name=user.full_name, role=user.role),
        tenant=TenantOut(id=tenant.id, name=tenant.name),
        onboarding_completed=settings_obj.onboarding_completed,
        access_token=token,
    )


@router.post("/logout")
async def logout(response: Response) -> dict[str, bool]:
    clear_auth_cookie(response)
    return {"ok": True}


@router.get("/me", response_model=AuthResponse)
async def me(current_user: CurrentUser = Depends(get_mock_current_user)) -> AuthResponse:
    store = get_store()
    user = store.users.get(current_user.user_id)
    tenant = store.tenants.get(current_user.tenant_id)
    if user is None or tenant is None:
        raise AppError("unauthorized", "User session no longer exists.", status_code=401)
    settings_obj = get_tenant_settings(store, current_user.tenant_id)
    return AuthResponse(
        user=UserOut(id=user.id, email=user.email, full_name=user.full_name, role=user.role),
        tenant=TenantOut(id=tenant.id, name=tenant.name),
        onboarding_completed=settings_obj.onboarding_completed,
    )
