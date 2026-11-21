"""Mock Notifications routes: /notifications, /notifications/{id}/read, /notifications/read-all."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.core.errors import NotFoundError
from app.core.security import CurrentUser
from app.mock_api.helpers import get_mock_current_user, paginate
from app.mock_api.state import get_store

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationOut(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID | None
    kind: str
    title: str
    body: str
    read_at: datetime | None
    telegram_sent_at: datetime | None
    created_at: datetime


class NotificationListOut(BaseModel):
    items: list[NotificationOut]
    total: int
    unread_count: int


@router.get("", response_model=NotificationListOut)
async def list_notifications(
    unread_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: CurrentUser = Depends(get_mock_current_user),
) -> NotificationListOut:
    store = get_store()
    all_rows = [n for n in store.notifications.values() if n.tenant_id == current_user.tenant_id]
    unread_count = sum(1 for n in all_rows if n.read_at is None)
    rows = [n for n in all_rows if n.read_at is None] if unread_only else all_rows
    # Unread first, then newest
    rows.sort(key=lambda n: (n.read_at is not None, -n.created_at.timestamp()))
    paged, total = paginate(rows, page, page_size)
    return NotificationListOut(
        items=[
            NotificationOut(
                id=n.id,
                lead_id=n.lead_id,
                kind=n.kind,
                title=n.title,
                body=n.body,
                read_at=n.read_at,
                telegram_sent_at=n.telegram_sent_at,
                created_at=n.created_at,
            )
            for n in paged
        ],
        total=total,
        unread_count=unread_count,
    )


@router.post("/{notification_id}/read", response_model=NotificationOut)
async def mark_read(
    notification_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_mock_current_user),
) -> NotificationOut:
    store = get_store()
    n = store.notifications.get(notification_id)
    if n is None or n.tenant_id != current_user.tenant_id:
        raise NotFoundError("notification")
    if n.read_at is None:
        n.read_at = datetime.now(UTC)
    return NotificationOut(
        id=n.id,
        lead_id=n.lead_id,
        kind=n.kind,
        title=n.title,
        body=n.body,
        read_at=n.read_at,
        telegram_sent_at=n.telegram_sent_at,
        created_at=n.created_at,
    )


@router.post("/read-all")
async def mark_all_read(current_user: CurrentUser = Depends(get_mock_current_user)) -> dict[str, int]:
    store = get_store()
    now = datetime.now(UTC)
    updated = 0
    for n in store.notifications.values():
        if n.tenant_id == current_user.tenant_id and n.read_at is None:
            n.read_at = now
            updated += 1
    return {"marked_read": updated}
