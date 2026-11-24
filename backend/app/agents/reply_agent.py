"""Inbound conversational reply agent (P3-4)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.agents.llm import LLMProviderError, ModelTier, ToolSpec, llm_structured, llm_tool_loop
from app.core.tracing import RunContext
from app.models.tenants import BusinessSettings
from app.schemas.agent_io import ReplyClassification

PROMPT_VERSION = "reply_agent@1"
SYSTEM = (Path(__file__).parent / "prompts" / "reply_agent.md").read_text(encoding="utf-8")


class DraftedReply(BaseModel):
    reply_text: str = Field(min_length=2, max_length=1500)


async def draft_reply(
    run: RunContext,
    *,
    settings: BusinessSettings,
    classification: ReplyClassification,
    recent_messages: list[dict[str, str]],
    knowledge_snippets: str,
    tools: list[ToolSpec] | None = None,
    lead_id: Any = None,
) -> str:
    """Draft a grounded WhatsApp reply using tool-loop (falling back to structured if tools unsupported)."""
    convo = [
        {
            "role": "assistant" if m.get("direction") == "outbound" else "user",
            "content": m.get("body", ""),
        }
        for m in recent_messages[-8:]
        if m.get("body")
    ]
    context_block = (
        f"company_name: {settings.company_name}\n"
        f"language: {settings.language}\n"
        f"tone: {settings.tone}\n"
        f"allowed_offers: {settings.allowed_offers}\n"
        f"max_discount_percent: {settings.max_discount_percent}\n"
        f"products: {settings.products or []}\n"
        f"detected_intent: {classification.intent.value}\n"
        f"knowledge_snippets:\n{knowledge_snippets or '(none)'}"
    )

    if tools:
        try:
            loop_res = await llm_tool_loop(
                run,
                name="reply_agent.reply",
                tier=ModelTier.SMART,
                system=SYSTEM,
                cached_context=context_block,
                messages=convo,
                tools=tools,
                effort="low",
                max_iterations=3,
                max_tokens=700,
                lead_id=lead_id,
            )
            if loop_res.final_text.strip():
                return loop_res.final_text.strip()
        except LLMProviderError:
            pass

    user_prompt = (
        f"{context_block}\n\n"
        "Conversation:\n"
        + "\n".join(f"- {m['role']}: {m['content']}" for m in convo)
        + "\n\nWrite the next WhatsApp reply."
    )
    res = await llm_structured(
        run,
        name="reply_agent.reply_structured",
        tier=ModelTier.SMART,
        effort="low",
        system=SYSTEM,
        user=user_prompt,
        output_model=DraftedReply,
        max_tokens=700,
        lead_id=lead_id,
    )
    return res.reply_text.strip()
