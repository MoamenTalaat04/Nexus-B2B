"""Authentication API routes (P0-4: Hybrid Auth0 + PostgreSQL / Argon2id + httpOnly JWT cookie)."""

import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.errors import AppError
from app.core.security import (
    CurrentUser,
    auth0_exchange_code,
    auth0_forgot_password,
    auth0_password_login,
    auth0_send_email_otp,
    auth0_signup,
    auth0_verify_email_otp,
    clear_auth_cookie,
    create_access_token,
    get_current_user,
    hash_password,
    is_auth0_configured,
    set_auth_cookie,
    verify_password,
)
from app.core.tenancy import get_settings_for
from app.db import get_session
from app.models.tenants import Tenant, User
from app.schemas.auth import (
    AuthMeResponse,
    AuthMessageResponse,
    AuthTenantOut,
    AuthUserOut,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    RegisterVerifyOtpRequest,
    SecurityStatusResponse,
    SendEmailOtpRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])

OAUTH_CONNECTIONS: dict[str, str] = {
    "google": "google-oauth2",
    "linkedin": "linkedin",
    "microsoft": "windowslive",
    "passkey": "Username-Password-Authentication",
}

LOGIN_RATE_LIMIT = 10
LOGIN_RATE_WINDOW_SEC = 60


async def _enforce_login_rate_limit(request: Request) -> None:
    """Simple Redis 10/min per-IP counter; fails open if Redis is unavailable in local/unit test runs."""
    ip = request.client.host if request.client else "unknown"
    key = f"rl:auth:login:{ip}"
    try:
        client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            count = await client.incr(key)
            if count == 1:
                await client.expire(key, LOGIN_RATE_WINDOW_SEC)
            if count > LOGIN_RATE_LIMIT:
                raise AppError("rate_limited", "Too many login attempts. Try again in a minute.", 429)
        finally:
            await client.aclose()
    except AppError:
        raise
    except Exception:
        return


def _build_auth_response(*, user: User, tenant: Tenant, onboarding_completed: bool) -> AuthMeResponse:
    return AuthMeResponse(
        user=AuthUserOut(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            tenant_id=user.tenant_id,
        ),
        tenant=AuthTenantOut(id=tenant.id, name=tenant.name),
        tenant_id=tenant.id,
        onboarding_completed=onboarding_completed,
        auth_provider="auth0" if is_auth0_configured() else "local",
    )


async def _provision_tenant_and_user(
    *,
    session: AsyncSession,
    response: Response,
    email: str,
    password: str,
    full_name: str,
    company_name: str,
) -> AuthMeResponse:
    if is_auth0_configured():
        await auth0_signup(email=email, password=password, full_name=full_name.strip())
        # Passwords are stored in Auth0; store an unguessable placeholder hash in PostgreSQL.
        stored_hash = hash_password(secrets.token_urlsafe(32))
    else:
        stored_hash = hash_password(password)

    tenant = Tenant(name=company_name.strip())
    session.add(tenant)
    await session.flush()

    user = User(
        tenant_id=tenant.id,
        email=email,
        password_hash=stored_hash,
        full_name=full_name.strip(),
        role="owner",
    )
    session.add(user)
    await session.flush()

    biz_settings = await get_settings_for(session, tenant.id)
    biz_settings.company_name = tenant.name
    await session.commit()
    await session.refresh(user)
    await session.refresh(tenant)

    token = create_access_token(user_id=user.id, tenant_id=tenant.id, role=user.role)
    set_auth_cookie(response, token)
    return _build_auth_response(
        user=user,
        tenant=tenant,
        onboarding_completed=biz_settings.onboarding_completed,
    )


@router.post("/register/send-otp", response_model=AuthMessageResponse)
async def register_send_otp(
    body: SendEmailOtpRequest,
    session: AsyncSession = Depends(get_session),
) -> AuthMessageResponse:
    email = body.email.strip().lower()
    existing = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing is not None:
        raise AppError("email_taken", "An account with this email already exists.", status_code=409)
    if is_auth0_configured():
        await auth0_send_email_otp(email=email)
    return AuthMessageResponse(ok=True, message=f"Verification code sent to {email}.")


@router.post("/register/verify-otp", response_model=AuthMeResponse, status_code=201)
async def register_verify_otp(
    body: RegisterVerifyOtpRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> AuthMeResponse:
    email = body.email.strip().lower()
    existing = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing is not None:
        raise AppError("email_taken", "An account with this email already exists.", status_code=409)
    if is_auth0_configured():
        await auth0_verify_email_otp(email=email, otp=body.otp.strip())
    return await _provision_tenant_and_user(
        session=session,
        response=response,
        email=email,
        password=body.password,
        full_name=body.full_name,
        company_name=body.company_name,
    )


@router.post("/register", response_model=AuthMeResponse, status_code=201)
async def register(
    body: RegisterRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> AuthMeResponse:
    email = body.email.strip().lower()
    existing = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing is not None:
        raise AppError("email_taken", "An account with this email already exists.", status_code=409)

    return await _provision_tenant_and_user(
        session=session,
        response=response,
        email=email,
        password=body.password,
        full_name=body.full_name,
        company_name=body.company_name,
    )


@router.post("/login", response_model=AuthMeResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> AuthMeResponse:
    await _enforce_login_rate_limit(request)

    email = body.email.strip().lower()
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()

    if is_auth0_configured():
        await auth0_password_login(email=email, password=body.password)
        if user is None:
            # Auto-provision PostgreSQL tenant + user on first Auth0 login
            tenant = Tenant(name=email.split("@")[0].title() + " Workspace")
            session.add(tenant)
            await session.flush()
            user = User(
                tenant_id=tenant.id,
                email=email,
                password_hash=hash_password(secrets.token_urlsafe(32)),
                full_name=email.split("@")[0],
                role="owner",
            )
            session.add(user)
            await session.flush()
            biz_settings = await get_settings_for(session, tenant.id)
            biz_settings.company_name = tenant.name
            await session.commit()
    else:
        if user is None or not verify_password(body.password, user.password_hash):
            raise AppError("invalid_credentials", "Invalid email or password.", status_code=401)

    tenant = (await session.execute(select(Tenant).where(Tenant.id == user.tenant_id))).scalar_one()
    biz_settings = await get_settings_for(session, tenant.id)
    await session.commit()

    token = create_access_token(user_id=user.id, tenant_id=tenant.id, role=user.role)
    set_auth_cookie(response, token)
    return _build_auth_response(
        user=user,
        tenant=tenant,
        onboarding_completed=biz_settings.onboarding_completed,
    )


@router.post("/logout", response_model=AuthMessageResponse)
async def logout(response: Response) -> AuthMessageResponse:
    clear_auth_cookie(response)
    return AuthMessageResponse(ok=True, message="Logged out")


@router.get("/me", response_model=AuthMeResponse)
async def me(
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AuthMeResponse:
    user = (await session.execute(select(User).where(User.id == current.user_id))).scalar_one_or_none()
    tenant = (
        await session.execute(select(Tenant).where(Tenant.id == current.tenant_id))
    ).scalar_one_or_none()
    if user is None or tenant is None:
        raise AppError("unauthorized", "Session user not found.", status_code=401)
    biz_settings = await get_settings_for(session, tenant.id)
    return _build_auth_response(
        user=user,
        tenant=tenant,
        onboarding_completed=biz_settings.onboarding_completed,
    )


@router.post("/forgot-password", response_model=AuthMessageResponse)
async def forgot_password(body: ForgotPasswordRequest) -> AuthMessageResponse:
    email = body.email.strip().lower()
    if is_auth0_configured():
        await auth0_forgot_password(email=email)
    return AuthMessageResponse(
        ok=True,
        message="If an account exists for that email, password reset instructions have been sent.",
    )


@router.get("/oauth/callback")
async def oauth_callback(
    code: str,
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    if not is_auth0_configured():
        raise AppError("auth0_not_configured", "Auth0 is not configured.", status_code=503)

    callback_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/api/v1/auth/oauth/callback"
    userinfo = await auth0_exchange_code(code=code, redirect_uri=callback_url)
    email = str(userinfo.get("email", "")).strip().lower()
    full_name = str(userinfo.get("name") or email.split("@")[0])
    if not email:
        raise AppError("oauth_failed", "Auth0 profile did not include an email.", status_code=400)

    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        tenant = Tenant(name=f"{full_name} Workspace")
        session.add(tenant)
        await session.flush()
        user = User(
            tenant_id=tenant.id,
            email=email,
            password_hash=hash_password(secrets.token_urlsafe(32)),
            full_name=full_name,
            role="owner",
        )
        session.add(user)
        await session.flush()
        biz_settings = await get_settings_for(session, tenant.id)
        biz_settings.company_name = tenant.name
        await session.commit()

    token = create_access_token(user_id=user.id, tenant_id=user.tenant_id, role=user.role)
    redirect_target = f"{settings.FRONTEND_ORIGIN.rstrip('/')}/"
    resp = RedirectResponse(url=redirect_target, status_code=302)
    set_auth_cookie(resp, token)
    return resp


@router.get("/oauth/{provider}")
async def oauth_start(provider: str) -> RedirectResponse:
    connection = OAUTH_CONNECTIONS.get(provider.lower())
    if not connection:
        raise AppError("unsupported_provider", f"Unsupported provider: {provider}", status_code=400)
    if not is_auth0_configured():
        raise AppError(
            "auth0_not_configured",
            "Auth0 credentials are not configured in .env yet.",
            status_code=503,
        )
    callback_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/api/v1/auth/oauth/callback"
    params = urlencode(
        {
            "response_type": "code",
            "client_id": settings.AUTH0_CLIENT_ID,
            "redirect_uri": callback_url,
            "scope": "openid profile email",
            "connection": connection,
        }
    )
    return RedirectResponse(url=f"https://{settings.AUTH0_DOMAIN}/authorize?{params}", status_code=302)


@router.get("/security", response_model=SecurityStatusResponse)
async def security_status(
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SecurityStatusResponse:
    user = (await session.execute(select(User).where(User.id == current.user_id))).scalar_one_or_none()
    if user is None:
        raise AppError("unauthorized", "User not found.", status_code=401)
    return SecurityStatusResponse(
        auth0_enabled=is_auth0_configured(),
        email=user.email,
        mfa_enabled=is_auth0_configured(),
        passkeys_enabled=is_auth0_configured(),
    )


@router.post("/security/reset-password", response_model=AuthMessageResponse)
async def security_reset_password(
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AuthMessageResponse:
    user = (await session.execute(select(User).where(User.id == current.user_id))).scalar_one_or_none()
    if user is None:
        raise AppError("unauthorized", "User not found.", status_code=401)
    if is_auth0_configured():
        await auth0_forgot_password(email=user.email)
    return AuthMessageResponse(
        ok=True,
        message=f"Password reset email triggered for {user.email}.",
    )
