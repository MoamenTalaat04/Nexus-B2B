"""P2-1 + P2-2 joint self-check: B's sourcing job with C's REAL query generator and Google Places, run twice.

    cd backend
    USE_MOCK_ADAPTERS=false uv run python -m scripts.try_sourcing             # 2 runs, then delete the tenant
    USE_MOCK_ADAPTERS=false uv run python -m scripts.try_sourcing --keep      # keep the demo tenant
    USE_MOCK_ADAPTERS=false uv run python -m scripts.try_sourcing --max 20    # new leads per run (30)

Needs USE_MOCK_LLM=false + LLM_* and GOOGLE_PLACES_API_KEY in .env (the free Maps Demo Key works).
Each search is one Places request; a run stops once --max new leads were created. The second run asks
the model for NEW
queries (recent ones are excluded), and the overlap between the two runs shows whether dedupe works.
Scoring is not enqueued here (no worker needed). The ICP is the saved real one in docs/examples.
"""

import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import delete, func, select, text

from app.config import settings as app_settings
from app.db import SessionLocal
from app.models.leads import Lead, SearchQuery
from app.models.tenants import BusinessSettings, Tenant
from app.schemas.agent_io import ICP, CompanyProfile
from app.services import icp_service
from app.workers.jobs import sourcing

TENANT_NAME = "Sourcing check (demo)"
EXAMPLE_ICP = Path(__file__).resolve().parents[2] / "docs" / "examples" / "icp-demo-gemini.json"
MAX = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 30

DUPLICATES_SQL = text(
    """
    SELECT 'same place id' AS kind, count(*) FROM (
        SELECT source_ref FROM leads WHERE tenant_id = :t AND source_ref IS NOT NULL
        GROUP BY source_ref HAVING count(*) > 1) a
    UNION ALL
    SELECT 'same mobile', count(*) FROM (
        SELECT raw->>'phone_e164' FROM leads WHERE tenant_id = :t AND raw->>'phone_e164' IS NOT NULL
        GROUP BY raw->>'phone_e164' HAVING count(*) > 1) b
    UNION ALL
    SELECT 'same name + city', count(*) FROM (
        SELECT lower(name), city FROM leads WHERE tenant_id = :t
        GROUP BY lower(name), city HAVING count(*) > 1) c
    """
)


async def cleanup() -> None:
    async with SessionLocal() as session:
        await session.execute(delete(Tenant).where(Tenant.name == TENANT_NAME))
        await session.commit()


async def main() -> int:
    if app_settings.USE_MOCK_ADAPTERS or app_settings.USE_MOCK_LLM or not app_settings.GOOGLE_PLACES_API_KEY:
        print("needs USE_MOCK_ADAPTERS=false, USE_MOCK_LLM=false and GOOGLE_PLACES_API_KEY")
        return 1

    async def no_queue(*args: object, **kwargs: object) -> str:  # scoring is not part of this check
        return "skipped"

    sourcing.enqueue = no_queue
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
                target_regions=[
                    {"governorate": "Cairo", "cities": ["Nasr City", "Heliopolis"]},
                    {"governorate": "Giza", "cities": []},
                ],
                onboarding_completed=True,
            )
        )
        await icp_service.save_version(
            session,
            tenant.id,
            CompanyProfile.model_validate(example["company_profile"]),
            ICP.model_validate(example["icp"]),
            "user",
            notes="P2-2 sourcing check (docs/examples)",
        )
        await session.commit()
        tenant_id = tenant.id

    try:
        for n in (1, 2):
            async with SessionLocal() as session:
                r = await sourcing.run_sourcing(session, tenant_id, max_results=MAX)
                await session.commit()
                queries = list(
                    (
                        await session.execute(
                            select(SearchQuery).where(SearchQuery.run_id == r.run_id).order_by(SearchQuery.id)
                        )
                    ).scalars()
                )
            print(f"\nrun {n}: {r.summary()}")
            for q in queries:
                print(
                    f"   {q.results_count:>2} results  {q.query_text}  "
                    f"{json.dumps(q.region, ensure_ascii=False)}"
                )

        async with SessionLocal() as session:
            total = await session.scalar(
                select(func.count()).select_from(Lead).where(Lead.tenant_id == tenant_id)
            )
            with_phone = await session.scalar(
                select(func.count())
                .select_from(Lead)
                .where(Lead.tenant_id == tenant_id, Lead.raw["phone_e164"].astext.is_not(None))
            )
            by_gov = (
                await session.execute(
                    select(Lead.governorate, func.count())
                    .where(Lead.tenant_id == tenant_id)
                    .group_by(Lead.governorate)
                    .order_by(func.count().desc())
                )
            ).all()
            dupes = (await session.execute(DUPLICATES_SQL, {"t": tenant_id})).all()
        print(f"\nleads: {total} ({with_phone} with a mobile/phone)  by governorate: {dict(by_gov)}")
        print("duplicate groups in SQL:", {kind: count for kind, count in dupes})
        return 0
    finally:
        if "--keep" not in sys.argv:
            await cleanup()
            print("demo tenant deleted (use --keep to keep it)")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(asyncio.run(main()))
