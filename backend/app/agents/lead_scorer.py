"""Lead qualification agent (P2-3)."""

import json
import logging
from pathlib import Path

from pydantic import BaseModel, Field

from app.agents.llm import (
    LLMInvalidOutput,
    LLMOutputTruncated,
    LLMRefused,
    ModelTier,
    llm_structured,
)
from app.core.tracing import RunContext
from app.schemas.agent_io import ICP, CompanyProfile, LeadScore, LeadScoreBatch

logger = logging.getLogger("app.agents.lead_scorer")

PROMPT_VERSION = "lead_scorer@1"
SYSTEM = (Path(__file__).parent / "prompts" / "lead_scorer.md").read_text(encoding="utf-8")
BATCH_SIZE = 15


class LeadForScoring(BaseModel):
    id: str
    name: str
    category: str | None = None
    types: list[str] = Field(default_factory=list)
    address: str | None = None
    governorate: str | None = None
    city: str | None = None
    rating: float | None = None
    reviews_count: int | None = None
    website: str | None = None
    business_status: str | None = None


def _cached_context(icp: ICP, profile: CompanyProfile, insights: list[str]) -> str:
    return (
        "<icp>\n"
        f"{json.dumps(icp.model_dump(), ensure_ascii=False, sort_keys=True)}\n"
        "</icp>\n"
        "<company_profile>\n"
        f"{json.dumps(profile.model_dump(), ensure_ascii=False, sort_keys=True)}\n"
        "</company_profile>\n"
        "<learned_insights>\n"
        f"{json.dumps(insights, ensure_ascii=False)}\n"
        "</learned_insights>"
    )


def _lead_payload(leads: list[LeadForScoring]) -> str:
    payload = [
        {
            "id": lead.id,
            "name": lead.name,
            "category": lead.category,
            "types": lead.types,
            "address": lead.address,
            "governorate": lead.governorate,
            "city": lead.city,
            "rating": lead.rating,
            "reviews_count": lead.reviews_count,
            "website": lead.website,
            "business_status": lead.business_status,
        }
        for lead in leads
    ]
    return "<leads>\n" + json.dumps(payload, ensure_ascii=False) + "\n</leads>"


def _clamp_score(score: LeadScore) -> LeadScore:
    score.score = max(0, min(10, int(score.score)))
    score.reasons = [str(reason).strip() for reason in score.reasons[:4] if str(reason).strip()]
    if not score.reasons:
        score.reasons = ["No specific fit evidence returned"]
    return score


async def _call_batch(
    run: RunContext,
    *,
    icp: ICP,
    profile: CompanyProfile,
    insights: list[str],
    leads: list[LeadForScoring],
) -> dict[str, LeadScore]:
    cached = _cached_context(icp, profile, insights)
    user = _lead_payload(leads)
    for attempt in (1, 2):
        try:
            batch = await llm_structured(
                run,
                name="lead_scorer.batch",
                tier=ModelTier.FAST,
                effort="low",
                system=SYSTEM,
                user=user,
                output_model=LeadScoreBatch,
                cached_context=cached,
            )
            break
        except (LLMRefused, LLMOutputTruncated, LLMInvalidOutput):
            return {}
        except Exception as exc:
            if attempt == 1:
                logger.warning("lead scorer batch call failed; retrying once: %s", exc)
                continue
            logger.error("lead scorer batch call failed twice: %s", exc)
            return {}

    known = {lead.id: lead for lead in leads}
    scored: dict[str, LeadScore] = {}
    for score in batch.scores:
        lead_id = str(score.lead_ref)
        if lead_id not in known:
            continue
        scored[lead_id] = _clamp_score(score)

    missing = [lead for lead in leads if lead.id not in scored]
    if missing:
        try:
            retry_batch = await llm_structured(
                run,
                name="lead_scorer.retry",
                tier=ModelTier.FAST,
                effort="low",
                system=SYSTEM,
                user=_lead_payload(missing),
                output_model=LeadScoreBatch,
                cached_context=cached,
            )
        except Exception:
            return scored

        for score in retry_batch.scores:
            lead_id = str(score.lead_ref)
            if lead_id in known:
                scored[lead_id] = _clamp_score(score)
    return scored


async def score_leads(
    run: RunContext,
    *,
    icp: ICP,
    profile: CompanyProfile,
    insights: list[str],
    leads: list[LeadForScoring],
) -> list[LeadScore]:
    """Score leads in batches of 15 and return exactly one result per input lead."""
    results: dict[str, LeadScore] = {}

    for start in range(0, len(leads), BATCH_SIZE):
        batch = leads[start : start + BATCH_SIZE]
        results.update(
            await _call_batch(
                run,
                icp=icp,
                profile=profile,
                insights=insights,
                leads=batch,
            )
        )

    ordered: list[LeadScore] = []
    for lead in leads:
        score = results.get(lead.id)
        if score is None:
            unscored = LeadScore(
                lead_ref=lead.id,
                score=0,
                fit="not_fit",
                reasons=["No reliable score returned"],
                disqualify_reason="scoring_unavailable",
            )
            object.__setattr__(unscored, "score", None)
            ordered.append(unscored)
        else:
            ordered.append(score)
    return ordered
