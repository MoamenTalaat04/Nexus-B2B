"""P4-4: the demo seed builds a believable account and is idempotent."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as app_settings
from app.core.phones import is_eg_mobile
from app.models.enums import MessageStatus
from app.models.leads import Contact, Lead, LeadOutcome
from app.models.messaging import Message
from app.models.notifications import LearnedInsight
from app.models.runs import AgentRun
from app.models.tenants import BusinessSettings, User
from scripts import seed_demo


@pytest.fixture
def seeded_session(session: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> AsyncSession:
    @asynccontextmanager
    async def test_session() -> AsyncIterator[AsyncSession]:
        yield session

    monkeypatch.setattr(seed_demo, "SessionLocal", test_session)
    monkeypatch.setattr(app_settings, "UPLOAD_DIR", str(tmp_path))
    return session


async def count(session: AsyncSession, model: type, *where: object) -> int:
    return int(await session.scalar(select(func.count()).select_from(model).where(*where)) or 0)  # type: ignore[arg-type]


async def test_seed_creates_the_demo_account(
    seeded_session: AsyncSession, capsys: pytest.CaptureFixture[str]
) -> None:
    session = seeded_session
    await seed_demo.seed(password="demo-pass-123", whitelist=["+201000009001"])
    out = capsys.readouterr().out
    assert "demo@example.com" in out and "demo-pass-123" in out

    user = (await session.execute(select(User).where(User.email == seed_demo.DEMO_EMAIL))).scalar_one()
    tid = user.tenant_id
    settings = (
        await session.execute(select(BusinessSettings).where(BusinessSettings.tenant_id == tid))
    ).scalar_one()
    assert settings.first_touch_mode == "api_template" and settings.demo_mode is True
    assert settings.onboarding_completed is True

    assert await count(session, Lead, Lead.tenant_id == tid) == 80
    statuses = set((await session.execute(select(Lead.status).where(Lead.tenant_id == tid))).scalars())
    assert len(statuses) == 17  # the whole funnel
    assert await count(session, LeadOutcome, LeadOutcome.tenant_id == tid, LeadOutcome.outcome == "won") == 6
    assert await count(session, LeadOutcome, LeadOutcome.tenant_id == tid, LeadOutcome.outcome == "lost") == 4
    assert (
        await count(
            session,
            Message,
            Message.tenant_id == tid,
            Message.status == MessageStatus.AWAITING_MANUAL_SEND.value,
        )
        == 5
    )
    intents = set(
        (
            await session.execute(
                select(Message.reply_intent).where(
                    Message.tenant_id == tid, Message.reply_intent.is_not(None)
                )
            )
        ).scalars()
    )
    assert len(intents) == 9  # every ReplyIntent appears in a conversation
    inbound_leads = await session.scalar(
        select(func.count(func.distinct(Message.lead_id))).where(
            Message.tenant_id == tid, Message.direction == "inbound"
        )
    )
    assert int(inbound_leads or 0) >= 25
    phones = (await session.execute(select(Contact.value).where(Contact.tenant_id == tid))).scalars().all()
    assert phones and all(p.startswith("+20100000") and is_eg_mobile(p) for p in phones)  # fake range only
    runs = (
        (await session.execute(select(AgentRun.created_at).where(AgentRun.tenant_id == tid))).scalars().all()
    )
    assert len(runs) > 40 and (max(runs) - min(runs)).days >= 14
    insight = (
        await session.execute(select(LearnedInsight).where(LearnedInsight.tenant_id == tid))
    ).scalar_one()
    assert insight.is_active and insight.stats["computed"]["outcomes"] == 10


async def test_seed_is_idempotent_and_reset_recreates(
    seeded_session: AsyncSession, capsys: pytest.CaptureFixture[str]
) -> None:
    session = seeded_session
    await seed_demo.seed(password="p1-xxxxxx", whitelist=[])
    await seed_demo.seed(password="p2-xxxxxx", whitelist=[])
    assert "already exists" in capsys.readouterr().out
    assert await count(session, User, User.email == seed_demo.DEMO_EMAIL) == 1
    await seed_demo.reset(session)
    assert await count(session, User, User.email == seed_demo.DEMO_EMAIL) == 0
    await seed_demo.seed(password="p3-xxxxxx", whitelist=[])
    assert await count(session, User, User.email == seed_demo.DEMO_EMAIL) == 1


def test_whitelist_parsing() -> None:
    assert seed_demo.parse_whitelist(None) == seed_demo.DEFAULT_WHITELIST
    assert seed_demo.parse_whitelist("010 0000 9001, +201000009002") == ["+201000009001", "+201000009002"]
