"""Message personalizer (P3-3): fills WhatsApp template params, or writes an assisted message, for one lead.

Two functions, one prompt (PROMPT_VERSION shared), FAST tier, effort low:
- personalize()    → PersonalizedOpening: the {{n}} params of an approved template (api_template mode)
- write_assisted() → AssistedMessage: a short text the owner sends personally (assisted mode, the default)

The stable part (prompt + company profile + ICP [+ template body]) goes first; the lead, wrapped as
untrusted <lead> data, goes last. Code checks every answer: params (count, ≤ 60 chars, one line, no prices
or links) and assisted text (≤ 400 chars, no prices). A bad answer is retried once with the problems
listed; if still bad, safe generic wording is used, so outreach never stalls on the model.
The assistant link line is always added by code.
"""

import json
import re
from pathlib import Path

from app.agents.llm import ModelTier, llm_structured
from app.core.tracing import RunContext
from app.models.enums import OutreachPurpose
from app.models.leads import Lead
from app.models.messaging import MessageTemplate
from app.schemas.agent_io import ICP, AssistedMessage, CompanyProfile, PersonalizedOpening
from app.services.messaging import render_template

PROMPT_VERSION = "message_personalizer@1"
SYSTEM = (Path(__file__).parent / "prompts" / "message_personalizer.md").read_text(encoding="utf-8")

MAX_PARAM_CHARS = 60
MAX_ASSISTED_TEXT_CHARS = 400  # the model's part; the link line comes on top
MAX_ASSISTED_TOTAL_CHARS = 500
INVITE_AR = "ولو حابب تشوف الكتالوج والأسعار، كلّم المساعد بتاعنا هنا:"
INVITE_EN = "For our catalogue and prices, chat with our assistant here:"

PRICE_RE = re.compile(
    r"[\d٠-٩][\d٠-٩,.]*\s*(%|٪|جنيه|ج\.?م|egp|le\b|\$|usd)|خصم|تخفيض|عرض خاص|discount|\boff\b",
    re.IGNORECASE,
)
LINK_RE = re.compile(r"(https?://|www\.|wa\.me/)\S+", re.IGNORECASE)


# ---------------------------------------------------------------------------------------------- helpers


def lead_data(lead: Lead) -> str:
    """The lead as untrusted data. Phone numbers are deliberately left out."""
    data = {
        "name": lead.name,
        "category": lead.category,
        "city": lead.city,
        "governorate": lead.governorate,
        "rating": lead.rating,
        "reviews_count": lead.reviews_count,
        "website": lead.domain or lead.website,
    }
    return "<lead>\n" + json.dumps({k: v for k, v in data.items() if v}, ensure_ascii=False) + "\n</lead>"


def _context(profile: CompanyProfile, icp: ICP, template: MessageTemplate | None = None) -> str:
    parts = [
        "<company_profile>\n" + json.dumps(profile.model_dump(), ensure_ascii=False) + "\n</company_profile>",
        "<icp>\n" + json.dumps(icp.model_dump(), ensure_ascii=False) + "\n</icp>",
    ]
    if template is not None:
        parts.append(f'<template params="{template.param_count}">\n{template.body_text}\n</template>')
    return "\n\n".join(parts)


def _step_words(purpose: OutreachPurpose) -> str:
    return "follow-up" if purpose == OutreachPurpose.FOLLOWUP else "first touch"


def param_problems(params: list[str], count: int) -> list[str]:
    """Why these params cannot be sent ([] when they are fine)."""
    problems: list[str] = []
    if len(params) != count:
        problems.append(f"exactly {count} parameter(s) are needed, got {len(params)}")
    for i, value in enumerate(params, 1):
        if not value.strip():
            problems.append(f"parameter {i} is empty")
        if "\n" in value or "\t" in value or "     " in value:
            problems.append(f"parameter {i} must be one line (no newlines, tabs or 5+ spaces)")
        if len(value) > MAX_PARAM_CHARS:
            problems.append(f"parameter {i} is longer than {MAX_PARAM_CHARS} characters")
        if PRICE_RE.search(value):
            problems.append(f"parameter {i} mentions a price or discount")
        if LINK_RE.search(value):
            problems.append(f"parameter {i} contains a link")
    return problems


def fallback_params(lead: Lead, count: int) -> list[str]:
    """Safe generic params: the business name, then its area (Egyptian Arabic)."""
    area = lead.city or lead.governorate
    candidates = [
        lead.name.strip()[:MAX_PARAM_CHARS] or "حضرتك",
        (f"محلكم في {area}" if area else "محلكم")[:MAX_PARAM_CHARS],
        (lead.category or "نشاطكم")[:MAX_PARAM_CHARS],
    ]
    return [candidates[i] if i < len(candidates) else candidates[0] for i in range(count)]


def text_problems(text: str) -> list[str]:
    problems: list[str] = []
    if not text.strip():
        problems.append("the message is empty")
    if len(text) > MAX_ASSISTED_TEXT_CHARS:
        problems.append(f"the message is longer than {MAX_ASSISTED_TEXT_CHARS} characters")
    if PRICE_RE.search(text):
        problems.append("the message mentions a price or discount")
    return problems


def _clean_text(text: str) -> str:
    text = LINK_RE.sub("", text)  # the link line is added by code
    lines = [" ".join(line.split()) for line in text.strip().splitlines()]
    return "\n".join(line for line in lines if line)


def _with_link(text: str, assistant_link: str | None, language: str) -> str:
    if not assistant_link:
        return text[:MAX_ASSISTED_TOTAL_CHARS]
    line = f"{INVITE_AR if language.startswith('ar') else INVITE_EN}\n{assistant_link}"
    room = MAX_ASSISTED_TOTAL_CHARS - len(line) - 2
    return f"{text[: max(room, 0)].rstrip()}\n\n{line}"


def _retry_note(problems: list[str]) -> str:
    return "\n\nYour previous answer was rejected: " + "; ".join(problems) + ". Fix it and answer again."


# ---------------------------------------------------------------------------------------------- the agent


async def personalize(
    run: RunContext,
    *,
    profile: CompanyProfile,
    icp: ICP,
    lead: Lead,
    template: MessageTemplate,
    step_purpose: OutreachPurpose,
) -> PersonalizedOpening:
    """Fill the template's params for this lead; always returns sendable params."""
    user = (
        f"{lead_data(lead)}\n\nTask: template params\nStep: {_step_words(step_purpose)}\n"
        f"Parameters needed: {template.param_count}"
    )
    context = _context(profile, icp, template)
    result: PersonalizedOpening | None = None
    problems: list[str] = []
    for attempt in (1, 2):
        result = await llm_structured(
            run,
            name="message_personalizer.opening",
            tier=ModelTier.FAST,
            effort="low",
            system=SYSTEM,
            cached_context=context,
            user=user if attempt == 1 else user + _retry_note(problems),
            output_model=PersonalizedOpening,
            lead_id=lead.id,
        )
        params = [
            " ".join(p.split()) if "\n" not in p and "\t" not in p else p for p in result.template_params
        ]
        problems = param_problems(params, template.param_count)
        if not problems:
            return PersonalizedOpening(
                template_params=params,
                preview_text=render_template(template.body_text, params),
                rationale=result.rationale,
            )
    params = fallback_params(lead, template.param_count)
    return PersonalizedOpening(
        template_params=params,
        preview_text=render_template(template.body_text, params),
        rationale="Generic wording: the AI's suggestion broke the message rules ("
        + "; ".join(problems)
        + ").",
    )


async def write_assisted(
    run: RunContext,
    *,
    profile: CompanyProfile,
    icp: ICP,
    lead: Lead,
    step_purpose: OutreachPurpose,
    assistant_link: str | None,
) -> AssistedMessage:
    """A short message the owner sends personally; ends with the assistant link line when there is one."""
    user = f"{lead_data(lead)}\n\nTask: assisted message\nStep: {_step_words(step_purpose)}"
    context = _context(profile, icp)
    problems: list[str] = []
    for attempt in (1, 2):
        result = await llm_structured(
            run,
            name="message_personalizer.assisted",
            tier=ModelTier.FAST,
            effort="low",
            system=SYSTEM,
            cached_context=context,
            user=user if attempt == 1 else user + _retry_note(problems),
            output_model=AssistedMessage,
            lead_id=lead.id,
        )
        text = _clean_text(result.text)
        problems = text_problems(text)
        if not problems:
            return AssistedMessage(
                text=_with_link(text, assistant_link, profile.language), rationale=result.rationale
            )
    if profile.language.startswith("en"):
        text = f"Hello {lead.name}, this is {profile.company_name}. {profile.one_liner}"
    else:
        text = f"أهلاً {lead.name}، معاك {profile.company_name}. {profile.one_liner}"
    return AssistedMessage(
        text=_with_link(_clean_text(text)[:MAX_ASSISTED_TEXT_CHARS], assistant_link, profile.language),
        rationale="Generic wording: the AI's message broke the rules (" + "; ".join(problems) + ").",
    )
