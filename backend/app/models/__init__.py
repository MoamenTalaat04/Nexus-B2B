"""SQLAlchemy models. Import every model module here so Alembic autogenerate sees it.

One file per area (P0-2); see app/models/README.md for the ER diagram.
"""

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDPkMixin
from app.models.icp import IcpVersion
from app.models.knowledge import KnowledgeFile
from app.models.leads import Contact, Lead, LeadNote, LeadOutcome, LeadStatusHistory, SearchQuery
from app.models.messaging import ChannelConnection, Conversation, DemoRoute, Message, MessageTemplate
from app.models.notifications import LearnedInsight, Notification
from app.models.runs import AgentRun, AgentStep
from app.models.tenants import BusinessSettings, Tenant, User

__all__ = [
    "AgentRun",
    "AgentStep",
    "Base",
    "BusinessSettings",
    "ChannelConnection",
    "Contact",
    "Conversation",
    "DemoRoute",
    "IcpVersion",
    "KnowledgeFile",
    "Lead",
    "LeadNote",
    "LeadOutcome",
    "LeadStatusHistory",
    "LearnedInsight",
    "Message",
    "MessageTemplate",
    "Notification",
    "SearchQuery",
    "Tenant",
    "TenantMixin",
    "TimestampMixin",
    "UUIDPkMixin",
    "User",
]
