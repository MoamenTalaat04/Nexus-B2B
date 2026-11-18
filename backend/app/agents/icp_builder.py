"""Company Profile & ICP builder agent (P1-3).

Turns the owner's onboarding answers and uploaded files into (1) a factual CompanyProfile and (2) an ICP
that drives sourcing and scoring. Two llm_structured calls (SMART tier, effort medium) share one stable
prefix: the system prompt, then the settings as YAML and the knowledge text, both wrapped as untrusted
data. Only the short task instruction differs, so providers with prefix caching reuse the big part.

After the model answers, code-level guardrails apply the owner's settings, which win over the model:
regions are limited to the owner's target regions; offer, discount, tone and language come from settings.
"""

import json
from pathlib import Path
from typing import Any

import yaml

from app.agents.llm import ModelTier, llm_structured
from app.core.tracing import RunContext
from app.models.enums import StepType
from app.models.tenants import BusinessSettings
from app.schemas.agent_io import ICP, CompanyProfile, RegionTarget

PROMPT_VERSION = "icp_builder@1"
SYSTEM = (Path(__file__).parent / "prompts" / "icp_builder.md").read_text(encoding="utf-8")

NO_FILES = "(the owner has not uploaded any files)"

PROFILE_TASK = (
    "Task 1 of 2: write the CompanyProfile for this business from <business_settings> and <company_files>. "
    "Facts only; unknown fields stay empty."
)
ICP_TASK = (
    "Task 2 of 2: here is the CompanyProfile you wrote:\n<company_profile>\n{profile}\n</company_profile>\n"
    "Now write the ICP. Allowed regions (use only these): {regions}."
)


def render_settings(settings: BusinessSettings) -> str:
    """The onboarding answers the agent needs, as YAML (stable order, Arabic kept readable)."""
    data: dict[str, Any] = {
        "company_name": settings.company_name,
        "website": settings.website or "",
        "description": settings.description,
        "ideal_customer_in_owner_words": settings.ideal_customer_text,
        "products": settings.products or [],
        "target_regions": settings.target_regions or [],
        "language": settings.language,
        "tone": settings.tone,
        "allowed_offers": settings.allowed_offers,
        "max_discount_percent": settings.max_discount_percent,
    }
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=1000)


def build_cached_context(settings: BusinessSettings, knowledge_text: str) -> str:
    """The stable, shared part of both calls. No timestamps or ids here (it must stay identical)."""
    return (
        "<business_settings>\n"
        f"{render_settings(settings)}"
        "</business_settings>\n\n"
        "<company_files>\n"
        f"{knowledge_text.strip() or NO_FILES}\n"
        "</company_files>"
    )


def _owner_regions(settings: BusinessSettings) -> list[RegionTarget]:
    return [RegionTarget.model_validate(r) for r in (settings.target_regions or [])]


def _norm(text: str) -> str:
    return " ".join(text.strip().lower().split())


def limit_regions(proposed: list[RegionTarget], allowed: list[RegionTarget]) -> list[RegionTarget]:
    """Keep only the owner's governorates (and, where the owner listed cities, only those cities).

    If the owner set no regions, the model's regions are kept. If nothing valid is left, the owner's regions
    are used as they are.
    """
    if not allowed:
        return proposed
    by_name = {_norm(r.governorate): r for r in allowed}
    result: list[RegionTarget] = []
    for region in proposed:
        owner = by_name.get(_norm(region.governorate))
        if owner is None:
            continue
        if owner.cities:
            owner_cities = {_norm(c): c for c in owner.cities}
            cities = [owner_cities[_norm(c)] for c in region.cities if _norm(c) in owner_cities]
            cities = cities or list(owner.cities)
        else:
            cities = list(region.cities)
        if all(_norm(r.governorate) != _norm(owner.governorate) for r in result):
            result.append(RegionTarget(governorate=owner.governorate, cities=cities))
    return result or [r.model_copy() for r in allowed]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = _norm(item)
        if key and key not in seen:
            seen.add(key)
            out.append(item.strip())
    return out


def apply_guardrails(
    settings: BusinessSettings, profile: CompanyProfile, icp: ICP
) -> tuple[CompanyProfile, ICP, dict[str, Any]]:
    """The owner's settings win over the model. Returns the fixed profile, ICP and what changed."""
    changes: dict[str, Any] = {}
    profile_updates: dict[str, Any] = {
        "allowed_offers": settings.allowed_offers,
        "max_discount_percent": settings.max_discount_percent,
        "tone": settings.tone,
        "language": settings.language,
    }
    if settings.company_name.strip():
        profile_updates["company_name"] = settings.company_name.strip()
    for field, value in profile_updates.items():
        if getattr(profile, field) != value:
            changes[f"profile.{field}"] = {"model": getattr(profile, field), "settings": value}
    profile = profile.model_copy(update=profile_updates)

    regions = limit_regions(icp.regions, _owner_regions(settings))
    if [r.model_dump() for r in regions] != [r.model_dump() for r in icp.regions]:
        changes["icp.regions"] = {
            "model": [r.model_dump() for r in icp.regions],
            "kept": [r.model_dump() for r in regions],
        }
    icp = icp.model_copy(
        update={
            "regions": regions,
            "target_business_types": _dedupe(icp.target_business_types),
            "include_keywords": _dedupe(icp.include_keywords),
            "exclude_keywords": _dedupe(icp.exclude_keywords),
            "google_place_types": _dedupe(icp.google_place_types),
            "language": settings.language,
        }
    )
    return profile, icp, changes


async def build_icp(
    run: RunContext, *, settings: BusinessSettings, knowledge_text: str
) -> tuple[CompanyProfile, ICP]:
    """Build the CompanyProfile, then the ICP from it. Raises the llm.* errors (LLMRefused, …) unchanged."""
    cached_context = build_cached_context(settings, knowledge_text)
    profile = await llm_structured(
        run,
        name="icp_builder.profile",
        tier=ModelTier.SMART,
        effort="medium",
        system=SYSTEM,
        cached_context=cached_context,
        user=PROFILE_TASK,
        output_model=CompanyProfile,
    )
    regions = ", ".join(r.governorate for r in _owner_regions(settings)) or "any governorate in Egypt"
    icp = await llm_structured(
        run,
        name="icp_builder.icp",
        tier=ModelTier.SMART,
        effort="medium",
        system=SYSTEM,
        cached_context=cached_context,
        user=ICP_TASK.format(profile=json.dumps(profile.model_dump(), ensure_ascii=False), regions=regions),
        output_model=ICP,
    )
    profile, icp, changes = apply_guardrails(settings, profile, icp)
    await run.step(StepType.DECISION, "icp_builder.guardrails", output={"changes": changes})
    return profile, icp
