"""P0-2: the lead state machine (CONTRACTS section 4), table-driven over every pair of statuses."""

import itertools
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import lead_state
from app.core.lead_state import ALLOWED, InvalidTransition, is_allowed, transition
from app.models.enums import LeadStatus as S
from app.models.leads import Lead, LeadStatusHistory
from app.models.tenants import Tenant

# The contract's table, written out again on purpose: an accidental edit of ALLOWED fails this test.
EXPECTED: dict[S, set[S]] = {
    S.NEW: {S.QUALIFIED, S.DISQUALIFIED},
    S.QUALIFIED: {S.ENRICHED, S.NO_CONTACT, S.DISQUALIFIED},
    S.DISQUALIFIED: set(),
    S.NO_CONTACT: {S.ENRICHED},
    S.ENRICHED: {S.QUEUED},
    S.QUEUED: {S.CONTACTED, S.ENRICHED},
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


def expected_allowed(src: S, dst: S) -> bool:
    if dst == S.OPTED_OUT:
        return src not in TERMINAL
    return dst in EXPECTED[src]


def test_table_matches_contract() -> None:
    assert set(ALLOWED) == set(S), "every status needs a row"
    assert ALLOWED == EXPECTED


@pytest.mark.parametrize(("src", "dst"), [(a, b) for a, b in itertools.product(S, S) if a != b])
def test_is_allowed_every_pair(src: S, dst: S) -> None:
    assert is_allowed(src, dst) is expected_allowed(src, dst)


def test_classified_statuses_can_go_back_to_replied() -> None:
    for status in (S.INTERESTED, S.WANTS_OFFER, S.WANTS_MANAGEMENT, S.LATER, S.NOT_INTERESTED, S.LOST):
        assert is_allowed(status, S.REPLIED), status


def test_opted_out_is_terminal() -> None:
    for dst in S:
        if dst != S.OPTED_OUT:
            assert not is_allowed(S.OPTED_OUT, dst)
    for src in S:
        if src not in TERMINAL:
            assert is_allowed(src, S.OPTED_OUT)


async def _lead(session: AsyncSession, status: S) -> Lead:
    tenant = Tenant(name="State test")
    session.add(tenant)
    await session.flush()
    lead = Lead(tenant_id=tenant.id, name="محل تجربة", status=status.value, dedupe_key=str(uuid.uuid4()))
    session.add(lead)
    await session.flush()
    return lead


async def _history(session: AsyncSession, lead: Lead) -> list[LeadStatusHistory]:
    rows = await session.execute(
        select(LeadStatusHistory)
        .where(LeadStatusHistory.lead_id == lead.id)
        .order_by(LeadStatusHistory.created_at)
    )
    return list(rows.scalars())


async def test_transition_writes_history(session: AsyncSession) -> None:
    lead = await _lead(session, S.NEW)
    await transition(session, lead, S.QUALIFIED, reason="score 8", actor="agent")
    assert lead.status == S.QUALIFIED.value
    [row] = await _history(session, lead)
    assert (row.from_status, row.to_status, row.reason, row.actor) == ("new", "qualified", "score 8", "agent")
    assert row.tenant_id == lead.tenant_id


async def test_transition_to_same_status_is_a_no_op(session: AsyncSession) -> None:
    lead = await _lead(session, S.CONTACTED)
    await transition(session, lead, S.CONTACTED, reason="again", actor="system")
    assert await _history(session, lead) == []


async def test_forbidden_transition_raises_and_writes_nothing(session: AsyncSession) -> None:
    lead = await _lead(session, S.NEW)
    with pytest.raises(InvalidTransition):
        await transition(session, lead, S.CONTACTED, reason="skip ahead", actor="agent")
    assert lead.status == S.NEW.value
    assert await _history(session, lead) == []


async def test_force_only_for_users(session: AsyncSession) -> None:
    lead = await _lead(session, S.WON)
    with pytest.raises(InvalidTransition):
        await transition(session, lead, S.REPLIED, reason="x", actor="agent", force=True)
    with pytest.raises(InvalidTransition):
        await transition(session, lead, S.REPLIED, reason="x", actor="system", force=True)
    user_id = uuid.uuid4()
    await transition(
        session, lead, S.LOST, reason="owner fixed it", actor="user", actor_user_id=user_id, force=True
    )
    assert lead.status == S.LOST.value
    [row] = await _history(session, lead)
    assert row.actor_user_id == user_id


async def test_opt_out_from_anywhere_non_terminal(session: AsyncSession) -> None:
    lead = await _lead(session, S.CONTACTED)
    await transition(session, lead, S.OPTED_OUT, reason="stop", actor="system")
    with pytest.raises(InvalidTransition):
        await transition(session, lead, S.REPLIED, reason="new inbound", actor="system")
    assert lead_state.TERMINAL == TERMINAL
