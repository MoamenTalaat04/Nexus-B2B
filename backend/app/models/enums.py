"""Enums from docs/CONTRACTS.md section 2, verbatim.

Stored in Postgres as text with a CHECK constraint (see `enum_check`), mirrored in frontend/src/lib/types.ts.

Note: written in P0-3 because the run tables need AgentRunKind/AgentRunStatus/StepType. P0-2 owns this
file; it already contains every enum from the contract, so P0-2 only needs to keep it in sync.
"""

from enum import StrEnum

from sqlalchemy import CheckConstraint


class LeadStatus(StrEnum):
    NEW = "new"
    QUALIFIED = "qualified"
    DISQUALIFIED = "disqualified"
    ENRICHED = "enriched"
    NO_CONTACT = "no_contact"
    QUEUED = "queued"
    CONTACTED = "contacted"
    REPLIED = "replied"
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    WANTS_OFFER = "wants_offer"
    WANTS_MANAGEMENT = "wants_management"
    LATER = "later"
    WRONG_CONTACT = "wrong_contact"
    OPTED_OUT = "opted_out"
    WON = "won"
    LOST = "lost"


class ReplyIntent(StrEnum):
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    WANTS_OFFER = "wants_offer"
    WANTS_MANAGEMENT = "wants_management"
    LATER = "later"
    WRONG_CONTACT = "wrong_contact"
    OPTED_OUT = "opted_out"
    QUESTION = "question"
    OTHER = "other"


class AutonomyMode(StrEnum):
    APPROVE_ALL = "approve_all"
    APPROVE_FIRST_TOUCH = "approve_first_touch"
    AUTOPILOT = "autopilot"


class FirstTouchMode(StrEnum):
    ASSISTED = "assisted"  # the owner sends first touches/follow-ups from their own WhatsApp (wa.me link)
    API_TEMPLATE = "api_template"  # the agent sends approved templates through the Cloud API


class AgentRunKind(StrEnum):
    ICP_BUILD = "icp_build"
    SOURCING = "sourcing"
    SCORING = "scoring"
    ENRICHMENT = "enrichment"
    OUTREACH_TICK = "outreach_tick"
    REPLY = "reply"
    FEEDBACK = "feedback"


class AgentRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepType(StrEnum):
    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    EXTERNAL_API = "external_api"
    DECISION = "decision"
    ERROR = "error"


class ChannelType(StrEnum):
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    EMAIL = "email"


class ContactType(StrEnum):
    MOBILE = "mobile"
    LANDLINE = "landline"
    EMAIL = "email"
    WHATSAPP_LINK = "whatsapp_link"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    WEBSITE = "website"


class MessageDirection(StrEnum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"


class MessageAuthor(StrEnum):
    AGENT = "agent"
    HUMAN = "human"
    LEAD = "lead"


class MessageKind(StrEnum):
    TEMPLATE = "template"
    TEXT = "text"
    ASSISTED = "assisted"  # sent by the owner via a wa.me link


class MessageStatus(StrEnum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    AWAITING_MANUAL_SEND = "awaiting_manual_send"  # assisted: ready for the owner to send from their phone
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    RECEIVED = "received"
    BLOCKED = "blocked"  # refused by a guardrail (opt-out, cap)


class OutreachPurpose(StrEnum):
    FIRST_TOUCH = "first_touch"
    FOLLOWUP = "followup"
    REPLY = "reply"


# Intent → status mapping used by the reply pipeline (CONTRACTS section 2).
INTENT_TO_STATUS: dict[ReplyIntent, LeadStatus] = {
    ReplyIntent.INTERESTED: LeadStatus.INTERESTED,
    ReplyIntent.NOT_INTERESTED: LeadStatus.NOT_INTERESTED,
    ReplyIntent.WANTS_OFFER: LeadStatus.WANTS_OFFER,
    ReplyIntent.WANTS_MANAGEMENT: LeadStatus.WANTS_MANAGEMENT,
    ReplyIntent.LATER: LeadStatus.LATER,
    ReplyIntent.WRONG_CONTACT: LeadStatus.WRONG_CONTACT,
    ReplyIntent.OPTED_OUT: LeadStatus.OPTED_OUT,
    ReplyIntent.QUESTION: LeadStatus.REPLIED,
    ReplyIntent.OTHER: LeadStatus.REPLIED,
}


def enum_check(column: str, values: type[StrEnum] | tuple[str, ...]) -> CheckConstraint:
    """CHECK (column IN (...)) built from a StrEnum (or a tuple of literals). Named `<column>_valid`."""
    items = [v.value for v in values] if isinstance(values, type) else list(values)
    allowed = ", ".join(f"'{v}'" for v in items)
    return CheckConstraint(f"{column} IN ({allowed})", name=f"{column}_valid")
