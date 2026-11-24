"""Super Admin API for managing Search Sources, API keys, enable/disable, and priority."""

import time
import uuid

import httpx
from fastapi import APIRouter, Depends, Header
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import CryptoError
from app.core.errors import AppError
from app.db import get_session
from app.models.search_source import SearchSourceConfig
from app.schemas.admin_search import (
    SearchSourceCreate,
    SearchSourceListOut,
    SearchSourceOut,
    SearchSourceReorderIn,
    SearchSourceTestOut,
    SearchSourceUpdate,
)
from app.services.search_registry import (
    decrypt_search_key,
    encrypt_search_key,
    ensure_default_search_sources,
    mask_search_key,
)

router = APIRouter(prefix="/admin/search-sources", tags=["admin-search"])


def _require_super_admin(x_admin_role: str | None = Header(default=None, alias="X-Admin-Role")) -> None:
    if x_admin_role != "super_admin":
        raise AppError("forbidden", "Super Admin access required.", status_code=403)


def _to_out(row: SearchSourceConfig) -> SearchSourceOut:
    try:
        plain = decrypt_search_key(row.encrypted_api_key)
    except CryptoError:
        plain = ""
    return SearchSourceOut(
        id=row.id,
        name=row.name,
        source_type=row.source_type,
        base_url=row.base_url,
        api_key_masked=mask_search_key(plain),
        has_api_key=bool(plain),
        extra_config=row.extra_config,
        priority=row.priority,
        is_active=row.is_active,
        is_primary=row.is_primary,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=SearchSourceListOut, dependencies=[Depends(_require_super_admin)])
async def list_search_sources(session: AsyncSession = Depends(get_session)) -> SearchSourceListOut:
    rows = await ensure_default_search_sources(session)
    return SearchSourceListOut(items=[_to_out(r) for r in rows], total=len(rows))


@router.post(
    "", response_model=SearchSourceOut, status_code=201, dependencies=[Depends(_require_super_admin)]
)
async def create_search_source(
    body: SearchSourceCreate,
    session: AsyncSession = Depends(get_session),
) -> SearchSourceOut:
    if body.is_primary:
        await session.execute(update(SearchSourceConfig).values(is_primary=False))
    row = SearchSourceConfig(
        name=body.name.strip(),
        source_type=body.source_type,
        base_url=body.base_url.strip(),
        encrypted_api_key=encrypt_search_key(body.api_key.strip()),
        extra_config=body.extra_config.strip(),
        priority=body.priority,
        is_active=body.is_active,
        is_primary=body.is_primary,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _to_out(row)


@router.put("/{source_id}", response_model=SearchSourceOut, dependencies=[Depends(_require_super_admin)])
async def update_search_source(
    source_id: uuid.UUID,
    body: SearchSourceUpdate,
    session: AsyncSession = Depends(get_session),
) -> SearchSourceOut:
    row = await session.get(SearchSourceConfig, source_id)
    if row is None:
        raise AppError("not_found", "Search source not found.", status_code=404)

    if body.is_primary is True:
        await session.execute(
            update(SearchSourceConfig).where(SearchSourceConfig.id != source_id).values(is_primary=False)
        )

    if body.name is not None:
        row.name = body.name.strip()
    if body.source_type is not None:
        row.source_type = body.source_type
    if body.base_url is not None:
        row.base_url = body.base_url.strip()
    if body.api_key is not None:
        row.encrypted_api_key = encrypt_search_key(body.api_key.strip())
    if body.extra_config is not None:
        row.extra_config = body.extra_config.strip()
    if body.priority is not None:
        row.priority = body.priority
    if body.is_active is not None:
        row.is_active = body.is_active
    if body.is_primary is not None:
        row.is_primary = body.is_primary

    await session.commit()
    await session.refresh(row)
    return _to_out(row)


@router.post(
    "/{source_id}/set-primary",
    response_model=SearchSourceOut,
    dependencies=[Depends(_require_super_admin)],
)
async def set_primary_search_source(
    source_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> SearchSourceOut:
    row = await session.get(SearchSourceConfig, source_id)
    if row is None:
        raise AppError("not_found", "Search source not found.", status_code=404)
    await session.execute(update(SearchSourceConfig).values(is_primary=False))
    row.is_primary = True
    row.is_active = True
    row.priority = 1
    await session.commit()
    await session.refresh(row)
    return _to_out(row)


@router.post(
    "/{source_id}/test",
    response_model=SearchSourceTestOut,
    dependencies=[Depends(_require_super_admin)],
)
async def test_search_source(
    source_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> SearchSourceTestOut:
    row = await session.get(SearchSourceConfig, source_id)
    if row is None:
        raise AppError("not_found", "Search source not found.", status_code=404)

    api_key = decrypt_search_key(row.encrypted_api_key)
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(
            timeout=10.0,
            headers={"User-Agent": "NexusB2B-SDR/1.0 (https://nexusb2b.app)"},
        ) as client:
            if row.source_type == "openstreetmap":
                res = await client.get(
                    "https://nominatim.openstreetmap.org/search",
                    params={"q": "computer Alexandria Egypt", "format": "jsonv2", "limit": 3},
                )
                count = len(res.json()) if res.status_code < 400 else 0
            elif row.source_type == "reddit" and not api_key:
                res = await client.get(
                    "https://www.reddit.com/search.json",
                    params={"q": "computer Egypt", "limit": 3},
                )
                count = len(res.json().get("data", {}).get("children", [])) if res.status_code < 400 else 0
            elif row.source_type == "google_places":
                if not api_key:
                    return SearchSourceTestOut(
                        ok=False,
                        latency_ms=0,
                        error="Google Places API key is not configured.",
                    )
                res = await client.post(
                    "https://places.googleapis.com/v1/places:searchText",
                    headers={
                        "X-Goog-Api-Key": api_key,
                        "X-Goog-FieldMask": "places.id,places.displayName",
                    },
                    json={"textQuery": "computer store Alexandria Egypt", "pageSize": 3},
                )
                count = len(res.json().get("places", [])) if res.status_code < 400 else 0
            else:
                if not api_key:
                    return SearchSourceTestOut(
                        ok=False,
                        latency_ms=0,
                        error="API key is required for this search source.",
                    )
                res = await client.post(
                    row.base_url or "https://google.serper.dev/search",
                    headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                    json={"q": f"{row.source_type} computer Alexandria Egypt", "num": 3},
                )
                count = len(res.json().get("organic", [])) if res.status_code < 400 else 0

        latency_ms = int((time.perf_counter() - started) * 1000)
        if res.status_code >= 400:
            return SearchSourceTestOut(
                ok=False,
                status_code=res.status_code,
                latency_ms=latency_ms,
                error=f"HTTP {res.status_code}",
            )
        return SearchSourceTestOut(
            ok=True,
            status_code=res.status_code,
            latency_ms=latency_ms,
            sample_count=count,
        )
    except Exception as exc:
        return SearchSourceTestOut(
            ok=False,
            latency_ms=int((time.perf_counter() - started) * 1000),
            error=str(exc),
        )


@router.post(
    "/reorder",
    response_model=SearchSourceListOut,
    dependencies=[Depends(_require_super_admin)],
)
async def reorder_search_sources(
    body: SearchSourceReorderIn,
    session: AsyncSession = Depends(get_session),
) -> SearchSourceListOut:
    rows = await ensure_default_search_sources(session)
    by_id = {row.id: row for row in rows}
    ordered_rows: list[SearchSourceConfig] = []
    seen: set[uuid.UUID] = set()
    for sid in body.ordered_ids:
        if sid in by_id and sid not in seen:
            ordered_rows.append(by_id[sid])
            seen.add(sid)
    for row in rows:
        if row.id not in seen:
            ordered_rows.append(row)

    for idx, row in enumerate(ordered_rows):
        row.priority = idx + 1
        row.is_primary = idx == 0

    await session.commit()
    refreshed = await ensure_default_search_sources(session)
    return SearchSourceListOut(items=[_to_out(r) for r in refreshed], total=len(refreshed))


@router.delete("/{source_id}", status_code=204, dependencies=[Depends(_require_super_admin)])
async def delete_search_source(
    source_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    row = await session.get(SearchSourceConfig, source_id)
    if row is None:
        raise AppError("not_found", "Search source not found.", status_code=404)
    await session.delete(row)
    await session.commit()
