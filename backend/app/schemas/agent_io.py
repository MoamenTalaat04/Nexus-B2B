"""Domain schemas exchanged with the agents (CONTRACTS section 8, verbatim).

Every agent's structured output is one of these models; llm_structured validates answers against them.
Written in P1-3 (which needs CompanyProfile and ICP); the others are here so later tasks import them as-is.
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import ReplyIntent


class Product(BaseModel):
    name: str
    description: str = ""
    price_range: str | None = None
    min_order: str | None = None


class FAQ(BaseModel):
    q: str
    a: str


class CompanyProfile(BaseModel):
    company_name: str
    one_liner: str
    products: list[Product]
    differentiators: list[str]
    target_customer_summary: str
    allowed_offers: str = ""
    max_discount_percent: int = 0
    faqs: list[FAQ] = Field(default_factory=list)
    tone: str = "friendly"
    language: str = "ar-EG"


class RegionTarget(BaseModel):
    governorate: str
    cities: list[str] = Field(default_factory=list)


class ICP(BaseModel):
    summary: str
    target_business_types: list[str]  # Arabic + English phrasings people type into Google Maps
    include_keywords: list[str]
    exclude_keywords: list[str]
    google_place_types: list[str] = Field(default_factory=list)  # e.g. ["clothing_store", "baby_store"]
    regions: list[RegionTarget]
    business_size: Literal["micro", "small", "medium", "large", "any"] = "any"
    must_have: list[str]
    nice_to_have: list[str]
    disqualifiers: list[str]
    value_proposition: str
    pain_points: list[str]
    outreach_angle: str
    language: str = "ar-EG"


class GeneratedQuery(BaseModel):
    query: str
    region: RegionTarget
    rationale: str


class QueryPlan(BaseModel):
    queries: list[GeneratedQuery]  # 5-15 queries


class LeadScore(BaseModel):
    lead_ref: str  # the lead id as a string
    score: int  # 0..10
    fit: Literal["fit", "partial", "not_fit"]
    reasons: list[str]  # 1-4 short reasons
    disqualify_reason: str | None = None


class LeadScoreBatch(BaseModel):
    scores: list[LeadScore]


class AssistedMessage(BaseModel):  # assisted mode: free text the owner sends from their own WhatsApp
    text: str  # Egyptian Arabic, <= 500 chars, ends with the assistant link line if given
    rationale: str


class PersonalizedOpening(BaseModel):
    template_params: list[str]  # exactly param_count items; no newlines/tabs; <= 60 chars each
    preview_text: str  # rendered message for the approval UI
    rationale: str


class ReplyClassification(BaseModel):
    intent: ReplyIntent
    confidence: float
    summary: str
    requested_discount_percent: int | None = None
    asks_for_human: bool = False
    language: str = "ar-EG"
