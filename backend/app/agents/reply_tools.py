"""Bound tools for the inbound reply agent (P3-4)."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm import ToolSpec
from app.models.leads import Lead
from app.models.tenants import BusinessSettings
from app.services import knowledge as knowledge_service
from app.services.notifications import notify_owner


class SearchKnowledgeIn(BaseModel):
    query: str = Field(min_length=1, max_length=200)


class EscalateIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


def build_reply_tools(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    lead: Lead,
    settings: BusinessSettings,
) -> list[ToolSpec]:
    """Build tenant- and lead-scoped ToolSpecs for the reply agent."""

    async def _search_knowledge(args: BaseModel) -> dict[str, Any]:
        parsed = SearchKnowledgeIn.model_validate(args)
        hits = await knowledge_service.search(session, tenant_id, parsed.query, limit=3)
        return {
            "matches": [
                {"filename": h.filename, "snippet": h.snippet}
                for h in hits
            ]
        }

    async def _get_offerings(_args: BaseModel) -> dict[str, Any]:
        return {
            "company_name": settings.company_name,
            "products": settings.products or [],
            "allowed_offers": settings.allowed_offers,
            "max_discount_percent": settings.max_discount_percent,
        }

    async def _escalate(args: BaseModel) -> dict[str, Any]:
        parsed = EscalateIn.model_validate(args)
        lead.agent_paused = True
        await notify_owner(
            session,
            tenant_id=tenant_id,
            kind="escalation",
            title=f"Lead {lead.name} needs human follow-up",
            body=parsed.reason,
        )
        await session.flush()
        return {"escalated": True, "agent_paused": True}

    return [
        ToolSpec(
            name="search_knowledge",
            description="Search uploaded company catalogs, FAQs, and price lists for factual answers.",
            input_model=SearchKnowledgeIn,
            handler=_search_knowledge,
        ),
        ToolSpec(
            name="get_company_offerings",
            description="Get the company's products/services, allowed offers, and maximum allowed discount percent.",
            input_model=BaseModel,
            handler=_get_offerings,
        ),
        ToolSpec(
            name="escalate_to_human",
            description="Pause AI replies for this lead and notify the owner when human intervention is needed.",
            input_model=EscalateIn,
            handler=_escalate,
        ),
    ]
