"""Google Places API (New) Text Search as a SearchSource (P2-1).

POST https://places.googleapis.com/v1/places:searchText with httpx. Details checked against Google's docs on
2026-11-18 (developers.google.com/maps/documentation/places/web-service/text-search):
- headers X-Goog-Api-Key and X-Goog-FieldMask (comma-separated, no spaces, `places.` prefix). The field mask
  drives the price, so it lists only what we store, plus nextPageToken for pagination.
- body: textQuery, languageCode "ar", regionCode "EG", pageSize (max 20), locationBias.circle
  (radius ≤ 50 km).
- pagination: pass nextPageToken as pageToken with every other parameter unchanged; at most 60 results
  per query.
- locationBias only *prefers* the circle, so results from a neighbouring governorate come back too (a real
  "Cairo" run returned Giza shops). search() drops a place whose own governorate (from addressComponents) is
  known and differs from the requested one; a place without that component is kept. Dropped places still
  count toward max_results for paging, so the filter never adds Places requests.

No tracing here (adapters have no RunContext). B's sourcing job records the EXTERNAL_API step around search()
and reads `last_request_count` (billable requests made by the last search) for the cost log;
`last_dropped_count` is how many places the governorate filter removed.
"""

import asyncio
import logging
import random
from typing import Any

import httpx

from app.adapters.base import PlaceResult, RegionFilter
from app.config import settings
from app.core.geo_eg_coords import MAX_RADIUS_M, find_city, find_governorate

logger = logging.getLogger("app.adapters.google_places")

SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
PLACE_FIELDS = (
    "id",
    "displayName",
    "formattedAddress",
    "addressComponents",
    "location",
    "types",
    "primaryTypeDisplayName",
    "nationalPhoneNumber",
    "internationalPhoneNumber",
    "websiteUri",
    "googleMapsUri",
    "rating",
    "userRatingCount",
    "businessStatus",
)
FIELD_MASK = ",".join(f"places.{f}" for f in PLACE_FIELDS) + ",nextPageToken"
PAGE_SIZE = 20
MAX_RESULTS_PER_QUERY = 60
DEFAULT_RADIUS_M = 20_000
MAX_RETRIES = 3

# addressComponents types we read (best effort: Google may omit them; we fall back to the RegionFilter)
_GOVERNORATE_TYPES = ("administrative_area_level_1",)
_CITY_TYPES = ("locality", "administrative_area_level_2", "sublocality_level_1", "sublocality")


class GooglePlacesError(RuntimeError):
    """A clear, actionable error from the Places API (bad key, API not enabled, bad request, outage)."""


def location_bias(region: RegionFilter) -> dict[str, Any] | None:
    """A circle around the region: explicit lat/lng, else the single city, else the governorate center."""
    if region.lat is not None and region.lng is not None:
        lat, lng, radius = region.lat, region.lng, region.radius_m or DEFAULT_RADIUS_M
    else:
        governorate = find_governorate(region.governorate)
        if governorate is None:
            return None
        point = find_city(governorate, region.cities[0]) if len(region.cities) == 1 else None
        point = point or governorate.center
        lat, lng, radius = point.lat, point.lng, region.radius_m or point.radius_m
    return {
        "circle": {
            "center": {"latitude": lat, "longitude": lng},
            "radius": float(min(max(radius, 1), MAX_RADIUS_M)),
        }
    }


def _text(value: Any) -> str | None:
    if isinstance(value, dict):
        text = value.get("text")
        return str(text) if text else None
    return None


def _component(place: dict[str, Any], types: tuple[str, ...]) -> str | None:
    for wanted in types:
        for comp in place.get("addressComponents") or []:
            if wanted in (comp.get("types") or []):
                return comp.get("longText") or comp.get("shortText")
    return None


def outside_region(place: dict[str, Any], region: RegionFilter) -> bool:
    """True when the place's own governorate is known and is not the requested one."""
    wanted = find_governorate(region.governorate)
    actual = find_governorate(_component(place, _GOVERNORATE_TYPES))
    return wanted is not None and actual is not None and actual.name != wanted.name


def to_place_result(place: dict[str, Any], region: RegionFilter) -> PlaceResult:
    """Map one Places API place to the contract's PlaceResult (governorate normalized to the English name)."""
    governorate = find_governorate(_component(place, _GOVERNORATE_TYPES))
    city = _component(place, _CITY_TYPES) or (region.cities[0] if len(region.cities) == 1 else None)
    location = place.get("location") or {}
    return PlaceResult(
        source="google_places",
        source_ref=str(place["id"]),
        name=_text(place.get("displayName")) or str(place["id"]),
        category=_text(place.get("primaryTypeDisplayName")),
        address=place.get("formattedAddress"),
        city=city,
        governorate=governorate.name if governorate else region.governorate,
        lat=location.get("latitude"),
        lng=location.get("longitude"),
        phone_national=place.get("nationalPhoneNumber"),
        phone_international=place.get("internationalPhoneNumber"),
        website=place.get("websiteUri"),
        google_maps_url=place.get("googleMapsUri"),
        rating=place.get("rating"),
        reviews_count=place.get("userRatingCount"),
        business_status=place.get("businessStatus"),
        types=list(place.get("types") or []),
        raw=place,
    )


def _error_message(response: httpx.Response) -> str:
    try:
        return str(response.json().get("error", {}).get("message") or response.text[:300])
    except ValueError:
        return response.text[:300]


class GooglePlacesSource:
    name = "google_places"

    def __init__(self, api_key: str | None = None, *, client: httpx.AsyncClient | None = None) -> None:
        self._api_key = api_key if api_key is not None else settings.GOOGLE_PLACES_API_KEY
        if not self._api_key:
            raise GooglePlacesError(
                "GOOGLE_PLACES_API_KEY is not set (see docs/setup-accounts.md), "
                "or set USE_MOCK_ADAPTERS=true."
            )
        self._client = client  # tests inject a mocked client; otherwise one client per search
        self.last_request_count = 0  # billable requests made by the last search() call
        self.last_dropped_count = 0  # places the last search() dropped as outside the requested governorate
        self._sleep = asyncio.sleep

    async def search(self, query: str, *, region: RegionFilter, max_results: int = 20) -> list[PlaceResult]:
        self.last_request_count = 0
        self.last_dropped_count = 0
        limit = max(1, min(max_results, MAX_RESULTS_PER_QUERY))
        body: dict[str, Any] = {
            "textQuery": query,
            "languageCode": "ar",
            "regionCode": "EG",
            "pageSize": min(PAGE_SIZE, limit),
        }
        bias = location_bias(region)
        if bias is not None:
            body["locationBias"] = bias

        results: list[PlaceResult] = []
        seen: set[str] = set()
        fetched = 0  # distinct places Google returned, kept or dropped (drives paging, so cost is unchanged)
        token: str | None = None
        client = self._client or httpx.AsyncClient(timeout=20)
        try:
            while fetched < limit:
                data = await self._post(client, {**body, "pageToken": token} if token else body)
                for place in data.get("places") or []:
                    if "id" not in place or place["id"] in seen:
                        continue
                    seen.add(place["id"])
                    fetched += 1
                    if outside_region(place, region):
                        self.last_dropped_count += 1
                    else:
                        results.append(to_place_result(place, region))
                    if fetched >= limit:
                        break
                token = data.get("nextPageToken")
                if not token:
                    break
        finally:
            if self._client is None:
                await client.aclose()
        if self.last_dropped_count:
            logger.info(
                "places: dropped %d result(s) outside %s", self.last_dropped_count, region.governorate
            )
        return results

    async def _post(self, client: httpx.AsyncClient, body: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": FIELD_MASK,
        }
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await client.post(SEARCH_URL, json=body, headers=headers)
            except httpx.TransportError as exc:
                if attempt < MAX_RETRIES:
                    await self._sleep(self._backoff(attempt))
                    continue
                raise GooglePlacesError(f"Could not reach the Places API: {exc}") from exc

            status = response.status_code
            if status == 200:
                self.last_request_count += 1
                payload: dict[str, Any] = response.json()
                return payload
            if status == 429 or status >= 500:
                if attempt < MAX_RETRIES:
                    logger.warning("places: HTTP %s, retry %d/%d", status, attempt + 1, MAX_RETRIES)
                    await self._sleep(self._backoff(attempt))
                    continue
                raise GooglePlacesError(
                    f"The Places API is unavailable (HTTP {status}): {_error_message(response)}"
                )
            if status == 403:
                raise GooglePlacesError(
                    "Google rejected the API key (HTTP 403). Check that 'Places API (New)' is enabled "
                    "for the project, billing is on, and the key's restrictions allow it. Google said: "
                    + _error_message(response)
                )
            raise GooglePlacesError(
                f"Google rejected the request (HTTP {status}). Check the API key and the request. "
                f"Google said: {_error_message(response)}"
            )
        raise AssertionError("unreachable")  # pragma: no cover

    @staticmethod
    def _backoff(attempt: int) -> float:
        return float(2**attempt) + random.uniform(0, 0.5)
