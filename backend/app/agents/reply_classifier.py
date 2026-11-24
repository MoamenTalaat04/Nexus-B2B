"""Inbound reply intent classifier agent (P3-4)."""

from pathlib import Path

from app.agents.llm import ModelTier, llm_structured
from app.core.tracing import RunContext
from app.schemas.agent_io import ReplyClassification

PROMPT_VERSION = "reply_classifier@1"
SYSTEM = (Path(__file__).parent / "prompts" / "reply_classifier.md").read_text(encoding="utf-8")


async def classify_reply(
    run: RunContext,
    *,
    inbound_text: str,
    recent_messages: list[dict[str, str]],
    language: str = "ar-EG",
    lead_id=None,
) -> ReplyClassification:
    """Classify the lead's inbound message into a ReplyIntent and extract signals."""
    history_lines = "\n".join(
        f"- [{m.get('direction', 'unknown')}] {m.get('body', '').strip()}"
        for m in recent_messages[-6:]
        if m.get("body")
    )
    user = (
        f"Expected language: {language}\n"
        f"Recent conversation:\n{history_lines or '(none)'}\n\n"
        f"Latest inbound message:\n{inbound_text.strip()}"
    )
    return await llm_structured(
        run,
        name="reply_classifier.classify",
        tier=ModelTier.FAST,
        effort="low",
        system=SYSTEM,
        user=user,
        output_model=ReplyClassification,
        max_tokens=500,
        lead_id=lead_id,
    )
