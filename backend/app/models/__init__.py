"""SQLAlchemy models. Import every model module here so Alembic autogenerate sees it.

P0-2 adds the domain models (one file per area) and imports them below.
"""

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDPkMixin
from app.models.icp import IcpVersion
from app.models.leads import Contact, Lead, LeadStatusHistory, SearchQuery
from app.models.messaging import ChannelConnection, Conversation, Message, MessageTemplate
from app.models.notifications import Notification
from app.models.runs import AgentRun, AgentStep
from app.models.tenants import BusinessSettings, Tenant

__all__ = [
    "AgentRun",
    "AgentStep",
    "Base",
    "BusinessSettings",
    "ChannelConnection",
    "Contact",
    "Conversation",
    "IcpVersion",
    "Lead",
    "LeadStatusHistory",
    "Message",
    "MessageTemplate",
    "Notification",
    "SearchQuery",
    "Tenant",
    "TenantMixin",
    "TimestampMixin",
    "UUIDPkMixin",
]
