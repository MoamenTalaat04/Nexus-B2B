"""Search query generator (P2-1): turns the active ICP into 5-15 Google Maps searches.

One llm_structured call (FAST tier, effort low). The stable part (prompt + ICP + profile) goes first; the
per-run part (allowed regions, recently used queries) goes last. Code post-processing then:
- keeps only queries inside the ICP regions (and, where the ICP lists cities, only those cities),
- drops duplicates and queries used recently (compared after Arabic/English normalization),
- caps the plan at 15 queries.

B's sourcing job (P2-2) calls generate_queries() and records the searches in `search_queries`;
recent_queries() reads them back so the next run tries new angles.
"""

import json
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm import ModelTier, llm_structured
from app.core.geo_eg_coords import normalize_arabic, normalize_name
from app.core.tracing import RunContext
from app.models.enums import StepType
from app.models.leads import SearchQuery
from app.schemas.agent_io import ICP, CompanyProfile, GeneratedQuery, QueryPlan, RegionTarget

PROMPT_VERSION = "query_generator@1"
SYSTEM = (Path(__file__).parent / "prompts" / "query_generator.md").read_text(encoding="utf-8")

MAX_QUERIES = 15
RECENT_LIMIT = 100


def normalize_query(text: str) -> str:
    """Compare-friendly query text (Arabic letter variants unified, lowercase, single spaces)."""
    return normalize_arabic(text)


async def recent_queries(session: AsyncSession, tenant_id: uuid.UUID, limit: int = RECENT_LIMIT) -> list[str]:
    """The tenant's last `limit` search texts, newest first (generate_queries' already_used)."""
    rows = await session.execute(
        select(SearchQuery.query_text)
        .where(SearchQuery.tenant_id == tenant_id)
        .order_by(SearchQuery.created_at.desc())
        .limit(limit)
    )
    return list(rows.scalars())


def _region_key(region: RegionTarget) -> tuple[str, tuple[str, ...]]:
    return normalize_name(region.governorate), tuple(sorted(normalize_name(c) for c in region.cities))


def _fit_region(region: RegionTarget, allowed: list[RegionTarget]) -> RegionTarget | None:
    """The query's region limited to the ICP regions, or None when it is outside them."""
    if not allowed:
        return region
    for target in allowed:
        if normalize_name(target.governorate) != normalize_name(region.governorate):
            continue
        if not target.cities:  # the ICP allows the whole governorate
            return RegionTarget(governorate=target.governorate, cities=list(region.cities))
        if not region.cities:  # stay inside the ICP's cities
            return RegionTarget(governorate=target.governorate, cities=list(target.cities))
        names = {normalize_name(c): c for c in target.cities}
        cities = [names[normalize_name(c)] for c in region.cities if normalize_name(c) in names]
        return RegionTarget(governorate=target.governorate, cities=cities) if cities else None
    return None


def postprocess(
    plan: QueryPlan, *, icp: ICP, already_used: list[str]
) -> tuple[QueryPlan, dict[str, list[str]]]:
    """Apply the code rules to the model's plan. Returns the cleaned plan and what was dropped."""
    used = {normalize_query(q) for q in already_used}
    seen: set[tuple[str, tuple[str, tuple[str, ...]]]] = set()
    kept: list[GeneratedQuery] = []
    dropped: dict[str, list[str]] = {
        "outside_regions": [],
        "already_used": [],
        "duplicate": [],
        "over_limit": [],
    }
    for item in plan.queries:
        text = " ".join(item.query.split())
        norm = normalize_query(text)
        if not norm:
            continue
        region = _fit_region(item.region, icp.regions)
        if region is None:
            dropped["outside_regions"].append(text)
            continue
        if norm in used:
            dropped["already_used"].append(text)
            continue
        key = (norm, _region_key(region))
        if key in seen:
            dropped["duplicate"].append(text)
            continue
        if len(kept) >= MAX_QUERIES:
            dropped["over_limit"].append(text)
            continue
        seen.add(key)
        kept.append(GeneratedQuery(query=text, region=region, rationale=item.rationale))
    return QueryPlan(queries=kept), {k: v for k, v in dropped.items() if v}


def build_cached_context(icp: ICP, profile: CompanyProfile) -> str:
    return (
        "<icp>\n"
        f"{json.dumps(icp.model_dump(), ensure_ascii=False)}\n"
        "</icp>\n\n"
        "<company_profile>\n"
        f"{json.dumps(profile.model_dump(), ensure_ascii=False)}\n"
        "</company_profile>"
    )


def build_user_message(icp: ICP, already_used: list[str]) -> str:
    regions = [
        f"- {r.governorate}" + (f" (cities: {', '.join(r.cities)})" if r.cities else " (any city)")
        for r in icp.regions
    ] or ["- any governorate in Egypt"]
    used = "\n".join(f"- {q}" for q in already_used[:RECENT_LIMIT]) or "- (none yet)"
    return (
        "Write the next Google Maps searches.\n\n"
        "Allowed regions:\n" + "\n".join(regions) + "\n\n"
        "Already used recently (do not repeat):\n" + used
    )


async def generate_queries(
    run: RunContext, *, icp: ICP, profile: CompanyProfile, already_used: list[str]
) -> QueryPlan:
    """5-15 new searches for the ICP, inside its regions and not in already_used."""
    raw = await llm_structured(
        run,
        name="query_generator.plan",
        tier=ModelTier.FAST,
        effort="low",
        system=SYSTEM,
        cached_context=build_cached_context(icp, profile),
        user=build_user_message(icp, already_used),
        output_model=QueryPlan,
    )
    plan, dropped = postprocess(raw, icp=icp, already_used=already_used)
    await run.step(
        StepType.DECISION,
        "query_generator.postprocess",
        output={"proposed": len(raw.queries), "kept": len(plan.queries), "dropped": dropped},
    )
    return plan
