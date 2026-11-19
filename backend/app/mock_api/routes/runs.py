"""Mock Runs & Sourcing Trigger routes: /runs, /runs/{id}, /runs/sourcing."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.icp import GenerateOut
from app.api.runs import RunDetailOut, RunListOut, RunOut, StepOut
from app.core.errors import AppError, NotFoundError
from app.core.security import CurrentUser
from app.mock_api.helpers import get_mock_current_user, get_tenant_settings, paginate
from app.mock_api.routes.icp import advance_icp_run
from app.mock_api.state import MockAgentRun, MockAgentStep, MockContact, MockLead, MockStore, get_store
from app.models.enums import AgentRunKind, AgentRunStatus, ContactType, LeadStatus, StepType

router = APIRouter(prefix="/runs", tags=["runs"])


class SourcingTriggerIn(BaseModel):
    max_results: int = Field(default=30, ge=1, le=100)


_EXTRA_SOURCING_BATCH = [
    (
        "ميني مودرن كيدز - Mini Modern",
        "kids clothing store",
        "Cairo",
        "New Cairo",
        4.6,
        72,
        8,
        "High-fit kids shop in New Cairo",
    ),
    ("بيبي توب - Baby Top", "baby store", "Giza", "Dokki", 4.5, 65, 8, "Baby & infant store in Dokki"),
    (
        "فاشون كيدز هاوس",
        "kids clothing store",
        "Cairo",
        "Maadi",
        4.4,
        53,
        7,
        "Kids apparel boutique in Maadi",
    ),
    (
        "عالم الصغار - Little World",
        "kids clothing store",
        "Giza",
        "6th of October",
        4.7,
        108,
        9,
        "Popular kids clothing store in October",
    ),
    (
        "بوتيك الياسمين",
        "clothing store",
        "Cairo",
        "Heliopolis",
        4.2,
        31,
        5,
        "General clothing store with small kids section",
    ),
]


def _run_to_out(run: MockAgentRun) -> RunOut:
    duration = None
    if run.started_at and run.finished_at:
        duration = int((run.finished_at - run.started_at).total_seconds() * 1000)
    return RunOut(
        id=run.id,
        kind=run.kind,
        status=run.status,
        trigger=run.trigger,
        error=run.error,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        duration_ms=duration,
        total_input_tokens=run.total_input_tokens,
        total_output_tokens=run.total_output_tokens,
        total_cost_usd=run.total_cost_usd,
    )


def _advance_sourcing_run(store: MockStore, run: MockAgentRun) -> None:
    run.poll_count += 1
    now = datetime.now(UTC)
    if run.status == AgentRunStatus.QUEUED.value:
        run.status = AgentRunStatus.RUNNING.value
        return

    if run.status == AgentRunStatus.RUNNING.value:
        tenant_id = run.tenant_id
        batch_num = store.sourcing_batch_counter.get(tenant_id, 0) + 1
        store.sourcing_batch_counter[tenant_id] = batch_num

        active_icp = next(
            (v for v in store.icp_versions.values() if v.tenant_id == tenant_id and v.is_active),
            None,
        )
        s = get_tenant_settings(store, tenant_id)
        existing_keys = {lead.dedupe_key for lead in store.leads.values() if lead.tenant_id == tenant_id}

        created_count = 0
        duplicates_count = 0
        qualified_count = 0
        disqualified_count = 0

        for idx, (name, cat, gov, city, rating, reviews, score, reason) in enumerate(
            _EXTRA_SOURCING_BATCH, start=1
        ):
            d_key = f"google_places:mock_sourcing_b{batch_num}_{idx}"
            if d_key in existing_keys:
                duplicates_count += 1
                continue
            lid = uuid.uuid4()
            is_qualified = score >= s.score_threshold
            lead_status = LeadStatus.QUALIFIED.value if is_qualified else LeadStatus.DISQUALIFIED.value
            if is_qualified:
                qualified_count += 1
            else:
                disqualified_count += 1
            created_count += 1
            display_name = name if batch_num == 1 else f"{name} (فرع {batch_num})"
            lead = MockLead(
                id=lid,
                tenant_id=tenant_id,
                name=display_name,
                source="google_places",
                source_ref=f"ChIJ_b{batch_num}_{idx}",
                category=cat,
                address=f"{20 + idx} شارع النصر، {city}، {gov}",
                city=city,
                governorate=gov,
                lat=30.05 + idx * 0.01,
                lng=31.24 + idx * 0.01,
                website=f"https://b{batch_num}shop{idx}.example.com",
                domain=f"b{batch_num}shop{idx}.example.com",
                google_maps_url=f"https://maps.google.com/?q=30.05,31.24&cid=b{batch_num}{idx}",
                rating=rating,
                reviews_count=reviews,
                status=lead_status,
                score=score,
                score_reasons=[reason],
                disqualify_reason=None if is_qualified else "Score below threshold",
                icp_version_id=active_icp.id if active_icp else None,
                sourcing_run_id=run.id,
                ref_code=f"S{batch_num}{idx:03d}",
                dedupe_key=d_key,
                created_at=now,
            )
            store.leads[lid] = lead
            cid = uuid.uuid4()
            store.contacts[cid] = MockContact(
                id=cid,
                tenant_id=tenant_id,
                lead_id=lid,
                type=ContactType.MOBILE.value,
                value=f"+2010{(batch_num * 1000000 + idx):08d}"[:13],
                source="google_places",
                is_primary=True,
                confidence=0.9,
                created_at=now,
            )

        steps_data = [
            (
                2,
                StepType.EXTERNAL_API,
                "google_places.search",
                {"queries": ["محل ملابس أطفال القاهرة الجديدة", "baby store Dokki"]},
                {"places_returned": len(_EXTRA_SOURCING_BATCH)},
                None,
                0,
                0,
                0,
                0.0,
                520,
            ),
            (
                3,
                StepType.LLM_CALL,
                "lead_scorer.batch",
                {"leads_count": created_count},
                {"qualified": qualified_count, "disqualified": disqualified_count},
                "gemini-3.5-flash-lite",
                1150,
                320,
                600,
                0.0014,
                740,
            ),
            (
                4,
                StepType.DECISION,
                "sourcing.summary",
                {},
                {"created": created_count, "duplicates": duplicates_count, "qualified": qualified_count},
                None,
                0,
                0,
                0,
                0.0,
                15,
            ),
        ]
        for seq, stype, sname, inp, outp, model, itok, otok, ctok, cost, lat in steps_data:
            sid = uuid.uuid4()
            store.steps[sid] = MockAgentStep(
                id=sid,
                tenant_id=tenant_id,
                run_id=run.id,
                seq=seq,
                step_type=stype.value,
                name=sname,
                input=inp,
                output=outp,
                model=model,
                input_tokens=itok,
                output_tokens=otok,
                cache_read_tokens=ctok,
                cost_usd=cost,
                latency_ms=lat,
                created_at=now,
            )

        run.status = AgentRunStatus.SUCCEEDED.value
        run.finished_at = now
        run.total_input_tokens += 1150
        run.total_output_tokens += 320
        run.total_cost_usd = round(run.total_cost_usd + 0.0014, 6)
        run.output_summary = {
            "created": created_count,
            "duplicates": duplicates_count,
            "qualified": qualified_count,
        }


@router.post("/sourcing", response_model=GenerateOut, status_code=202)
async def trigger_sourcing(
    body: SourcingTriggerIn | None = None,
    current_user: CurrentUser = Depends(get_mock_current_user),
) -> GenerateOut:
    store = get_store()
    s = get_tenant_settings(store, current_user.tenant_id)
    if not s.onboarding_completed:
        raise AppError(
            "onboarding_incomplete", "Complete onboarding before starting sourcing.", status_code=400
        )

    active_icp = next(
        (v for v in store.icp_versions.values() if v.tenant_id == current_user.tenant_id and v.is_active),
        None,
    )
    if active_icp is None:
        raise AppError(
            "no_active_icp", "Generate or activate an ICP before starting sourcing.", status_code=400
        )

    running_sourcing = any(
        r.tenant_id == current_user.tenant_id
        and r.kind == AgentRunKind.SOURCING.value
        and r.status in {AgentRunStatus.QUEUED.value, AgentRunStatus.RUNNING.value}
        for r in store.runs.values()
    )
    if running_sourcing:
        raise AppError("sourcing_already_running", "A sourcing run is already in progress.", status_code=409)

    max_results = body.max_results if body else s.daily_new_leads_target
    now = datetime.now(UTC)
    run_id = uuid.uuid4()
    run = MockAgentRun(
        id=run_id,
        tenant_id=current_user.tenant_id,
        kind=AgentRunKind.SOURCING.value,
        status=AgentRunStatus.QUEUED.value,
        trigger="manual",
        input={"max_results": max_results},
        created_at=now,
        started_at=now,
        total_input_tokens=620,
        total_output_tokens=210,
        total_cost_usd=0.0008,
    )
    store.runs[run_id] = run

    step_id = uuid.uuid4()
    store.steps[step_id] = MockAgentStep(
        id=step_id,
        tenant_id=current_user.tenant_id,
        run_id=run_id,
        seq=1,
        step_type=StepType.LLM_CALL.value,
        name="query_generator",
        input={"icp_version": active_icp.version, "max_results": max_results},
        output={"queries_generated": 5},
        model="gemini-3.5-flash-lite",
        input_tokens=620,
        output_tokens=210,
        cache_read_tokens=200,
        cost_usd=0.0008,
        latency_ms=410,
        created_at=now,
    )
    return GenerateOut(run_id=run_id)


@router.get("", response_model=RunListOut)
async def list_runs(
    kind: AgentRunKind | None = None,
    status: AgentRunStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: CurrentUser = Depends(get_mock_current_user),
) -> RunListOut:
    store = get_store()
    rows = [r for r in store.runs.values() if r.tenant_id == current_user.tenant_id]
    if kind is not None:
        rows = [r for r in rows if r.kind == kind.value]
    if status is not None:
        rows = [r for r in rows if r.status == status.value]
    rows.sort(key=lambda r: r.created_at, reverse=True)
    paged, total = paginate(rows, page, page_size)
    return RunListOut(items=[_run_to_out(r) for r in paged], total=total)


@router.get("/{run_id}", response_model=RunDetailOut)
async def get_run(
    run_id: uuid.UUID, current_user: CurrentUser = Depends(get_mock_current_user)
) -> RunDetailOut:
    store = get_store()
    run = store.runs.get(run_id)
    if run is None or run.tenant_id != current_user.tenant_id:
        raise NotFoundError("run")

    if run.status in {AgentRunStatus.QUEUED.value, AgentRunStatus.RUNNING.value}:
        if run.kind == AgentRunKind.ICP_BUILD.value:
            advance_icp_run(store, run)
        elif run.kind == AgentRunKind.SOURCING.value:
            _advance_sourcing_run(store, run)

    steps = [s for s in store.steps.values() if s.run_id == run.id and s.tenant_id == current_user.tenant_id]
    steps.sort(key=lambda s: s.seq)
    return RunDetailOut(
        **_run_to_out(run).model_dump(),
        input=run.input,
        output_summary=run.output_summary,
        steps=[
            StepOut(
                id=s.id,
                seq=s.seq,
                step_type=s.step_type,
                name=s.name,
                input=s.input,
                output=s.output,
                model=s.model,
                input_tokens=s.input_tokens,
                output_tokens=s.output_tokens,
                cache_read_tokens=s.cache_read_tokens,
                cost_usd=s.cost_usd,
                latency_ms=s.latency_ms,
                lead_id=s.lead_id,
                created_at=s.created_at,
            )
            for s in steps
        ],
    )
