"""AI-assisted company profile & ICP description helper for Onboarding / Settings."""

from __future__ import annotations

import asyncio
import logging
import re
import tempfile
import uuid
from pathlib import Path
from typing import Literal
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.adapters.llm.base import LLMProviderError
from app.agents.llm import LLMInvalidOutput, LLMOutputTruncated, LLMRefused, ModelTier, llm_structured
from app.core.errors import AppError
from app.core.tracing import agent_run
from app.db import SessionLocal
from app.models.enums import AgentRunKind, AgentRunStatus
from app.models.runs import AgentRun
from app.schemas.settings import ProductIn
from app.services.knowledge import KnowledgeExtractionError, extract_knowledge_text

logger = logging.getLogger("app.services.company_assist")

AI_ATTEMPT_LIMIT = 3
_QUOTA_KEYS = (
    "description",
    "ideal_customer_text",
    "offerings",
    "knowledge_catalog",
    "knowledge_pricing",
    "knowledge_faq",
    "knowledge_case_studies",
)


async def get_ai_quota_summary(tenant_id: uuid.UUID) -> dict[str, Any]:
    """Count succeeded manual onboarding AI assists per field and return remaining tries."""
    counts: dict[str, int] = {k: 0 for k in _QUOTA_KEYS}
    try:
        async with SessionLocal() as session:
            rows = (
                await session.execute(
                    select(AgentRun.input).where(
                        AgentRun.tenant_id == tenant_id,
                        AgentRun.kind == AgentRunKind.ICP_BUILD.value,
                        AgentRun.trigger == "manual",
                        AgentRun.status == AgentRunStatus.SUCCEEDED.value,
                    )
                )
            ).scalars().all()
        for payload in rows:
            if not isinstance(payload, dict):
                continue
            if payload.get("assist_field") in ("description", "ideal_customer_text"):
                key = str(payload["assist_field"])
                counts[key] += 1
            elif payload.get("extract_offerings") is True:
                counts["offerings"] += 1
            elif payload.get("knowledge_doc_type") in ("catalog", "pricing", "faq", "case_studies"):
                key = f"knowledge_{payload['knowledge_doc_type']}"
                counts[key] += 1
    except Exception:
        pass
    remaining = {k: max(0, AI_ATTEMPT_LIMIT - counts[k]) for k in _QUOTA_KEYS}
    return {"limit": AI_ATTEMPT_LIMIT, "remaining": remaining}


async def _enforce_ai_quota(tenant_id: uuid.UUID, quota_key: str) -> None:
    summary = await get_ai_quota_summary(tenant_id)
    if summary["remaining"].get(quota_key, AI_ATTEMPT_LIMIT) <= 0:
        raise AppError(
            "ai_quota_exceeded",
            f"You have used all {AI_ATTEMPT_LIMIT} AI attempts for this section.",
            status_code=429,
        )

_FETCH_TIMEOUT = 8.0
_MAX_HTML_BYTES = 512 * 1024
_MAX_SUBPAGES = 3
_MAX_TOTAL_CHARS = 60000
_discovered_tpm_limit: int | None = None


class _ChunkFacts(BaseModel):
    facts: str = Field(min_length=5, max_length=2000)


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    non_ascii = sum(1 for ch in text if ord(ch) > 127)
    ascii_chars = len(text) - non_ascii
    # Arabic/non-ASCII tokenizes denser (~1.5 chars/token) than ASCII (~3.2 chars/token)
    return max(1, int(non_ascii / 1.5 + ascii_chars / 3.2))


def _parse_tpm_limit(exc: Exception) -> int | None:
    match = re.search(r"\bLimit\s+(\d+)\b", str(exc))
    if match:
        return int(match.group(1))
    return None


def _parse_tpm_requested(exc: Exception) -> int | None:
    match = re.search(r"\bRequested\s+(\d+)\b", str(exc))
    if match:
        return int(match.group(1))
    return None


def _is_payload_too_large(exc: LLMProviderError) -> bool:
    return exc.status_code == 413 or "413" in str(exc) or "request too large" in str(exc).lower()


def _dedupe_text_blocks(text: str) -> str:
    """Remove repeated boilerplate lines across crawled pages while keeping unique content."""
    seen: set[str] = set()
    kept: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        norm = re.sub(r"\s+", " ", line).lower()
        if len(norm) >= 12 and norm in seen:
            continue
        seen.add(norm)
        kept.append(line)
    return "\n".join(kept)


def _split_chunks(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for block in re.split(r"\n{2,}|(?:\n---\n)", text):
        part = block.strip()
        if not part:
            continue
        if len(part) > max_chars:
            for i in range(0, len(part), max_chars):
                sub = part[i : i + max_chars]
                if current:
                    chunks.append("\n\n".join(current))
                    current, current_len = [], 0
                chunks.append(sub)
            continue
        if current_len + len(part) + 2 > max_chars and current:
            chunks.append("\n\n".join(current))
            current, current_len = [], 0
        current.append(part)
        current_len += len(part) + 2
    if current:
        chunks.append("\n\n".join(current))
    return chunks


async def _smart_llm_structured[T: BaseModel](
    run: Any,
    *,
    name: str,
    system: str,
    source_text: str,
    build_user_prompt: Any,
    map_instruction: str,
    output_model: type[T],
    desired_max_tokens: int,
) -> T:
    """Send full context optimistically; auto-detect 413 TPM limits and fall back to Map-Reduce."""
    global _discovered_tpm_limit
    cleaned = _dedupe_text_blocks(source_text)
    full_user = build_user_prompt(cleaned)
    est_prompt_tokens = _estimate_tokens(system) + _estimate_tokens(full_user) + 250

    can_try_full = (
        _discovered_tpm_limit is None
        or (est_prompt_tokens + 700) <= _discovered_tpm_limit
    )

    if can_try_full:
        effective_max = (
            min(desired_max_tokens, max(700, _discovered_tpm_limit - est_prompt_tokens))
            if _discovered_tpm_limit is not None
            else desired_max_tokens
        )
        try:
            return await llm_structured(
                run,
                name=name,
                tier=ModelTier.SMART,
                effort="low",
                system=system,
                user=full_user,
                output_model=output_model,
                max_tokens=effective_max,
            )
        except LLMProviderError as exc:
            if not _is_payload_too_large(exc):
                raise
            parsed_limit = _parse_tpm_limit(exc) or 8000
            _discovered_tpm_limit = parsed_limit
            logger.info("Detected TPM limit %d for %s; switching to Map-Reduce", parsed_limit, name)

    # Map-Reduce path: distill every chunk without losing tail/other pages
    limit = _discovered_tpm_limit or 8000
    map_output_tokens = min(650, max(350, limit // 6))
    overhead_tokens = 650  # system + JSON schema instructions + framing
    chunk_input_tokens = max(600, limit - map_output_tokens - overhead_tokens)
    chunk_chars = chunk_input_tokens * 2

    chunks = _split_chunks(cleaned, chunk_chars)[:8]
    distilled_parts: list[str] = []
    for idx, chunk in enumerate(chunks, start=1):
        try:
            res = await llm_structured(
                run,
                name=f"{name}.map",
                tier=ModelTier.FAST,
                effort="low",
                system=(
                    "You are a concise information extractor. "
                    f"{map_instruction} "
                    "Return dense, factual bullet points preserving exact names, prices, and specs."
                ),
                user=f"Section {idx}/{len(chunks)}:\n{chunk}",
                output_model=_ChunkFacts,
                max_tokens=map_output_tokens,
            )
            distilled_parts.append(res.facts.strip())
        except LLMProviderError as exc:
            if _is_payload_too_large(exc):
                sub_limit = _parse_tpm_limit(exc)
                if sub_limit and sub_limit < limit:
                    _discovered_tpm_limit = sub_limit
            logger.warning("Map chunk %d/%d skipped due to provider error: %s", idx, len(chunks), exc)

    merged_context = "\n\n".join(distilled_parts) if distilled_parts else cleaned[:chunk_chars]
    schema_overhead = 650
    reduce_overhead = _estimate_tokens(system) + _estimate_tokens(build_user_prompt("")) + schema_overhead
    target_reduce_output = min(desired_max_tokens, max(900, limit // 3))
    max_reduce_tokens = max(600, limit - reduce_overhead - target_reduce_output)
    while _estimate_tokens(merged_context) > max_reduce_tokens and len(merged_context) > 400:
        merged_context = merged_context[: int(len(merged_context) * 0.8)]

    reduce_user = build_user_prompt(merged_context)
    est_reduce = _estimate_tokens(system) + _estimate_tokens(reduce_user) + schema_overhead
    reduce_max_tokens = min(desired_max_tokens, max(700, limit - est_reduce))

    try:
        return await llm_structured(
            run,
            name=f"{name}.reduce",
            tier=ModelTier.SMART,
            effort="low",
            system=system,
            user=reduce_user,
            output_model=output_model,
            max_tokens=reduce_max_tokens,
        )
    except LLMProviderError as exc:
        if not _is_payload_too_large(exc):
            raise
        actual_limit = _parse_tpm_limit(exc) or limit
        requested = _parse_tpm_requested(exc) or (actual_limit + 600)
        overshoot = max(400, requested - actual_limit + 400)
        _discovered_tpm_limit = actual_limit
        # Trim merged_context + reduce_max_tokens by the exact overshoot so retry fits under limit
        tighter_output = max(600, reduce_max_tokens - overshoot // 2)
        trimmed_chars = max(500, len(merged_context) - overshoot * 2)
        tighter_user = build_user_prompt(merged_context[:trimmed_chars])
        return await llm_structured(
            run,
            name=f"{name}.reduce_fit",
            tier=ModelTier.SMART,
            effort="low",
            system=system,
            user=tighter_user,
            output_model=output_model,
            max_tokens=tighter_output,
        )
_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
_RELEVANT_LINK_RE = re.compile(
    r"(about|company|who-we-are|what-we-do|service|product|solution|feature|pricing|overview|"
    r"من-نحن|من_نحن|عن-الشركة|خدمات|منتجات)",
    re.IGNORECASE,
)


class _AssistResult(BaseModel):
    text: str = Field(min_length=10, max_length=2500)


def _normalize_url(raw: str | None) -> str | None:
    if not raw or not raw.strip():
        return None
    url = raw.strip()
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = f"https://{url}"
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return url


def _extract_page_summary(url: str, html: str) -> tuple[str, list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()

    parts: list[str] = [f"URL: {url}"]
    if soup.title and soup.title.string:
        parts.append(f"Title: {soup.title.string.strip()}")

    for attr_name, attr_val in (
        ("name", "description"),
        ("property", "og:title"),
        ("property", "og:description"),
    ):
        meta = soup.find("meta", attrs={attr_name: attr_val})
        if meta and meta.get("content"):
            parts.append(f"{attr_val}: {str(meta['content']).strip()}")

    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()
    if text:
        parts.append(f"Content: {text[:3500]}")

    parsed_base = urlparse(url)
    links: list[str] = []
    seen: set[str] = {url}
    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"]).strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        abs_url = urljoin(url, href).split("#")[0]
        parsed_link = urlparse(abs_url)
        if parsed_link.scheme not in {"http", "https"} or parsed_link.netloc != parsed_base.netloc:
            continue
        if abs_url in seen:
            continue
        anchor_text = anchor.get_text(" ", strip=True)
        if _RELEVANT_LINK_RE.search(parsed_link.path) or _RELEVANT_LINK_RE.search(anchor_text):
            seen.add(abs_url)
            links.append(abs_url)
            if len(links) >= _MAX_SUBPAGES:
                break

    return "\n".join(parts), links


async def _fetch_html(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        resp = await client.get(url)
    except httpx.HTTPError:
        return None
    if resp.status_code >= 400:
        return None
    content_type = resp.headers.get("content-type", "")
    if "html" not in content_type.lower() and "text/" not in content_type.lower():
        return None
    return resp.text[:_MAX_HTML_BYTES]


async def _crawl_website(url: str) -> tuple[str, int]:
    """Fetch the given URL plus up to 3 relevant same-origin pages."""
    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
    }
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(_FETCH_TIMEOUT),
        headers=headers,
    ) as client:
        main_html = await _fetch_html(client, url)
        if not main_html:
            return "", 0

        main_summary, sub_links = _extract_page_summary(url, main_html)
        summaries = [main_summary]
        pages_count = 1

        if sub_links:
            sub_htmls = await asyncio.gather(*(_fetch_html(client, link) for link in sub_links))
            for link, html in zip(sub_links, sub_htmls, strict=True):
                if not html:
                    continue
                sub_summary, _ = _extract_page_summary(link, html)
                summaries.append(sub_summary)
                pages_count += 1

        combined = "\n\n---\n\n".join(summaries)
        return combined[:_MAX_TOTAL_CHARS], pages_count


def _build_prompts(
    *,
    field: Literal["description", "ideal_customer_text"],
    mode: Literal["generate", "enhance"],
    company_name: str,
    website: str | None,
    website_context: str,
    current_text: str,
    other_text: str,
) -> tuple[str, str]:
    field_goal = (
        "a clear, high-signal overview of what the company does, what products/services it sells, "
        "its core value proposition, and its industry (2-4 concise sentences, plain text, no bullet lists)"
        if field == "description"
        else "a clear, actionable Ideal Customer Profile (ICP) description covering target industries/business types, "
        "company size or decision-maker roles, key pain points solved, and buying signals (2-4 concise sentences, plain text)"
    )

    if mode == "enhance":
        system = (
            "You are an expert B2B GTM and AI SDR strategist. "
            "Your job is to rewrite and structure a user's rough draft into "
            f"{field_goal}. "
            "Preserve all factual details and intent from the user's draft, fix clarity and structure so downstream "
            "B2B lead-sourcing and qualification AI agents can use it effectively, and match the language of the user's draft "
            "(Arabic if the draft is in Arabic, otherwise English). Return only the polished text."
        )
        user_parts = [f"User's draft to enhance:\n{current_text.strip()}"]
        if company_name:
            user_parts.append(f"Company name: {company_name}")
        if website:
            user_parts.append(f"Website: {website}")
        if other_text.strip():
            sibling_label = "Ideal Customer Description" if field == "description" else "Company Description"
            user_parts.append(f"Additional context ({sibling_label}): {other_text.strip()}")
        return system, "\n\n".join(user_parts)

    system = (
        "You are an expert B2B GTM and AI SDR strategist. "
        f"Based on the available company information, write {field_goal}. "
        "Be specific and grounded in the provided website content when available; if only the company name is provided "
        "or the website could not be read, make your best realistic B2B inference from the name and context without "
        "inventing fake metrics or awards. Match Arabic if the company info/website is primarily Arabic, otherwise write in clear English."
    )
    user_parts = []
    if company_name:
        user_parts.append(f"Company name: {company_name}")
    if website:
        user_parts.append(f"Website/URL: {website}")
    if website_context:
        user_parts.append(f"Extracted website content:\n{website_context}")
    else:
        user_parts.append("No readable website content was available; infer carefully from the company name and context.")
    if other_text.strip():
        sibling_label = "Ideal Customer Description" if field == "description" else "Company Description"
        user_parts.append(f"Additional context ({sibling_label}): {other_text.strip()}")
    if current_text.strip():
        user_parts.append(f"Existing notes in field: {current_text.strip()}")
    return system, "\n\n".join(user_parts)


async def assist_company_field(
    *,
    tenant_id: uuid.UUID,
    field: Literal["description", "ideal_customer_text"],
    mode: Literal["generate", "enhance"],
    company_name: str,
    website: str | None,
    current_text: str,
    other_text: str = "",
) -> tuple[str, str]:
    """Generate or enhance a company onboarding field using website crawling + active LLM."""
    clean_company = company_name.strip()
    clean_current = current_text.strip()
    normalized_url = _normalize_url(website)

    if mode == "enhance" and not clean_current:
        raise AppError("empty_text", "Write a short draft in this field first so AI can enhance it.", status_code=422)

    if mode == "generate" and not normalized_url:
        raise AppError(
            "missing_website",
            "Add your website URL in the Website field first so AI can analyze it.",
            status_code=422,
        )

    await _enforce_ai_quota(tenant_id, field)

    website_context = ""
    pages_count = 0
    if mode == "generate" and normalized_url:
        website_context, pages_count = await _crawl_website(normalized_url)
        if not website_context:
            raise AppError(
                "website_unreadable",
                "Could not read content from that website URL. Please check the link or write your draft manually.",
                status_code=422,
            )

    system, user_prompt = _build_prompts(
        field=field,
        mode=mode,
        company_name=clean_company,
        website=normalized_url or (website.strip() if website else None),
        website_context=website_context,
        current_text=clean_current,
        other_text=other_text,
    )

    try:
        async with agent_run(
            tenant_id,
            AgentRunKind.ICP_BUILD,
            trigger="manual",
            input={"assist_field": field, "mode": mode, "has_website": bool(normalized_url)},
        ) as run:
            if mode == "generate" and website_context:
                result = await _smart_llm_structured(
                    run,
                    name=f"company_assist.{mode}",
                    system=system,
                    source_text=website_context,
                    build_user_prompt=lambda ctx: _build_prompts(
                        field=field,
                        mode=mode,
                        company_name=clean_company,
                        website=normalized_url or (website.strip() if website else None),
                        website_context=ctx,
                        current_text=clean_current,
                        other_text=other_text,
                    )[1],
                    map_instruction=(
                        "Extract what the company sells/does, its value proposition, target industries, and ideal buyers."
                    ),
                    output_model=_AssistResult,
                    desired_max_tokens=2000,
                )
            else:
                result = await llm_structured(
                    run,
                    name=f"company_assist.{mode}",
                    tier=ModelTier.SMART,
                    effort="low",
                    system=system,
                    user=user_prompt,
                    output_model=_AssistResult,
                    max_tokens=2000,
                )
            run.output_summary = {"field": field, "mode": mode, "chars": len(result.text)}
    except (LLMProviderError, LLMRefused, LLMOutputTruncated, LLMInvalidOutput) as exc:
        logger.warning("Company AI assist failed (%s/%s): %s", field, mode, exc)
        raise AppError(
            "ai_assist_failed",
            "Could not reach an active AI provider right now. Please try again or edit manually.",
            status_code=502,
        ) from exc

    if mode == "enhance":
        summary = "Enhanced & structured with AI"
    elif pages_count > 0:
        summary = f"Analyzed website ({pages_count} page{'s' if pages_count > 1 else ''})"
    else:
        summary = "Generated from company name"

    return result.text.strip(), summary


class _OfferingsResult(BaseModel):
    items: list[ProductIn] = Field(min_length=1, max_length=15)


_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _extract_uploaded_catalog_text(file_bytes: bytes, filename: str, mime_type: str) -> str:
    if len(file_bytes) > _MAX_UPLOAD_BYTES:
        raise AppError("file_too_large", "Catalog file must be 10 MB or smaller.", status_code=422)
    suffix = Path(filename or "catalog.txt").suffix.lower() or ".txt"
    if suffix == ".csv" or mime_type.lower().strip() == "text/csv":
        text = file_bytes.decode("utf-8", errors="ignore").strip()
        if not text:
            raise AppError("empty_file", "The uploaded CSV file is empty.", status_code=422)
        return text[:_MAX_TOTAL_CHARS]

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
        tmp.write(file_bytes)
        tmp.flush()
        try:
            text = extract_knowledge_text(tmp.name, mime_type)
        except KnowledgeExtractionError as exc:
            code = str(exc)
            if code == "unsupported_file_type":
                raise AppError(
                    "unsupported_file_type",
                    "Please upload a PDF, DOCX, TXT, MD, or CSV catalog.",
                    status_code=422,
                ) from exc
            raise AppError("extraction_failed", "Could not read text from this catalog file.", status_code=422) from exc

    if not text.strip():
        raise AppError("empty_file", "No readable text was found in this catalog file.", status_code=422)
    return text[:_MAX_TOTAL_CHARS]


async def extract_offerings_from_source(
    *,
    tenant_id: uuid.UUID,
    company_name: str,
    website: str | None,
    description: str,
    file_bytes: bytes | None = None,
    filename: str = "",
    mime_type: str = "",
) -> tuple[list[ProductIn], str]:
    """Extract structured products and services from an uploaded catalog or company website."""
    clean_company = company_name.strip()
    clean_desc = description.strip()
    normalized_url = _normalize_url(website)

    await _enforce_ai_quota(tenant_id, "offerings")

    source_text = ""
    pages_count = 0
    used_file = False

    if file_bytes is not None:
        used_file = True
        source_text = _extract_uploaded_catalog_text(file_bytes, filename, mime_type)
    else:
        if not normalized_url:
            raise AppError(
                "missing_website",
                "Add your website URL in Step 1 first, or upload a catalog file.",
                status_code=422,
            )
        source_text, pages_count = await _crawl_website(normalized_url)
        if not source_text:
            raise AppError(
                "website_unreadable",
                "Could not read content from that website URL. Try uploading a catalog file instead.",
                status_code=422,
            )

    system = (
        "You are an expert B2B product & service catalog analyst. "
        "Extract the distinct offerings (both physical/digital products AND services such as rentals, subscriptions, "
        "consulting, maintenance, SaaS, or agency packages) from the provided source. "
        "For each item set `kind` to 'product' or 'service', provide a concise `name`, optional `price_range` if stated "
        "(else null), optional `min_order` (MOQ for products or minimum commitment/scope for services, else null), "
        "and a crisp 1-2 sentence `description`. Match the language of the source (Arabic if primarily Arabic, else English)."
    )
    def _build_offerings_user(ctx: str) -> str:
        parts: list[str] = []
        if clean_company:
            parts.append(f"Company name: {clean_company}")
        if normalized_url:
            parts.append(f"Website: {normalized_url}")
        if clean_desc:
            parts.append(f"Company description: {clean_desc}")
        if ctx:
            label = f"Uploaded catalog ({filename or 'file'})" if used_file else "Extracted website content"
            parts.append(f"{label}:\n{ctx}")
        return "\n\n".join(parts)

    try:
        async with agent_run(
            tenant_id,
            AgentRunKind.ICP_BUILD,
            trigger="manual",
            input={"extract_offerings": True, "used_file": used_file, "has_website": bool(normalized_url)},
        ) as run:
            result = await _smart_llm_structured(
                run,
                name="company_assist.extract_offerings",
                system=system,
                source_text=source_text,
                build_user_prompt=_build_offerings_user,
                map_instruction=(
                    "Extract every distinct product and service offered, including pricing, MOQ/commitment, and short description."
                ),
                output_model=_OfferingsResult,
                desired_max_tokens=3000,
            )
            run.output_summary = {"items": len(result.items), "used_file": used_file}
    except (LLMProviderError, LLMRefused, LLMOutputTruncated, LLMInvalidOutput) as exc:
        logger.warning("Offerings AI extract failed: %s", exc)
        raise AppError(
            "ai_assist_failed",
            "Could not extract products/services with AI right now. Please try again or add manually.",
            status_code=502,
        ) from exc

    if used_file:
        summary = f"Extracted {len(result.items)} item(s) from {filename or 'catalog'}"
    elif pages_count > 0:
        summary = f"Extracted {len(result.items)} item(s) from website ({pages_count} page{'s' if pages_count > 1 else ''})"
    else:
        summary = f"Suggested {len(result.items)} item(s) from company info"

    return result.items, summary


KnowledgeDocType = Literal["catalog", "pricing", "faq", "case_studies"]

_DOC_SPECS: dict[KnowledgeDocType, tuple[str, str]] = {
    "catalog": (
        "company-catalog.md",
        "a comprehensive Product & Service Catalog in Markdown covering offerings, features, specs, deliverables, and target use cases",
    ),
    "pricing": (
        "pricing-packages.md",
        "a structured Price List & Packages guide in Markdown covering pricing tiers, packages, MOQs/commitments, and commercial terms found on the site",
    ),
    "faq": (
        "faqs-objections.md",
        "a B2B FAQs & Objection Handling document in Markdown answering common buyer questions about the offerings, onboarding, delivery/SLA, and support",
    ),
    "case_studies": (
        "case-studies-portfolio.md",
        "a Case Studies & Portfolio summary in Markdown highlighting client types, solutions delivered, outcomes, and proof points found on the site",
    ),
}


class _KnowledgeDocResult(BaseModel):
    markdown_content: str = Field(min_length=50, max_length=12000)


async def generate_knowledge_doc_from_website(
    *,
    tenant_id: uuid.UUID,
    doc_type: KnowledgeDocType,
    company_name: str,
    website: str | None,
    description: str = "",
    ideal_customer_text: str = "",
) -> tuple[str, str]:
    """Crawl the company website and generate a structured Markdown knowledge document."""
    normalized_url = _normalize_url(website)
    if not normalized_url:
        raise AppError(
            "missing_website",
            "Add your website URL in Step 1 first so AI can generate this document.",
            status_code=422,
        )

    await _enforce_ai_quota(tenant_id, f"knowledge_{doc_type}")

    website_context, _ = await _crawl_website(normalized_url)
    if not website_context:
        raise AppError(
            "website_unreadable",
            "Could not read content from that website URL. Please upload a file manually instead.",
            status_code=422,
        )

    default_filename, doc_goal = _DOC_SPECS[doc_type]
    system = (
        "You are an expert B2B GTM knowledge base architect. "
        f"Using the extracted website content, write {doc_goal}. "
        "Ground every detail in the provided website content; if certain pricing or metrics are not stated on the site, "
        "do not invent fake numbers—note what is available or mark as 'Contact for custom quote'. "
        "Use clean Markdown headings and bullet points. Match Arabic if the website is primarily Arabic, else English."
    )
    def _build_knowledge_user(ctx: str) -> str:
        parts = [f"Website: {normalized_url}"]
        if company_name.strip():
            parts.append(f"Company name: {company_name.strip()}")
        if description.strip():
            parts.append(f"Company description: {description.strip()}")
        if ideal_customer_text.strip():
            parts.append(f"Ideal customer: {ideal_customer_text.strip()}")
        parts.append(f"Extracted website content:\n{ctx}")
        return "\n\n".join(parts)

    try:
        async with agent_run(
            tenant_id,
            AgentRunKind.ICP_BUILD,
            trigger="manual",
            input={"knowledge_doc_type": doc_type, "website": normalized_url},
        ) as run:
            result = await _smart_llm_structured(
                run,
                name="company_assist.knowledge_doc",
                system=system,
                source_text=website_context,
                build_user_prompt=_build_knowledge_user,
                map_instruction=f"Extract all facts needed to build {doc_goal}.",
                output_model=_KnowledgeDocResult,
                desired_max_tokens=3200,
            )
            run.output_summary = {"doc_type": doc_type, "chars": len(result.markdown_content)}
    except (LLMProviderError, LLMRefused, LLMOutputTruncated, LLMInvalidOutput) as exc:
        logger.warning("Knowledge doc AI generation failed (%s): %s", doc_type, exc)
        raise AppError(
            "ai_assist_failed",
            "Could not generate knowledge document with AI right now. Please try again.",
            status_code=502,
        ) from exc

    return default_filename, result.markdown_content.strip()
