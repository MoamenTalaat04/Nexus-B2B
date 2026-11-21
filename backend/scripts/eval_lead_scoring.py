"""P2-3 eval runner (stand-in until D's P1-4 harness lands): scores the 40 labelled leads with the REAL model.

    cd backend
    uv run python -m scripts.eval_lead_scoring          # needs USE_MOCK_LLM=false + LLM_* in .env

It calls A's scorer exactly as the scoring job does (batches of 15, FAST tier), then reuses A's
`evals/suites/lead_scoring.summarize` for precision/recall/confusion/injection. The dataset is fictional
("Little Stars Kids Wear" style kids-clothing leads); the ICP is the saved kids-clothing factory example in
docs/examples (same target: kids clothing shops in Cairo & Giza). Writes evals/results/lead_scoring-<ts>.json.
Runs inside one SCORING agent run on a temporary tenant (deleted afterwards) so the cost is traced.
"""

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete

from app.agents.lead_scorer import BATCH_SIZE, PROMPT_VERSION, LeadForScoring, score_leads
from app.config import settings as app_settings
from app.core.tracing import agent_run
from app.db import SessionLocal
from app.models.enums import AgentRunKind
from app.models.tenants import Tenant
from app.schemas.agent_io import ICP, CompanyProfile
from evals.suites import lead_scoring as suite

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_ICP = ROOT / "docs" / "examples" / "icp-demo-gemini.json"
RESULTS = Path(__file__).resolve().parents[1] / "evals" / "results"
TENANT_NAME = "Lead scoring eval (temp)"


def load_cases() -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in suite.DATASET.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def to_lead(data: dict[str, Any]) -> LeadForScoring:
    return LeadForScoring(
        id=str(data["id"]),
        name=str(data.get("name") or ""),
        category=data.get("category"),
        types=list(data.get("types") or []),
        address=data.get("address"),
        governorate=data.get("governorate"),
        city=data.get("city"),
        rating=data.get("rating"),
        reviews_count=data.get("reviews_count"),
        website=data.get("website"),
        business_status=data.get("business_status"),
    )


async def main() -> int:
    if app_settings.USE_MOCK_LLM:
        print("set USE_MOCK_LLM=false (and LLM_* in .env): this eval needs the real model")
        return 1
    cases = load_cases()
    example = json.loads(EXAMPLE_ICP.read_text(encoding="utf-8"))
    profile = CompanyProfile.model_validate(example["company_profile"])
    icp = ICP.model_validate(example["icp"])
    leads = [to_lead(c["lead"]) for c in cases]

    async with SessionLocal() as session:
        tenant = Tenant(name=TENANT_NAME)
        session.add(tenant)
        await session.commit()
        tenant_id = tenant.id
    try:
        async with agent_run(
            tenant_id, AgentRunKind.SCORING, trigger="manual", input={"eval": "lead_scoring"}
        ) as run:
            scores = await score_leads(run, icp=icp, profile=profile, insights=[], leads=leads)
            cost = float(run.total_cost_usd)
            tokens = (run.total_input_tokens, run.total_output_tokens)
    finally:
        async with SessionLocal() as session:
            await session.execute(delete(Tenant).where(Tenant.id == tenant_id))
            await session.commit()

    results = []
    for case, lead, score in zip(cases, leads, scores, strict=True):
        numeric = score.score
        results.append(
            {
                "lead_ref": lead.id,
                "lead_name": lead.name,
                "expected_fit": case["expected_fit"],
                "predicted_fit": score.fit,
                "score": numeric,
                "predicted_qualified": numeric is not None and int(numeric) >= 6,
                "reasons": list(score.reasons),
                "disqualify_reason": score.disqualify_reason,
            }
        )
    metrics = suite.summarize(results)
    metrics |= {
        "cases": len(results),
        "unscored": sum(1 for r in results if r["score"] is None),
        "model": app_settings.LLM_MODEL_FAST,
        "prompt_version": PROMPT_VERSION,
        "batch_size": BATCH_SIZE,
        "cost_usd_estimated": round(cost, 6),
        "cost_per_100_leads_usd": round(cost / len(results) * 100, 6) if results else None,
        "input_tokens": tokens[0],
        "output_tokens": tokens[1],
    }

    print(
        f"precision {metrics['precision']:.3f}   recall {metrics['recall']:.3f}   "
        f"injection {'PASS' if metrics['injection_passed'] else 'FAIL'}   unscored {metrics['unscored']}"
    )
    print("confusion (expected → predicted):")
    for expected, row in metrics["confusion_matrix"].items():
        print(f"   {expected:<8} {row}")
    print(
        f"cost ≈ ${metrics['cost_usd_estimated']} (${metrics['cost_per_100_leads_usd']} per 100 leads), "
        f"tokens in/out {tokens[0]}/{tokens[1]}, model {metrics['model']}"
    )
    wrong = [r for r in results if (r["expected_fit"] != "not_fit") != r["predicted_qualified"]]
    for r in wrong:
        print(
            f"   miss: {r['lead_ref']:<12} expected {r['expected_fit']:<8} "
            f"got {r['score']} {r['predicted_fit']}"
            f"  — {(r['reasons'] or ['-'])[0]}"
        )

    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"lead_scoring-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.json"
    out.write_text(
        json.dumps({"metrics": metrics, "results": results}, ensure_ascii=False, indent=2), "utf-8"
    )
    print("saved", out.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(asyncio.run(main()))
