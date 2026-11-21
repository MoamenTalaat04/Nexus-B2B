import httpx
import pytest
import respx

from app.adapters.base import ContactCandidate
from app.adapters.enrichment.places_contacts import PlacesContactsEnricher
from app.adapters.enrichment.website_crawler import WebsiteCrawlerEnricher
from app.models.enums import ContactType


@pytest.mark.asyncio
async def test_places_contacts_classifies_mobile_and_landline() -> None:
    enricher = PlacesContactsEnricher()
    candidates = [
        ContactCandidate(type=ContactType.MOBILE, value="010 1234 5678", source="google_places"),
        ContactCandidate(type=ContactType.LANDLINE, value="02 2345 6789", source="google_places"),
        ContactCandidate(type=ContactType.MOBILE, value="not a phone", source="google_places"),
    ]
    result = await enricher.enrich(
        lead_name="Test Lead",
        website=None,
        known=candidates,
    )
    assert {(item.type, item.value) for item in result} == {
        (ContactType.MOBILE, "+201012345678"),
        (ContactType.LANDLINE, "+20223456789"),
    }
    assert all(item.source == "google_places" and item.confidence == 0.9 for item in result)


@pytest.mark.asyncio
async def test_places_contacts_deduplicates() -> None:
    enricher = PlacesContactsEnricher()
    result = await enricher.enrich(
        lead_name="Test Lead",
        website=None,
        known=[
            ContactCandidate(type=ContactType.MOBILE, value="+201012345678", source="google_places"),
            ContactCandidate(type=ContactType.MOBILE, value="01012345678", source="google_places"),
        ],
    )
    assert len(result) == 1


@respx.mock
@pytest.mark.asyncio
async def test_website_extracts_contacts_and_socials() -> None:
    homepage = """
    <html><body>
    <a href="/contact">اتصل بنا</a>
    <a href="/about">من نحن</a>
    <p>البريد sales [at] example [dot] com</p>
    <p>Mobile 01012345678</p>
    <a href="tel:+20-11-1234-5678">Call</a>
    <a href="https://wa.me/201012345678">WhatsApp</a>
    <a href="https://facebook.com/example-company">Facebook</a>
    <a href="https://instagram.com/example-company">Instagram</a>
    <a href="https://facebook.com/sharer/sharer.php">Share</a>
    </body></html>
    """
    contact = "<html><body><p>٠١٠١٢٣٤٥٦٧٨</p></body></html>"
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /\n")
    )
    respx.get("https://example.com/").mock(return_value=httpx.Response(200, text=homepage))
    respx.get("https://example.com/contact").mock(return_value=httpx.Response(200, text=contact))
    respx.get("https://example.com/about").mock(return_value=httpx.Response(200, text="<html></html>"))

    async with httpx.AsyncClient(follow_redirects=True) as client:
        enricher = WebsiteCrawlerEnricher(client=client)
        result = await enricher.enrich(
            lead_name="Example",
            website="https://example.com",
            known=[],
        )

    mobile = [item for item in result if item.type == ContactType.MOBILE]
    assert "+201012345678" in {item.value for item in mobile}
    assert "+201112345678" in {item.value for item in mobile}
    assert any(item.type == ContactType.WHATSAPP_LINK and item.confidence == 0.95 for item in result)
    assert any(item.type == ContactType.EMAIL and item.value == "sales@example.com" for item in result)
    assert any(item.type == ContactType.FACEBOOK for item in result)
    assert any(item.type == ContactType.INSTAGRAM for item in result)
    assert not any("sharer" in item.value for item in result)


@respx.mock
@pytest.mark.asyncio
async def test_website_robots_disallow_skips_homepage() -> None:
    respx.get("https://blocked.example/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nDisallow: /\n")
    )
    route = respx.get("https://blocked.example/").mock(
        return_value=httpx.Response(200, text="<html><p>01012345678</p></html>")
    )

    async with httpx.AsyncClient(follow_redirects=True) as client:
        result = await WebsiteCrawlerEnricher(client=client).enrich(
            lead_name="Blocked",
            website="https://blocked.example",
            known=[],
        )

    assert result == []
    assert not route.called


@respx.mock
@pytest.mark.asyncio
async def test_website_respects_page_limit_and_timeout() -> None:
    links = "".join(f'<a href="/contact{i}">اتصل بنا</a>' for i in range(6))
    respx.get("https://limit.example/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /\n")
    )
    respx.get("https://limit.example/").mock(
        return_value=httpx.Response(200, text=f"<html><body>{links}</body></html>")
    )
    for index in range(3):
        respx.get(f"https://limit.example/contact{index}").mock(
            return_value=httpx.Response(200, text=f"<p>01012345{index:03d}</p>")
        )
    extra_route = respx.get("https://limit.example/contact3").mock(
        return_value=httpx.Response(200, text="<p>01012345678</p>")
    )

    async with httpx.AsyncClient(follow_redirects=True) as client:
        result = await WebsiteCrawlerEnricher(client=client).enrich(
            lead_name="Limit",
            website="https://limit.example",
            known=[],
        )

    assert isinstance(result, list)
    assert not extra_route.called


@respx.mock
@pytest.mark.asyncio
async def test_website_skips_page_over_one_megabyte() -> None:
    respx.get("https://large.example/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /\n")
    )
    respx.get("https://large.example/").mock(
        return_value=httpx.Response(
            200,
            headers={"Content-Length": str(1024 * 1024 + 1)},
            content=b"x" * (1024 * 1024 + 1),
        )
    )

    async with httpx.AsyncClient(follow_redirects=True) as client:
        result = await WebsiteCrawlerEnricher(client=client).enrich(
            lead_name="Large",
            website="https://large.example",
            known=[],
        )

    assert result == []


@respx.mock
@pytest.mark.asyncio
async def test_website_timeout_returns_no_contacts() -> None:
    respx.get("https://timeout.example/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /\n")
    )
    respx.get("https://timeout.example/").mock(side_effect=httpx.TimeoutException("timed out"))

    async with httpx.AsyncClient(follow_redirects=True) as client:
        result = await WebsiteCrawlerEnricher(client=client).enrich(
            lead_name="Timeout",
            website="https://timeout.example",
            known=[],
        )

    assert result == []


@respx.mock
@pytest.mark.asyncio
async def test_website_caps_text_phone_candidates_at_five() -> None:
    phones = " ".join(f"+20 10 1234 56{i:02d}" for i in range(20))
    respx.get("https://phones.example/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /\n")
    )
    respx.get("https://phones.example/").mock(
        return_value=httpx.Response(200, text=f"<html><body>{phones}</body></html>")
    )

    async with httpx.AsyncClient(follow_redirects=True) as client:
        result = await WebsiteCrawlerEnricher(client=client).enrich(
            lead_name="Phones",
            website="https://phones.example",
            known=[],
        )

    mobiles = [item for item in result if item.type == ContactType.MOBILE]
    assert len(mobiles) <= 5
