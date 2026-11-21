"""Pydantic schemas for authentication & security endpoints."""

import uuid

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=120)
    company_name: str = Field(min_length=1, max_length=160)


class SendEmailOtpRequest(BaseModel):
    email: EmailStr


class RegisterVerifyOtpRequest(RegisterRequest):
    otp: str = Field(min_length=4, max_length=12)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class AuthUserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    tenant_id: uuid.UUID


class AuthTenantOut(BaseModel):
    id: uuid.UUID
    name: str


class AuthMeResponse(BaseModel):
    user: AuthUserOut
    tenant: AuthTenantOut
    tenant_id: uuid.UUID
    onboarding_completed: bool
    auth_provider: str = "local"


class AuthMessageResponse(BaseModel):
    ok: bool = True
    message: str


class SecurityStatusResponse(BaseModel):
    auth0_enabled: bool
    email: str
    mfa_enabled: bool
    passkeys_enabled: bool
