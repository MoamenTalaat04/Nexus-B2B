"""P3-4 Reply safety eval suite."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from app.agents.reply_agent import draft_reply
from app.models.enums import ReplyIntent
from app.schemas.agent_io import ReplyClassification

DATASET = Path(__file__).parents[1] / "datasets" / "reply_safety.jsonl"


async def run_case(case: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    settings = SimpleNamespace(
        company_name="Nexus Demo Co",
        language="ar-EG",
        tone="friendly",
        allowed_offers="Standard B2B wholesale pricing",
        max_discount_percent=int(case.get("max_discount_percent", 10)),
        products=[{"name": "Wholesale Package", "price_range": "500 EGP", "description": "Standard B2B pack"}],
    )
    classification = ReplyClassification(
        intent=ReplyIntent.WANTS_OFFER,
        confidence=0.9,
        summary="Customer inquiry",
        language="ar-EG",
    )
    reply_text = await draft_reply(
        ctx["run"],
        settings=settings,  # type: ignore[arg-type]
        classification=classification,
        recent_messages=[{"direction": "inbound", "body": case["inbound"]}],
        knowledge_snippets="Delivery within Cairo takes 2-3 business days.",
    )
    lowered = reply_text.lower()
    forbidden = [str(s).lower() for s in case.get("forbidden_substrings", [])]
    safe = bool(reply_text.strip()) and all(f not in lowered for f in forbidden)
    return {"id": case["id"], "passed": safe, "reply_preview": reply_text[:120]}


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for r in results if r.get("passed"))
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": (passed / total) if total else 0.0,
    }
