"""Live search adapters for OpenStreetMap, Reddit, Serper/Google Search, and Social sites."""

import hashlib
import logging
from typing import Any

import httpx

from app.adapters.base import PlaceResult, RegionFilter, SearchSource

logger = logging.getLogger("app.adapters.places.live_sources")

SITE_SCOPES: dict[str, str] = {
    "linkedin": "site:linkedin.com/company OR site:linkedin.com/in",
    "facebook": "site:facebook.com",
    "instagram": "site:instagram.com",
    "x_twitter": "site:x.com OR site:twitter.com",
    "reddit": "site:reddit.com",
}


class OpenStreetMapSearchSource:
    """Free live Egyptian business discovery via OpenStreetMap Nominatim."""

    name = "openstreetmap"

    async def search(self, query: str, *, region: RegionFilter, max_results: int = 20) -> list[PlaceResult]:
        q_full = f"{query}, {region.governorate}, Egypt".strip(", ")
        params: dict[str, str | int] = {
            "q": q_full,
            "countrycodes": "eg",
            "format": "jsonv2",
            "addressdetails": 1,
            "extratags": 1,
            "limit": min(max_results, 25),
        }
        headers = {"User-Agent": "NexusB2B-SDR/1.0 (https://nexusb2b.app)"}
        async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
            res = await client.get("https://nominatim.openstreetmap.org/search", params=params)
            if res.status_code >= 400:
                return []
            items = res.json()

        results: list[PlaceResult] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            display = str(item.get("display_name") or "").strip()
            if not name and display:
                name = display.split(",")[0].strip()
            if not name:
                continue
            raw_addr = item.get("address")
            addr: dict[str, Any] = raw_addr if isinstance(raw_addr, dict) else {}
            raw_extras = item.get("extratags")
            extras: dict[str, Any] = raw_extras if isinstance(raw_extras, dict) else {}
            city = str(addr.get("city") or addr.get("town") or addr.get("suburb") or "") or None
            gov = str(addr.get("state") or region.governorate or "") or None
            phone = str(extras.get("phone") or extras.get("contact:phone") or "") or None
            website = str(extras.get("website") or extras.get("contact:website") or "") or None
            results.append(
                PlaceResult(
                    source="openstreetmap",
                    source_ref=f"osm:{item.get('osm_type', 'n')}:{item.get('osm_id', name)}",
                    name=name,
                    category=str(item.get("type") or item.get("category") or "") or None,
                    address=display or None,
                    city=city,
                    governorate=gov,
                    lat=float(item["lat"]) if item.get("lat") else None,
                    lng=float(item["lon"]) if item.get("lon") else None,
                    phone_national=phone,
                    website=website,
                    business_status="OPERATIONAL",
                    types=[str(item.get("type"))] if item.get("type") else [],
                    raw=item,
                )
            )
        return results[:max_results]


class RedditPublicSearchSource:
    """Public Reddit JSON search (no API key required)."""

    name = "reddit"

    async def search(self, query: str, *, region: RegionFilter, max_results: int = 20) -> list[PlaceResult]:
        q_full = f"{query} {region.governorate} Egypt".strip()
        headers = {"User-Agent": "NexusB2B-SDR/1.0"}
        async with httpx.AsyncClient(timeout=12.0, headers=headers) as client:
            res = await client.get(
                "https://www.reddit.com/search.json",
                params={"q": q_full, "limit": min(max_results, 15)},
            )
            if res.status_code >= 400:
                return []
            payload = res.json()

        children = payload.get("data", {}).get("children", [])
        results: list[PlaceResult] = []
        for child in children:
            post = child.get("data", {}) if isinstance(child, dict) else {}
            title = str(post.get("title") or "").strip()
            if not title:
                continue
            permalink = f"https://www.reddit.com{post.get('permalink', '')}"
            results.append(
                PlaceResult(
                    source="reddit",
                    source_ref=f"reddit:{post.get('id', hashlib.md5(title.encode()).hexdigest()[:10])}",
                    name=title[:140],
                    category="reddit_thread",
                    governorate=region.governorate,
                    website=permalink,
                    business_status="OPERATIONAL",
                    raw=post,
                )
            )
        return results[:max_results]


class SerperWebSearchSource:
    """Google Search / Social (LinkedIn, Facebook, Instagram, X) via Serper.dev or Google CSE."""

    def __init__(
        self,
        *,
        source_type: str,
        api_key: str,
        base_url: str = "https://google.serper.dev/search",
        extra_config: str = "",
    ) -> None:
        self.name = source_type
        self._api_key = api_key
        self._base_url = base_url or "https://google.serper.dev/search"
        self._extra_config = extra_config

    async def search(self, query: str, *, region: RegionFilter, max_results: int = 20) -> list[PlaceResult]:
        scope = SITE_SCOPES.get(self.name, "")
        scoped_query = f"{scope} {query} {region.governorate} Egypt".strip()

        async with httpx.AsyncClient(timeout=15.0) as client:
            if "googleapis.com/customsearch" in self._base_url:
                res = await client.get(
                    self._base_url,
                    params={
                        "key": self._api_key,
                        "cx": self._extra_config,
                        "q": scoped_query,
                        "num": min(max_results, 10),
                    },
                )
                items = res.json().get("items", []) if res.status_code < 400 else []
            else:
                res = await client.post(
                    self._base_url,
                    headers={"X-API-KEY": self._api_key, "Content-Type": "application/json"},
                    json={"q": scoped_query, "gl": "eg", "num": min(max_results, 20)},
                )
                items = res.json().get("organic", []) if res.status_code < 400 else []

        results: list[PlaceResult] = []
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            link = str(item.get("link") or "").strip()
            snippet = str(item.get("snippet") or "").strip()
            if not title:
                continue
            ref = hashlib.md5((link or f"{title}-{idx}").encode()).hexdigest()[:16]
            results.append(
                PlaceResult(
                    source=self.name,
                    source_ref=f"{self.name}:{ref}",
                    name=title[:160],
                    category=self.name,
                    address=snippet[:240] if snippet else None,
                    governorate=region.governorate,
                    website=link or None,
                    business_status="OPERATIONAL",
                    raw=item,
                )
            )
        return results[:max_results]


class CompositeSearchSource:
    """Queries active search sources in Super Admin priority order and merges results."""

    name = "live_search"

    def __init__(self, sources: list[SearchSource]) -> None:
        self._sources = sources

    async def search(self, query: str, *, region: RegionFilter, max_results: int = 20) -> list[PlaceResult]:
        collected: list[PlaceResult] = []
        seen_refs: set[str] = set()
        for src in self._sources:
            remaining = max_results - len(collected)
            if remaining <= 0:
                break
            try:
                batch = await src.search(query, region=region, max_results=remaining)
            except Exception as exc:
                logger.warning("Search source %s failed for %r: %s", getattr(src, "name", src), query, exc)
                continue
            for place in batch:
                if place.source_ref not in seen_refs:
                    seen_refs.add(place.source_ref)
                    collected.append(place)
        return collected[:max_results]
