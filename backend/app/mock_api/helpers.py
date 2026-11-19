"""Shared helpers for the Mock API layer."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi import Request, Response

from app.config import settings
from app.core.errors import AppError
from app.core.lead_state import ALLOWED, TERMINAL
from app.core.security import COOKIE_NAME, JWT_ALGORITHM, CurrentUser
from app.mock_api.state import MockStore, MockUser
from app.models.enums import LeadStatus, ReplyIntent

TOKEN_TTL_DAYS = 7


def create_access_token(user: MockUser) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "tid": str(user.tenant_id),
        "role": user.role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=TOKEN_TTL_DAYS)).timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=JWT_ALGORITHM)


def set_auth_cookie(response: Response, token: str) -> None:
    is_local = settings.FRONTEND_ORIGIN.startswith("http://localhost") or settings.PUBLIC_BASE_URL.startswith(
        "http://localhost"
    )
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=not is_local,
        max_age=TOKEN_TTL_DAYS * 86400,
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(key=COOKIE_NAME, path="/")


async def get_mock_current_user(request: Request) -> CurrentUser:
    """Resolve CurrentUser from httpOnly cookie `access_token` or Bearer token (for Swagger)."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()
    if not token:
        raise AppError("unauthorized", "Not authenticated", status_code=401)
    try:
        claims = jwt.decode(token, settings.JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return CurrentUser(
            user_id=uuid.UUID(str(claims["sub"])),
            tenant_id=uuid.UUID(str(claims["tid"])),
            role=str(claims.get("role", "member")),
        )
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise AppError("unauthorized", "Invalid or expired session", status_code=401) from exc


def normalize_ar(text: str) -> str:
    """Normalize Arabic text for case/diacritic-insensitive search."""
    t = re.sub(r"[\u064B-\u065F\u0670]", "", text)
    t = re.sub(r"[أإآ]", "ا", t)
    t = t.replace("ة", "ه").replace("ى", "ي")
    return t.lower().strip()


def normalize_eg_phone(raw: str) -> str | None:
    """Normalize common Egyptian phone formats to E.164 (+20...)."""
    arabic_digits = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
    cleaned = re.sub(r"[^\d+]", "", raw.translate(arabic_digits))
    if cleaned.startswith("0020"):
        cleaned = "+20" + cleaned[4:]
    elif cleaned.startswith("20") and len(cleaned) >= 11:
        cleaned = "+" + cleaned
    elif cleaned.startswith("0") and len(cleaned) in (10, 11):
        cleaned = "+20" + cleaned[1:]
    elif not cleaned.startswith("+20"):
        return None
    if not re.fullmatch(r"\+20\d{9,10}", cleaned):
        return None
    return cleaned


def is_eg_mobile(e164: str) -> bool:
    return bool(re.fullmatch(r"\+20(10|11|12|15)\d{8}", e164))


def is_allowed_transition(from_status: LeadStatus, to_status: LeadStatus, *, force: bool = False) -> bool:
    if from_status == to_status:
        return True
    if force:
        return True
    if to_status == LeadStatus.OPTED_OUT:
        return from_status not in TERMINAL
    return to_status in ALLOWED.get(from_status, set())


def paginate(items: list[Any], page: int, page_size: int) -> tuple[list[Any], int]:
    total = len(items)
    start = (page - 1) * page_size
    return items[start : start + page_size], total


def classify_mock_reply(text: str) -> tuple[ReplyIntent, str, bool]:
    """Deterministic Egyptian Arabic / English reply classifier for mock simulation.

    Returns (intent, suggested_reply, should_escalate).
    """
    norm = normalize_ar(text)
    if any(w in norm for w in ("stop", "unsubscribe", "الغي", "وقف", "متبعتش", "كفايه")):
        return (
            ReplyIntent.OPTED_OUT,
            "تم إيقاف الرسائل تماماً بناءً على طلبك. نعتذر عن أي إزعاج.",
            False,
        )
    if any(w in norm for w in ("wrong", "غلط", "الرقم غلط", "مش المحل")):
        return (
            ReplyIntent.WRONG_CONTACT,
            "نعتذر جداً عن الإزعاج، تم تحديث الرقم ولن نتواصل مجدداً.",
            False,
        )
    if any(w in norm for w in ("صاحب المصنع", "المدير", "الاداره", "manager", "owner")):
        return (
            ReplyIntent.WANTS_MANAGEMENT,
            "بكل سرور، تم تحويل طلبك لإدارة المبيعات وسيتواصل معك مسؤول المبيعات فوراً.",
            True,
        )
    if any(w in norm for w in ("خصم", "عرض", "اقل سعر", "discount", "offer", "كميه")):
        return (
            ReplyIntent.WANTS_OFFER,
            (
                "متاح لدينا عروض وخصومات للكميات تبدأ من 50 قطعة وتصل إلى 10% للطلبات الكبيرة."
                " سيتواصل معك فريق المبيعات بالتفاصيل."
            ),
            True,
        )
    if any(w in norm for w in ("مش مهتم", "لا شكرا", "مش محتاج", "not interested", "no thanks")):
        return (
            ReplyIntent.NOT_INTERESTED,
            "شكراً لوقتك! لو احتجت أي تشكيلة ملابس أطفال مستقبلاً يسعدنا تواصلك.",
            False,
        )
    if any(w in norm for w in ("الشهر الجاي", "بعدين", "لاحقا", "later", "next month")):
        return (
            ReplyIntent.LATER,
            "تمام جداً، سنتواصل معك الشهر القادم إن شاء الله. بالتوفيق!",
            False,
        )
    if any(w in norm for w in ("مهتم", "الاسعار", "كتالوج", "ابعتلي", "interested", "price", "catalog")):
        return (
            ReplyIntent.INTERESTED,
            (
                "أهلاً بك! يسعدنا إرسال كتالوج وأسعار الجملة لملابس الأطفال من مصنع لتل ستارز."
                " هل تفضل تيشيرتات أم أطقم خروج؟"
            ),
            True,
        )
    return (
        ReplyIntent.QUESTION,
        (
            "أهلاً بك في مصنع لتل ستارز! أنا المساعد الذكي، أقل كمية للطلب هي 24 قطعة"
            " والتوصيل متاح للقاهرة والجيزة."
        ),
        False,
    )


def get_tenant_settings(store: MockStore, tenant_id: uuid.UUID) -> Any:
    for s in store.settings.values():
        if s.tenant_id == tenant_id:
            return s
    raise AppError("not_found", "Business settings not found", status_code=404)
