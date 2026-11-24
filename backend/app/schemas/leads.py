"""Pydantic schemas for Leads list and stats endpoints (P2-4)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class LeadSummaryOut(BaseModel):
    id: uuid.UUID
    ref_code: str
    source: str
    name: str
    category: str | None = None
    address: str | None = None
    city: str | None = None
    governorate: str | None = None
    website: str | None = None
    rating: float | None = None
    reviews_count: int | None = None
    status: str
    score: int | None = None
    score_reasons: list[str] = Field(default_factory=list)
    disqualify_reason: str | None = None
    sourcing_run_id: uuid.UUID | None = None
    agent_paused: bool = False
    created_at: datetime
    updated_at: datetime


class LeadListOut(BaseModel):
    items: list[LeadSummaryOut] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 25


class LeadStatsOut(BaseModel):
    total: int = 0
    by_status: dict[str, int] = Field(default_factory=dict)
    avg_score: float | None = None
    qualified_count: int = 0
    enriched_count: int = 0
    contacted_count: int = 0
    won_count: int = 0
