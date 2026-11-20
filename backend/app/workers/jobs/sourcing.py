"""job_run_sourcing (CONTRACTS section 10, P2-2 orchestration + P2-1 query generation and search).

Inside one SOURCING agent_run:
  active ICP (none → the run fails with "no_active_icp")
  → C's generate_queries(run, icp, profile, already_used=recent_queries)   (LLM, FAST tier)
  → per query: registry.get_search_source().search(query, region, max_results=20)   (EXTERNAL_API step)
               a search_queries row, then ingest (normalize + dedupe → leads status=new)
  → stop once max_results new leads were created
  → a DECISION step with the totals, then enqueue job_score_leads(tenant_id, run_id).
One failing search is recorded as an ERROR step and skipped; the run fails only if every search failed.
POST /api/v1/runs/sourcing pre-creates the run (status queued) and passes run_id here.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters import registry
from app.adapters.base import RegionFilter
from app.agents.query_generator import generate_queries, recent_queries
from app.core.tracing import agent_run
from app.db import SessionLocal
from app.models.enums import AgentRunKind, StepType
from app.models.leads import SearchQuery
from app.schemas.agent_io import ICP, CompanyProfile
from app.services import icp_service
from app.services.leads_ingest import ingest_places
from app.workers.queue import enqueue

logger = logging.getLogger("app.jobs.sourcing")

DEFAULT_MAX_RESULTS = 60
RESULTS_PER_QUERY = 20


class SourcingError(Exception):
    """A readable reason the run could not source leads; stored as the run's error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass
class SourcingResult:
    run_id: uuid.UUID
    created: int = 0
    duplicates: int = 0
    skipped: int = 0
    queries_run: int = 0
    queries_failed: int = 0
    api_requests: int = 0
    lead_ids: list[uuid.UUID] = field(default_factory=list)
    scoring_enqueued: bool = False

    def summary(self) -> dict[str, Any]:
        return {
            "created": self.created,
            "duplicates": self.duplicates,
            "skipped": self.skipped,
            "queries_run": self.queries_run,
            "queries_failed": self.queries_failed,
            "api_requests": self.api_requests,
            "scoring_enqueued": self.scoring_enqueued,
        }


async def run_sourcing(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    max_results: int = DEFAULT_MAX_RESULTS,
    run_id: uuid.UUID | None = None,
    trigger: str = "manual",
) -> SourcingResult:
    async with agent_run(
        tenant_id, AgentRunKind.SOURCING, trigger=trigger, input={"max_results": max_results}, run_id=run_id
    ) as run:
        result = SourcingResult(run_id=run.run_id)
        active = await icp_service.get_active_icp(session, tenant_id)
        if active is None:
            raise SourcingError("no_active_icp", "Generate and save the customer profile (ICP) first.")
        icp = ICP.model_validate(active.icp)
        profile = CompanyProfile.model_validate(active.company_profile)
        used = await recent_queries(session, tenant_id)
        plan = await generate_queries(run, icp=icp, profile=profile, already_used=used)
        source = registry.get_search_source()
        source_name = getattr(source, "name", "search")

        for query in plan.queries:
            remaining = max_results - result.created
            if remaining <= 0:
                break
            region = RegionFilter(governorate=query.region.governorate, cities=list(query.region.cities))
            region_json = query.region.model_dump(mode="json")
            started = time.perf_counter()
            try:
                places = await source.search(query.query, region=region, max_results=RESULTS_PER_QUERY)
            except Exception as exc:  # one failing search must not kill the run
                result.queries_failed += 1
                await run.step(
                    StepType.ERROR,
                    f"{source_name}.search_failed",
                    input={"query": query.query, "region": region_json},
                    output={"error": f"{type(exc).__name__}: {exc}"[:500]},
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )
                continue
            requests = int(getattr(source, "last_request_count", 0) or 0)
            result.queries_run += 1
            result.api_requests += requests
            await run.step(
                StepType.EXTERNAL_API,
                f"{source_name}.search",
                input={"query": query.query, "region": region_json, "max_results": RESULTS_PER_QUERY},
                output={"results": len(places), "requests": requests},
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
            session.add(
                SearchQuery(
                    tenant_id=tenant_id,
                    run_id=run.run_id,
                    source=source_name,
                    query_text=query.query,
                    region=region_json,
                    results_count=len(places),
                )
            )
            ingest = await ingest_places(session, run, tenant_id, places, active.id, limit=remaining)
            result.created += ingest.created
            result.duplicates += ingest.duplicates
            result.skipped += ingest.skipped
            result.lead_ids.extend(ingest.lead_ids)
            await session.commit()  # keep progress even if a later step fails

        if plan.queries and result.queries_run == 0:
            raise SourcingError("all_searches_failed", "Every search failed; check the search API key.")

        if result.created > 0:
            try:
                await enqueue("job_score_leads", tenant_id=str(tenant_id), run_id=str(run.run_id))
                result.scoring_enqueued = True
            except Exception as exc:
                logger.exception("could not enqueue job_score_leads")
                await run.step(StepType.ERROR, "sourcing.enqueue_scoring_failed", output={"error": str(exc)})
        await run.step(StepType.DECISION, "sourcing.totals", output=result.summary())
        run.output_summary = result.summary()
        return result


async def job_run_sourcing(
    ctx: dict[str, Any],
    tenant_id: str,
    max_results: int = DEFAULT_MAX_RESULTS,
    run_id: str | None = None,
    trigger: str = "manual",
) -> dict[str, Any]:
    tid = uuid.UUID(str(tenant_id))
    rid = uuid.UUID(str(run_id)) if run_id else None
    async with SessionLocal() as session:
        try:
            result = await run_sourcing(
                session, tid, max_results=int(max_results), run_id=rid, trigger=trigger
            )
        except SourcingError as exc:  # already recorded on the run
            logger.warning("sourcing failed for tenant %s: %s", tid, exc)
            return {"status": "failed", "error": exc.code}
    return {"status": "succeeded", "run_id": str(result.run_id), **result.summary()}
