"""Website contact enricher (P3-1)."""

import re
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from app.adapters.base import ContactCandidate
from app.core.phones import is_eg_mobile, normalize_eg_phone
from app.models.enums import ContactType

USER_AGENT = "Nexus-B2B-EnrichmentBot/1.0"
TIMEOUT_SECONDS = 8.0
MAX_PAGE_BYTES = 1024 * 1024
MAX_CONTACT_PAGES = 3
MAX_PHONE_CANDIDATES = 5

_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_EMAIL_RE = re.compile(
    r"[A-Z0-9._%+-]+\s*(?:\[at\]|\(at\)|@)\s*[A-Z0-9.-]+\s*(?:\[dot\]|\(dot\)|\.)\s*[A-Z]{2,}",
    re.IGNORECASE,
)
_PHONE_TEXT_RE = re.compile(
    r"(?:\+?20|0020|0)?1[0125][\s().-]*\d{4}[\s().-]*\d{4}"
    r"|(?:\+?20|0020|0)?0?2[\s().-]*\d{3,4}[\s().-]*\d{4}",
    re.IGNORECASE,
)
_LINK_CONTACT_RE = re.compile(
    r"(contact|اتصل|اتصال|تواصل|about|من\s*نحن|من نحن|عنا)",
    re.IGNORECASE,
)
_FACEBOOK_RE = re.compile(r"https?://(?:www\.|m\.)?facebook\.com/[^\s\"'<>]+", re.IGNORECASE)
_INSTAGRAM_RE = re.compile(r"https?://(?:www\.)?instagram\.com/[^\s\"'<>]+", re.IGNORECASE)
_SOCIAL_IGNORE_RE = re.compile(r"/(?:sharer|share|plugins|dialog|login|signup)(?:/|$)", re.IGNORECASE)


class WebsiteCrawlerEnricher:
    name = "website_crawler"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def enrich(
        self,
        *,
        lead_name: str,
        website: str | None,
        known: list[ContactCandidate],
    ) -> list[ContactCandidate]:
        if not website:
            return []

        parsed = urlparse(website)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return []

        candidates: list[ContactCandidate] = []
        seen: set[tuple[ContactType, str]] = set()
        if self._client is not None:
            await self._crawl(
                self._client,
                website,
                candidates,
                seen,
            )
            return candidates

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(TIMEOUT_SECONDS),
            headers={"User-Agent": USER_AGENT},
        ) as client:
            await self._crawl(client, website, candidates, seen)
        return candidates

    async def _robots_allowed(self, client: httpx.AsyncClient, url: str) -> bool:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        try:
            response = await client.get(
                robots_url,
                timeout=TIMEOUT_SECONDS,
                headers={"User-Agent": USER_AGENT},
            )
            if response.status_code >= 400:
                return True
            robots = RobotFileParser()
            robots.parse(response.text.splitlines())
            return robots.can_fetch(USER_AGENT, url)
        except Exception:
            return True

    async def _fetch_limited(self, client: httpx.AsyncClient, url: str) -> str | None:
        try:
            async with client.stream(
                "GET",
                url,
                timeout=TIMEOUT_SECONDS,
                headers={"User-Agent": USER_AGENT},
            ) as response:
                if response.status_code >= 400:
                    return None
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > MAX_PAGE_BYTES:
                    return None
                size = 0
                chunks: list[bytes] = []
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > MAX_PAGE_BYTES:
                        return None
                    chunks.append(chunk)
                return b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
        except Exception:
            return None

    async def _crawl(
        self,
        client: httpx.AsyncClient,
        website: str,
        candidates: list[ContactCandidate],
        seen: set[tuple[ContactType, str]],
    ) -> None:
        if not await self._robots_allowed(client, website):
            return

        homepage = await self._fetch_limited(client, website)
        if homepage is None:
            return

        pages = [homepage]
        links = self._contact_links(homepage, website)
        for link in links[:MAX_CONTACT_PAGES]:
            if not await self._robots_allowed(client, link):
                continue
            html = await self._fetch_limited(client, link)
            if html is not None:
                pages.append(html)

        tel_count = 0
        text_phone_count = 0
        for html in pages:
            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text(" ", strip=True)
            deobfuscated = (
                text.replace("[at]", "@").replace("(at)", "@").replace("[dot]", ".").replace("(dot)", ".")
            )

            for match in _EMAIL_RE.findall(deobfuscated):
                email = (
                    match.lower()
                    .replace("[at]", "@")
                    .replace("(at)", "@")
                    .replace("[dot]", ".")
                    .replace("(dot)", ".")
                )
                email = re.sub(r"\s+", "", email)
                self._add_candidate(
                    candidates,
                    seen,
                    ContactType.EMAIL,
                    email,
                    "website",
                    0.6,
                )

            for mail_link in soup.find_all("a", href=True):
                mail_href = str(mail_link["href"]).strip()
                if mail_href.lower().startswith("mailto:"):
                    email = mail_href.split(":", 1)[1].split("?", 1)[0].lower()
                    self._add_candidate(
                        candidates,
                        seen,
                        ContactType.EMAIL,
                        email,
                        "website",
                        0.6,
                    )

            for phone_link in soup.find_all("a", href=True):
                phone_href = str(phone_link["href"]).strip()
                if phone_href.lower().startswith("tel:"):
                    raw_tel_phone = phone_href.split(":", 1)[1]
                    tel_normalized = normalize_eg_phone(raw_tel_phone)
                    if tel_normalized and is_eg_mobile(tel_normalized) and tel_count < MAX_PHONE_CANDIDATES:
                        self._add_candidate(
                            candidates,
                            seen,
                            ContactType.MOBILE,
                            tel_normalized,
                            "website",
                            0.85,
                        )
                        tel_count += 1
                    elif tel_normalized and tel_count < MAX_PHONE_CANDIDATES:
                        self._add_candidate(
                            candidates,
                            seen,
                            ContactType.LANDLINE,
                            tel_normalized,
                            "website",
                            0.85,
                        )
                        tel_count += 1

                absolute = urljoin(website, phone_href)
                if re.search(r"(wa\.me/|api\.whatsapp\.com/send)", absolute, re.IGNORECASE):
                    phone_match = re.search(r"wa\.me/([^/?#]+)", absolute, re.IGNORECASE)
                    if phone_match is None:
                        phone_match = re.search(r"[?&]phone=([^&#]+)", absolute)
                    if phone_match:
                        normalized = normalize_eg_phone(phone_match.group(1))
                        if normalized and is_eg_mobile(normalized):
                            self._add_candidate(
                                candidates,
                                seen,
                                ContactType.WHATSAPP_LINK,
                                absolute,
                                "website",
                                0.95,
                            )
                            self._add_candidate(
                                candidates,
                                seen,
                                ContactType.MOBILE,
                                normalized,
                                "website",
                                0.95,
                            )

                for social_re, contact_type in (
                    (_FACEBOOK_RE, ContactType.FACEBOOK),
                    (_INSTAGRAM_RE, ContactType.INSTAGRAM),
                ):
                    for match in social_re.findall(absolute):
                        if _SOCIAL_IGNORE_RE.search(match):
                            continue
                        self._add_candidate(
                            candidates,
                            seen,
                            contact_type,
                            match,
                            "website",
                            0.6,
                        )

            translated_text = text.translate(_ARABIC_DIGITS)
            for raw_phone in _PHONE_TEXT_RE.findall(translated_text):
                normalized = normalize_eg_phone(raw_phone)
                if not normalized:
                    continue
                if is_eg_mobile(normalized):
                    if text_phone_count >= MAX_PHONE_CANDIDATES:
                        continue
                    self._add_candidate(
                        candidates,
                        seen,
                        ContactType.MOBILE,
                        normalized,
                        "website",
                        0.6,
                    )
                    text_phone_count += 1
                elif text_phone_count < MAX_PHONE_CANDIDATES:
                    self._add_candidate(
                        candidates,
                        seen,
                        ContactType.LANDLINE,
                        normalized,
                        "website",
                        0.6,
                    )
                    text_phone_count += 1

    def _contact_links(self, html: str, base_url: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        links: list[str] = []
        seen: set[str] = set()
        for link in soup.find_all("a", href=True):
            href = str(link["href"]).strip()
            label = link.get_text(" ", strip=True)
            if not _LINK_CONTACT_RE.search(f"{label} {href}"):
                continue
            absolute = urljoin(base_url, href)
            parsed = urlparse(absolute)
            if parsed.scheme not in {"http", "https"} or parsed.netloc == "":
                continue
            if absolute not in seen:
                seen.add(absolute)
                links.append(absolute)
            if len(links) >= MAX_CONTACT_PAGES:
                break
        return links

    @staticmethod
    def _add_candidate(
        candidates: list[ContactCandidate],
        seen: set[tuple[ContactType, str]],
        contact_type: ContactType,
        value: str,
        source: str,
        confidence: float,
    ) -> None:
        key = (contact_type, value)
        if key in seen:
            return
        seen.add(key)
        candidates.append(
            ContactCandidate(
                type=contact_type,
                value=value,
                source=source,
                confidence=confidence,
            )
        )
