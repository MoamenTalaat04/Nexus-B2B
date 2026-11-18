"""Generate one ICP with the REAL model from a FICTIONAL demo business (P1-3 manual check).

    cd backend
    uv run python -m scripts.try_icp                       # prints the CompanyProfile + ICP as JSON
    uv run python -m scripts.try_icp --out ../docs/x.json  # also saves it (UTF-8)

Needs USE_MOCK_LLM=false and the LLM_* values in .env. Creates a temporary tenant with demo onboarding answers
and a short demo catalogue, runs the real ICP builder (two SMART calls), prints the result plus tokens/cost,
then deletes the tenant. All data is made up: free tiers may use requests to improve the provider's models.
"""

import asyncio
import json
import sys
import uuid
from pathlib import Path

from sqlalchemy import delete, select

from app.agents import icp_builder
from app.config import settings
from app.core.tracing import agent_run
from app.db import SessionLocal
from app.models.enums import AgentRunKind
from app.models.runs import AgentRun, AgentStep
from app.models.tenants import BusinessSettings, Tenant

OUT_PATH = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None

DEMO_SETTINGS = {
    "company_name": "مصنع نور لملابس الأطفال (شركة تجريبية)",
    "website": "https://nour-kids.example",
    "description": "مصنع ملابس أطفال في شبرا الخيمة، بننتج أطقم صيفي وترينجات وبيجامات من سنة لـ 12 سنة.",
    "ideal_customer_text": "محلات ملابس الأطفال والبيبي الصغيرة والمتوسطة اللي بتشتري جملة كل موسم.",
    "products": [
        {
            "name": "أطقم أطفال قطن صيفي",
            "description": "تيشيرت وشورت قطن 100%",
            "price_range": "120-180 جنيه للطقم جملة",
            "min_order": "3 دستة من الموديل",
        },
        {
            "name": "ترينجات شتوي",
            "description": "قطن مبطن، ولادي وبناتي",
            "price_range": None,
            "min_order": "3 دستة",
        },
    ],
    "target_regions": [
        {"governorate": "Cairo", "cities": ["Nasr City", "Heliopolis"]},
        {"governorate": "Giza", "cities": []},
    ],
    "allowed_offers": "خصم 5% على أول طلبية فوق 10 دستة",
    "max_discount_percent": 5,
}
DEMO_KNOWLEDGE = """### catalogue.md
مصنع نور لملابس الأطفال — كتالوج موسم الصيف (بيانات تجريبية)
- أطقم قطن 100% من سنة لـ 8 سنين، ألوان ثابتة وخياطة مزدوجة.
- توصيل للقاهرة والجيزة خلال 3 أيام عمل.
- الدفع: نص المبلغ مقدم والباقي عند الاستلام.
- أقل طلبية 3 دستة من الموديل، وممكن تقسيم المقاسات.
"""


async def main() -> int:
    if settings.USE_MOCK_LLM:
        print("USE_MOCK_LLM=true in .env: set it to false to call the real model.")
        return 1
    async with SessionLocal() as session:
        tenant = Tenant(name=f"ICP demo (temporary) {uuid.uuid4().hex[:6]}")
        session.add(tenant)
        await session.flush()
        session.add(BusinessSettings(tenant_id=tenant.id, onboarding_completed=True, **DEMO_SETTINGS))
        await session.commit()
    try:
        async with SessionLocal() as session:
            s = (
                await session.execute(select(BusinessSettings).where(BusinessSettings.tenant_id == tenant.id))
            ).scalar_one()
            async with agent_run(
                tenant.id, AgentRunKind.ICP_BUILD, trigger="manual", input={"demo": True}
            ) as run:
                profile, icp = await icp_builder.build_icp(run, settings=s, knowledge_text=DEMO_KNOWLEDGE)
        result = json.dumps(
            {"company_profile": profile.model_dump(), "icp": icp.model_dump()}, ensure_ascii=False, indent=2
        )
        if OUT_PATH:
            await asyncio.to_thread(Path(OUT_PATH).write_text, result + "\n", encoding="utf-8")
            print(f"saved to {OUT_PATH}")
        print(result)
        async with SessionLocal() as session:
            row = await session.get(AgentRun, run.run_id)
            steps = list(
                (await session.execute(select(AgentStep).where(AgentStep.run_id == run.run_id))).scalars()
            )
        assert row is not None
        llm = [st for st in steps if st.step_type == "llm_call"]
        print(
            f"\n{len(llm)} model calls, {sum(st.latency_ms for st in llm) / 1000:.1f}s, tokens in/out "
            f"{row.total_input_tokens}/{row.total_output_tokens} "
            f"(cached {sum(st.cache_read_tokens for st in llm)}), "
            f"estimated cost ${float(row.total_cost_usd):.4f} at paid prices"
        )
        guard = next((st.output for st in steps if st.name == "icp_builder.guardrails"), {})
        print("guardrail changes:", list((guard or {}).get("changes", {}).keys()) or "none")
        return 0
    finally:
        async with SessionLocal() as session:
            await session.execute(delete(Tenant).where(Tenant.id == tenant.id))
            await session.commit()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(asyncio.run(main()))
