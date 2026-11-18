"""Lead state machine (CONTRACTS section 4). Lead status changes ONLY through transition().

Stand-in written in P3-3 (outreach moves leads ENRICHED→QUEUED→CONTACTED) from the contract's table, verbatim.
P0-2 owns this file.
"""

import uuid
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import LeadStatus as S
from app.models.leads import Lead, LeadStatusHistory

Actor = Literal["agent", "user", "system"]

ALLOWED: dict[S, set[S]] = {
    S.NEW: {S.QUALIFIED, S.DISQUALIFIED},
    S.QUALIFIED: {S.ENRICHED, S.NO_CONTACT, S.DISQUALIFIED},
    S.DISQUALIFIED: set(),
    S.NO_CONTACT: {S.ENRICHED},  # e.g. a manual contact was added
    S.ENRICHED: {S.QUEUED},
    S.QUEUED: {S.CONTACTED, S.ENRICHED},  # back to ENRICHED if the first message is rejected
    S.CONTACTED: {S.REPLIED, S.WON, S.LOST},
    S.REPLIED: {
        S.INTERESTED,
        S.NOT_INTERESTED,
        S.WANTS_OFFER,
        S.WANTS_MANAGEMENT,
        S.LATER,
        S.WRONG_CONTACT,
        S.WON,
        S.LOST,
    },
    S.INTERESTED: {S.WANTS_OFFER, S.WANTS_MANAGEMENT, S.LATER, S.NOT_INTERESTED, S.WON, S.LOST, S.REPLIED},
    S.WANTS_OFFER: {S.INTERESTED, S.WANTS_MANAGEMENT, S.LATER, S.NOT_INTERESTED, S.WON, S.LOST, S.REPLIED},
    S.WANTS_MANAGEMENT: {S.INTERESTED, S.WANTS_OFFER, S.LATER, S.NOT_INTERESTED, S.WON, S.LOST, S.REPLIED},
    S.LATER: {S.CONTACTED, S.REPLIED, S.INTERESTED, S.NOT_INTERESTED, S.WON, S.LOST},
    S.NOT_INTERESTED: {S.REPLIED, S.LOST},
    S.WRONG_CONTACT: {S.ENRICHED, S.LOST},
    S.WON: set(),
    S.LOST: {S.REPLIED},
    S.OPTED_OUT: set(),
}
TERMINAL = {S.WON, S.OPTED_OUT}


class InvalidTransition(Exception):
    def __init__(self, from_status: S, to_status: S) -> None:
        super().__init__(f"Lead status cannot change from {from_status.value} to {to_status.value}.")
        self.from_status = from_status
        self.to_status = to_status


def is_allowed(from_status: S, to_status: S) -> bool:
    if to_status == S.OPTED_OUT:
        return from_status not in TERMINAL  # any non-terminal status may opt out
    return to_status in ALLOWED.get(from_status, set())


async def transition(
    session: AsyncSession,
    lead: Lead,
    to: S,
    *,
    reason: str,
    actor: Actor,
    actor_user_id: uuid.UUID | None = None,
    force: bool = False,
) -> None:
    """Change lead.status and write lead_status_history in the caller's session (no commit here).

    Raises InvalidTransition unless allowed; force=True is accepted only for actor="user".
    """
    current = S(lead.status)
    if current == to:
        return
    if not is_allowed(current, to) and not (force and actor == "user"):
        raise InvalidTransition(current, to)
    lead.status = to.value
    session.add(
        LeadStatusHistory(
            tenant_id=lead.tenant_id,
            lead_id=lead.id,
            from_status=current.value,
            to_status=to.value,
            reason=reason,
            actor=actor,
            actor_user_id=actor_user_id,
        )
    )
    await session.flush()
