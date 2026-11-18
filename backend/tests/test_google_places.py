"""P2-1: the Google Places adapter (HTTP mocked with respx), the Egypt coordinates and the registry."""

import json
from typing import Any

import httpx
import pytest
import respx

from app.adapters import registry
from app.adapters.base import RegionFilter
from app.adapters.search.google_places import (
    FIELD_MASK,
    SEARCH_URL,
    GooglePlacesError,
    GooglePlacesSource,
    location_bias,
)
from app.config import settings
from app.core.geo_eg_coords import GOVERNORATES, MAX_RADIUS_M, find_city, find_governorate

CAIRO = RegionFilter(governorate="Cairo")


def place(i: int, **overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": f"place-{i}",
        "displayName": {"text": f"محل نونو لملابس الأطفال {i}", "languageCode": "ar"},
        "formattedAddress": "شارع عباس العقاد، مدينة نصر، القاهرة",
        "addressComponents": [
            {"longText": "مدينة نصر", "shortText": "مدينة نصر", "types": ["locality", "political"]},
            {
                "longText": "محافظة القاهرة",
                "shortText": "محافظة القاهرة",
                "types": ["administrative_area_level_1", "political"],
            },
        ],
        "location": {"latitude": 30.05, "longitude": 31.33},
        "types": ["clothing_store", "store"],
        "primaryTypeDisplayName": {"text": "متجر ملابس", "languageCode": "ar"},
        "nationalPhoneNumber": "010 12345678",
        "internationalPhoneNumber": "+20 10 12345678",
        "websiteUri": "https://nono.example.com",
        "googleMapsUri": f"https://maps.google.com/?cid={i}",
        "rating": 4.5,
        "userRatingCount": 120,
        "businessStatus": "OPERATIONAL",
    }
    data.update(overrides)
    return data


def page(ids: range, token: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"places": [place(i) for i in ids]}
    if token:
        body["nextPageToken"] = token
    return body


@pytest.fixture
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    slept: list[float] = []

    async def fake_sleep(delay: float) -> None:
        slept.append(delay)

    monkeypatch.setattr("app.adapters.search.google_places.asyncio.sleep", fake_sleep)
    return slept


def source() -> GooglePlacesSource:
    return GooglePlacesSource(api_key="test-places-key")


def sent(route: respx.Route, index: int) -> dict[str, Any]:
    return json.loads(route.calls[index].request.content)


@respx.mock
async def test_request_headers_and_body() -> None:
    route = respx.post(SEARCH_URL).mock(return_value=httpx.Response(200, json=page(range(3))))
    results = await source().search(
        "محل ملابس اطفال", region=RegionFilter(governorate="Cairo", cities=["Nasr City"])
    )

    request = route.calls[0].request
    assert request.headers["X-Goog-Api-Key"] == "test-places-key"
    assert request.headers["X-Goog-FieldMask"] == FIELD_MASK
    assert " " not in FIELD_MASK and "nextPageToken" in FIELD_MASK
    assert FIELD_MASK.startswith("places.id,places.displayName,")
    body = sent(route, 0)
    assert body["textQuery"] == "محل ملابس اطفال"
    assert body["languageCode"] == "ar" and body["regionCode"] == "EG" and body["pageSize"] == 20
    nasr = find_city(GOVERNORATES["Cairo"], "Nasr City")
    assert nasr is not None
    assert body["locationBias"] == {
        "circle": {"center": {"latitude": nasr.lat, "longitude": nasr.lng}, "radius": float(nasr.radius_m)}
    }
    assert len(results) == 3


@respx.mock
async def test_mapping_arabic_names_and_governorate() -> None:
    respx.post(SEARCH_URL).mock(return_value=httpx.Response(200, json=page(range(1))))
    (r,) = await source().search("x", region=CAIRO)
    assert r.source == "google_places" and r.source_ref == "place-0"
    assert r.name == "محل نونو لملابس الأطفال 0"
    assert r.category == "متجر ملابس"
    assert r.governorate == "Cairo"  # "محافظة القاهرة" mapped to the English name the app uses
    assert r.city == "مدينة نصر"
    assert (r.lat, r.lng) == (30.05, 31.33)
    assert r.phone_national == "010 12345678" and r.phone_international == "+20 10 12345678"
    assert r.website == "https://nono.example.com" and r.google_maps_url == "https://maps.google.com/?cid=0"
    assert (r.rating, r.reviews_count, r.business_status) == (4.5, 120, "OPERATIONAL")
    assert r.types == ["clothing_store", "store"]
    assert r.raw["id"] == "place-0"


@respx.mock
async def test_missing_phone_website_and_address_parts_fall_back() -> None:
    bare = {"id": "p1", "displayName": {"text": "Baby Shop"}}
    respx.post(SEARCH_URL).mock(return_value=httpx.Response(200, json={"places": [bare]}))
    region = RegionFilter(governorate="Giza", cities=["Dokki"])
    (r,) = await source().search("baby shop", region=region)
    assert r.phone_national is None and r.phone_international is None and r.website is None
    assert r.rating is None and r.reviews_count is None and r.types == []
    assert (r.governorate, r.city) == ("Giza", "Dokki")  # from the RegionFilter


@respx.mock
async def test_pagination_up_to_60_with_identical_parameters() -> None:
    route = respx.post(SEARCH_URL).mock(
        side_effect=[
            httpx.Response(200, json=page(range(0, 20), "t1")),
            httpx.Response(200, json=page(range(20, 40), "t2")),
            httpx.Response(200, json=page(range(40, 55))),
        ]
    )
    src = source()
    results = await src.search("kids wear", region=CAIRO, max_results=100)  # capped at 60
    assert len(results) == 55 and len({r.source_ref for r in results}) == 55
    assert src.last_request_count == 3
    first, second, third = (sent(route, i) for i in range(3))
    assert "pageToken" not in first
    assert second.pop("pageToken") == "t1" and third.pop("pageToken") == "t2"
    assert first == second == third  # every other parameter unchanged, as the API requires


@respx.mock
async def test_stops_at_max_results() -> None:
    route = respx.post(SEARCH_URL).mock(
        side_effect=[
            httpx.Response(200, json=page(range(0, 20), "t1")),
            httpx.Response(200, json=page(range(20, 40), "t2")),
        ]
    )
    src = source()
    results = await src.search("kids wear", region=CAIRO, max_results=25)
    assert len(results) == 25
    assert len(route.calls) == 2 and src.last_request_count == 2


@respx.mock
async def test_duplicate_places_across_pages_are_skipped() -> None:
    respx.post(SEARCH_URL).mock(
        side_effect=[
            httpx.Response(200, json=page(range(0, 3), "t1")),
            httpx.Response(200, json=page(range(2, 5))),
        ]
    )
    results = await source().search("x", region=CAIRO, max_results=60)
    assert [r.source_ref for r in results] == [f"place-{i}" for i in range(5)]


@respx.mock
async def test_403_gives_a_clear_message_and_is_not_retried(no_sleep: list[float]) -> None:
    route = respx.post(SEARCH_URL).mock(
        return_value=httpx.Response(403, json={"error": {"message": "Places API (New) has not been used"}})
    )
    with pytest.raises(GooglePlacesError, match=r"Places API \(New\)' is enabled"):
        await source().search("x", region=CAIRO)
    assert len(route.calls) == 1 and no_sleep == []


@respx.mock
async def test_400_shows_googles_message() -> None:
    respx.post(SEARCH_URL).mock(
        return_value=httpx.Response(
            400, json={"error": {"message": "API key not valid. Please pass a valid API key."}}
        )
    )
    with pytest.raises(GooglePlacesError, match="API key not valid"):
        await source().search("x", region=CAIRO)


@respx.mock
async def test_429_and_5xx_are_retried(no_sleep: list[float]) -> None:
    route = respx.post(SEARCH_URL).mock(
        side_effect=[
            httpx.Response(429, json={"error": {"message": "quota"}}),
            httpx.Response(503, text="unavailable"),
            httpx.ConnectError("down"),
            httpx.Response(200, json=page(range(2))),
        ]
    )
    src = source()
    assert len(await src.search("x", region=CAIRO)) == 2
    assert len(route.calls) == 4 and len(no_sleep) == 3
    assert src.last_request_count == 1  # failed attempts are not billable


@respx.mock
async def test_gives_up_after_retries(no_sleep: list[float]) -> None:
    respx.post(SEARCH_URL).mock(return_value=httpx.Response(500, text="boom"))
    with pytest.raises(GooglePlacesError, match="unavailable"):
        await source().search("x", region=CAIRO)


def test_missing_key_is_a_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GOOGLE_PLACES_API_KEY", "")
    with pytest.raises(GooglePlacesError, match="GOOGLE_PLACES_API_KEY"):
        GooglePlacesSource()


# ---------------------------------------------------------------------------------------------- location bias


def test_location_bias_choices() -> None:
    giza = GOVERNORATES["Giza"]
    by_governorate = location_bias(RegionFilter(governorate="الجيزة", cities=["Dokki", "Haram"]))
    assert by_governorate == {
        "circle": {
            "center": {"latitude": giza.center.lat, "longitude": giza.center.lng},
            "radius": float(giza.center.radius_m),
        }
    }
    explicit = location_bias(RegionFilter(governorate="Cairo", lat=30.1, lng=31.2, radius_m=90_000))
    assert explicit is not None and explicit["circle"]["radius"] == MAX_RADIUS_M  # capped at 50 km
    assert location_bias(RegionFilter(governorate="Atlantis")) is None


def test_all_27_governorates_with_valid_points() -> None:
    assert len(GOVERNORATES) == 27
    for g in GOVERNORATES.values():
        for point in [g.center, *g.cities.values()]:
            assert 22 <= point.lat <= 32 and 24 <= point.lng <= 37, g.name  # inside Egypt's bounding box
            assert 0 < point.radius_m <= MAX_RADIUS_M
        assert find_governorate(g.name) is g and find_governorate(g.name_ar) is g
    assert find_governorate("محافظة الإسكندرية") is GOVERNORATES["Alexandria"]
    assert find_governorate("Kafr el-Sheikh Governorate") is GOVERNORATES["Kafr El Sheikh"]


# ---------------------------------------------------------------------------------------------- registry


def test_registry_returns_google_places_in_real_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "USE_MOCK_ADAPTERS", False)
    monkeypatch.setattr(settings, "GOOGLE_PLACES_API_KEY", "k")
    assert isinstance(registry.get_search_source("google_places"), GooglePlacesSource)
    with pytest.raises(ValueError, match="Unknown search source"):
        registry.get_search_source("bing")


def test_registry_mock_mode_names_the_task_that_adds_the_mock() -> None:
    try:
        import app.adapters.search.mock  # noqa: F401
    except ModuleNotFoundError:
        with pytest.raises(NotImplementedError, match="P0-1"):
            registry.get_search_source()
    else:  # A's mock has landed
        assert registry.get_search_source().name
