"""Feedback agent (P4-4): won/lost outcomes → a few rules for the lead scorer ("the system gets smarter").

The numbers are computed by code (app.services.insights.compute_stats); the model only turns them into short,
actionable rules, ICP suggestions and caveats. SMART tier, effort medium. Example leads are wrapped as
untrusted <examples> data and contain no phone numbers.
"""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.agents.llm import ModelTier, llm_structured
from app.core.tracing import RunContext, mask_phones
from app.schemas.agent_io import ICP

PROMPT_VERSION = "feedback@1"
SYSTEM = (Path(__file__).parent / "prompts" / "feedback.md").read_text(encoding="utf-8")

MAX_INSIGHTS = 7
MAX_SUGGESTIONS = 4
MAX_CHARS = 300


class LearnedInsights(BaseModel):
    insights: list[str] = Field(description="3-7 actionable rules for the scorer, citing the numbers")
    icp_suggestions: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)


def _clean(items: list[str], limit: int) -> list[str]:
    out: list[str] = []
    for item in items:
        text = " ".join(mask_phones(str(item)).split())[:MAX_CHARS]
        if text and text not in out:
            out.append(text)
    return out[:limit]


def build_user_message(stats: dict[str, Any], examples: list[dict[str, Any]], icp: ICP | None) -> str:
    icp_json = (
        icp.model_dump_json(
            include={"summary", "target_business_types", "regions", "must_have", "disqualifiers"}
        )
        if icp
        else "{}"
    )
    return (
        "<stats>\n" + json.dumps(stats, ensure_ascii=False) + "\n</stats>\n\n"
        "<examples>\n" + json.dumps(examples, ensure_ascii=False) + "\n</examples>\n\n"
        "<icp>\n" + icp_json + "\n</icp>\n\n"
        "Write the insights for the scorer."
    )


async def generate_insights(
    run: RunContext, *, stats: dict[str, Any], examples: list[dict[str, Any]], icp: ICP | None
) -> LearnedInsights:
    raw = await llm_structured(
        run,
        name="feedback.insights",
        tier=ModelTier.SMART,
        effort="medium",
        system=SYSTEM,
        user=build_user_message(stats, examples, icp),
        output_model=LearnedInsights,
        max_tokens=4000,
    )
    return LearnedInsights(
        insights=_clean(raw.insights, MAX_INSIGHTS),
        icp_suggestions=_clean(raw.icp_suggestions, MAX_SUGGESTIONS),
        caveats=_clean(raw.caveats, MAX_SUGGESTIONS),
    )
