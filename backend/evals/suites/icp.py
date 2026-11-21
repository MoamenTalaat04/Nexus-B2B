"""P1-4 ICP builder eval suite."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from app.agents.icp_builder import build_icp
from evals.graders import grade_icp_case

DATASET = Path(__file__).parents[1] / "datasets" / "icp.jsonl"


async def run_case(case: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """Run `build_icp` on one JSONL case and grade the resulting profile + ICP."""
    settings = SimpleNamespace(
        company_name=case["company_name"],
        website=case.get("website") or "",
        description=case.get("description") or "",
        ideal_customer_text=case.get("ideal_customer_text") or "",
        products=case.get("products") or [],
        target_regions=case.get("target_regions") or [],
        language=case.get("language", "ar-EG"),
        tone=case.get("tone", "friendly"),
        allowed_offers=case.get("allowed_offers", ""),
        max_discount_percent=int(case.get("max_discount_percent", 0)),
    )
    profile, icp = await build_icp(
        ctx["run"],
        settings=settings,  # type: ignore[arg-type]
        knowledge_text=str(case.get("knowledge_text") or ""),
    )
    graded = grade_icp_case(case, profile, icp)
    return {
        "id": case["id"],
        "passed": graded["passed"],
        "score": graded["score"],
        "checks": graded["checks"],
        "regions": [r.governorate for r in icp.regions],
        "language": icp.language,
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate pass rate and per-check breakdown across all ICP eval cases."""
    total = len(results)
    passed = sum(1 for r in results if r.get("passed"))
    check_names = list(results[0]["checks"].keys()) if results else []
    breakdown = {
        name: sum(1 for r in results if r["checks"].get(name)) / total if total else 0.0
        for name in check_names
    }
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": (passed / total) if total else 0.0,
        "checks_breakdown": breakdown,
    }
