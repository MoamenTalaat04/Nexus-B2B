"""Dynamic Search Source registry backed by PostgreSQL."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import SearchSource
from app.adapters.search.google_places import GooglePlacesSource
from app.adapters.search.live_sources import (
    CompositeSearchSource,
    OpenStreetMapSearchSource,
    RedditPublicSearchSource,
    SerperWebSearchSource,
)
from app.config import settings
from app.core.crypto import CryptoError, decrypt_json, encrypt_json
from app.db import SessionLocal
from app.models.search_source import SearchSourceConfig

logger = logging.getLogger("app.services.search_registry")


def encrypt_search_key(api_key: str) -> str:
    if not api_key:
        return ""
    return encrypt_json({"api_key": api_key})


def decrypt_search_key(token: str) -> str:
    if not token:
        return ""
    data = decrypt_json(token)
    return str(data.get("api_key", ""))


def mask_search_key(api_key: str) -> str:
    if not api_key:
        return "None (Free)"
    if len(api_key) <= 8:
        return "****"
    return f"{api_key[:5]}...{api_key[-4:]}"


async def ensure_default_search_sources(session: AsyncSession) -> list[SearchSourceConfig]:
    rows = list(
        (
            await session.execute(
                select(SearchSourceConfig).order_by(
                    SearchSourceConfig.is_primary.desc(),
                    SearchSourceConfig.priority.asc(),
                    SearchSourceConfig.created_at.asc(),
                )
            )
        )
        .scalars()
        .all()
    )
    if rows:
        return rows

    has_gplaces = bool(settings.GOOGLE_PLACES_API_KEY)
    defaults = [
        SearchSourceConfig(
            name="OpenStreetMap (Free Live Places)",
            source_type="openstreetmap",
            base_url="https://nominatim.openstreetmap.org/search",
            encrypted_api_key="",
            priority=1,
            is_active=True,
            is_primary=not has_gplaces,
        ),
        SearchSourceConfig(
            name="Google Places (Maps)",
            source_type="google_places",
            base_url="https://places.googleapis.com/v1/places:searchText",
            encrypted_api_key=encrypt_search_key(settings.GOOGLE_PLACES_API_KEY),
            priority=2,
            is_active=has_gplaces,
            is_primary=has_gplaces,
        ),
        SearchSourceConfig(
            name="Google Search (Serper / CSE)",
            source_type="google_search",
            base_url="https://google.serper.dev/search",
            encrypted_api_key="",
            priority=3,
            is_active=False,
            is_primary=False,
        ),
        SearchSourceConfig(
            name="LinkedIn",
            source_type="linkedin",
            base_url="https://google.serper.dev/search",
            encrypted_api_key="",
            priority=4,
            is_active=False,
            is_primary=False,
        ),
        SearchSourceConfig(
            name="Facebook",
            source_type="facebook",
            base_url="https://google.serper.dev/search",
            encrypted_api_key="",
            priority=5,
            is_active=False,
            is_primary=False,
        ),
        SearchSourceConfig(
            name="Instagram",
            source_type="instagram",
            base_url="https://google.serper.dev/search",
            encrypted_api_key="",
            priority=6,
            is_active=False,
            is_primary=False,
        ),
        SearchSourceConfig(
            name="X (Twitter)",
            source_type="x_twitter",
            base_url="https://google.serper.dev/search",
            encrypted_api_key="",
            priority=7,
            is_active=False,
            is_primary=False,
        ),
        SearchSourceConfig(
            name="Reddit",
            source_type="reddit",
            base_url="https://www.reddit.com/search.json",
            encrypted_api_key="",
            priority=8,
            is_active=False,
            is_primary=False,
        ),
    ]
    session.add_all(defaults)
    await session.commit()
    return await ensure_default_search_sources(session)


async def build_live_search_source() -> SearchSource:
    """Build a CompositeSearchSource from active DB search sources in priority order."""
    try:
        async with SessionLocal() as session:
            rows = await ensure_default_search_sources(session)
    except Exception:
        return OpenStreetMapSearchSource()

    active_rows = [r for r in rows if r.is_active]
    sources: list[SearchSource] = []
    for row in active_rows:
        try:
            api_key = decrypt_search_key(row.encrypted_api_key)
        except CryptoError:
            api_key = ""

        if row.source_type == "openstreetmap":
            sources.append(OpenStreetMapSearchSource())
        elif row.source_type == "reddit" and not api_key:
            sources.append(RedditPublicSearchSource())
        elif row.source_type == "google_places":
            if api_key:
                sources.append(GooglePlacesSource(api_key=api_key))
        elif api_key:
            sources.append(
                SerperWebSearchSource(
                    source_type=row.source_type,
                    api_key=api_key,
                    base_url=row.base_url,
                    extra_config=row.extra_config,
                )
            )

    if not sources:
        sources.append(OpenStreetMapSearchSource())
    return CompositeSearchSource(sources)
