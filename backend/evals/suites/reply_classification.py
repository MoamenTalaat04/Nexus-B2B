"""P3-4 Reply classification eval suite."""

from pathlib import Path
from typing import Any

from app.agents.reply_classifier import classify_reply

DATASET = Path(__file__).parents[1] / "datasets" / "reply_classification.jsonl"


async def run_case(case: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    res = await classify_reply(
        ctx["run"],
        inbound_text=case["text"],
        recent_messages=[],
        language=case.get("language", "ar-EG"),
    )
    intent_ok = res.intent.value == case["expected_intent"]
    human_ok = True if "expected_human" not in case else (res.asks_for_human == bool(case["expected_human"]))
    discount_ok = (
        True
        if "expected_min_discount" not in case
        else (res.requested_discount_percent is not None and res.requested_discount_percent >= case["expected_min_discount"])
    )
    passed = intent_ok and human_ok and discount_ok
    return {
        "id": case["id"],
        "passed": passed,
        "predicted_intent": res.intent.value,
        "expected_intent": case["expected_intent"],
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for r in results if r.get("passed"))
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": (passed / total) if total else 0.0,
    }
