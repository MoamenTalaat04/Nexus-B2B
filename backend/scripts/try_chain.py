"""B + A + C real chain self-check: sourcing → scoring → enrichment → outreach tick, with real services.

    cd backend
    USE_MOCK_ADAPTERS=false uv run python -m scripts.try_chain            # ~10 leads, then delete the tenant
    USE_MOCK_ADAPTERS=false uv run python -m scripts.try_chain --max 15 --keep

Needs USE_MOCK_LLM=false + LLM_*, GOOGLE_PLACES_API_KEY and DEMO_TEST_PHONES in the private .env.

The jobs run directly in order (no worker). Each `enqueue` is captured and its arguments go to the next
job, so this also checks the hand-off between members. Enrichment reads the public websites of the leads
found (robots.txt respected). No WhatsApp channel is connected: the intro/followup template rows are copied
from the mock and marked approved, and outreach stops at pending approval, so nothing is sent.
Demo mode stays on.
"""

import asyncio
import json
import os
import sys
import uuid
from collections import Counter
from datetime import UTC, datetime, time
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select

from app.adapters.channels.mock import MOCK_TEMPLATES
from app.config import settings as app_settings
from app.db import SessionLocal
from app.models.enums import MessageStatus
from app.models.leads import Contact, Lead
from app.models.messaging import Message, MessageTemplate
from app.models.tenants import BusinessSettings, Tenant
from app.schemas.agent_io import ICP, CompanyProfile
from app.services import icp_service, messaging, outreach
from app.workers.jobs import enrichment, scoring, sourcing

TENANT_NAME = "Chain check (demo)"
ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_ICP = ROOT / "docs" / "examples" / "icp-demo-gemini.json"
MAX = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 10
queued: list[tuple[str, dict[str, Any]]] = []


async def capture(job: str, **kwargs: Any) -> str:
    queued.append((job, kwargs))
    return f"captured-{len(queued)}"


def demo_phones() -> list[str]:
    raw = os.environ.get("DEMO_TEST_PHONES", "")
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("DEMO_TEST_PHONES=") and not raw:
            raw = line.split("=", 1)[1]
    return [p.strip() for p in raw.split(",") if p.strip()]


async def cleanup() -> None:
    async with SessionLocal() as session:
        await session.execute(delete(Tenant).where(Tenant.name == TENANT_NAME))
        await session.commit()


async def status_counts(tenant_id: uuid.UUID) -> dict[str, int]:
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(Lead.status, func.count()).where(Lead.tenant_id == tenant_id).group_by(Lead.status)
            )
        ).all()
    return {status: count for status, count in rows}


async def main() -> int:
    phones = demo_phones()
    if app_settings.USE_MOCK_ADAPTERS or app_settings.USE_MOCK_LLM or not app_settings.GOOGLE_PLACES_API_KEY:
        print("needs USE_MOCK_ADAPTERS=false, USE_MOCK_LLM=false and GOOGLE_PLACES_API_KEY")
        return 1
    if not phones:
        print("needs DEMO_TEST_PHONES")
        return 1
    sourcing.enqueue = capture
    scoring.enqueue = capture

    async def no_send(*args: object, **kwargs: object) -> None:
        return None

    messaging.enqueue_send = no_send
    await cleanup()
    example = json.loads(EXAMPLE_ICP.read_text(encoding="utf-8"))
    async with SessionLocal() as session:
        tenant = Tenant(name=TENANT_NAME)
        session.add(tenant)
        await session.flush()
        session.add(
            BusinessSettings(
                tenant_id=tenant.id,
                company_name="مصنع نور لملابس الأطفال (شركة تجريبية)",
                description="مصنع ملابس أطفال في شبرا الخيمة، بيبيع جملة للمحلات.",
                target_regions=[{"governorate": "Cairo", "cities": ["Nasr City"]}],
                first_touch_mode="api_template",
                autonomy_mode="approve_first_touch",
                agent_enabled=True,
                demo_mode=True,
                demo_whitelist=phones,
                quiet_hours_start=time(0, 0),
                quiet_hours_end=time(23, 59),
                working_days=[0, 1, 2, 3, 4, 5, 6],
                onboarding_completed=True,
            )
        )
        await icp_service.save_version(
            session,
            tenant.id,
            CompanyProfile.model_validate(example["company_profile"]),
            ICP.model_validate(example["icp"]),
            "user",
            notes="chain check (docs/examples)",
        )
        for t in MOCK_TEMPLATES:
            if t.name in ("intro", "followup"):
                session.add(
                    MessageTemplate(
                        tenant_id=tenant.id,
                        name=t.name,
                        language=t.language,
                        category=t.category,
                        purpose=t.name,
                        body_text=t.body_text,
                        param_count=t.param_count,
                        status="approved",
                    )
                )
        await session.commit()
        tenant_id = tenant.id

    ok = True
    try:
        # 1. B: sourcing (C's query generator + Google Places)
        async with SessionLocal() as session:
            src = await sourcing.run_sourcing(session, tenant_id, max_results=MAX)
            await session.commit()
        print("1. sourcing:", src.summary())
        print("   leads by status:", await status_counts(tenant_id))
        handoff = [kw for job, kw in queued if job == "job_score_leads"]
        print("   handed to scoring:", bool(handoff))
        ok &= bool(handoff)

        # 2. A: scoring with the run id B handed over
        async with SessionLocal() as session:
            counts = await scoring.run_score_leads(session, tenant_id, uuid.UUID(str(handoff[-1]["run_id"])))
        print("\n2. scoring:", counts)
        async with SessionLocal() as session:
            scored = (
                await session.execute(
                    select(Lead)
                    .where(Lead.tenant_id == tenant_id, Lead.score.is_not(None))
                    .order_by(Lead.score.desc())
                )
            ).scalars()
            for lead in scored:
                reason = (lead.score_reasons or ["-"])[0]
                print(f"   {lead.score:>2} {lead.status:<12} {lead.name}  — {reason}")
        enrich_handoff = [kw for job, kw in queued if job == "job_enrich_leads"]
        print(
            "   handed to enrichment:", len(enrich_handoff[-1]["lead_ids"]) if enrich_handoff else 0, "leads"
        )

        # 3. A: enrichment of the qualified leads
        if enrich_handoff:
            lead_ids = [uuid.UUID(i) for i in enrich_handoff[-1]["lead_ids"]]
            async with SessionLocal() as session:
                summary = await enrichment.run_enrich_leads(session, tenant_id, lead_ids)
            print("\n3. enrichment:", summary)
            ok &= summary["failed"] == 0
            async with SessionLocal() as session:
                types = (
                    await session.execute(
                        select(Contact.type, func.count())
                        .where(Contact.tenant_id == tenant_id, Contact.is_primary)
                        .group_by(Contact.type)
                    )
                ).all()
            print("   primary contacts by type:", dict(types))
        else:
            print("\n3. enrichment: skipped (no qualified leads)")

        # 4. C: outreach tick (approve_first_touch → pending approval; nothing is sent)
        async with SessionLocal() as session:
            bs = (
                await session.execute(select(BusinessSettings).where(BusinessSettings.tenant_id == tenant_id))
            ).scalar_one()
            tick = await outreach.tick_tenant(session, bs, now=datetime.now(UTC))
        print(f"\n4. outreach tick: created={tick.created} skipped={dict(tick.skipped)} reason={tick.reason}")
        async with SessionLocal() as session:
            msgs = list(
                (await session.execute(select(Message).where(Message.tenant_id == tenant_id))).scalars()
            )
        print("   messages by status:", dict(Counter(m.status for m in msgs)))
        for m in msgs[:3]:
            print("   ", m.body)
        if msgs:
            ok &= all(m.status == MessageStatus.PENDING_APPROVAL.value for m in msgs)

        print("\nfinal leads by status:", await status_counts(tenant_id))
        print("CHAIN OK" if ok else "CHAIN HAD PROBLEMS")
        return 0 if ok else 2
    finally:
        if "--keep" not in sys.argv:
            await cleanup()
            print("demo tenant deleted (use --keep to keep it)")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(asyncio.run(main()))
