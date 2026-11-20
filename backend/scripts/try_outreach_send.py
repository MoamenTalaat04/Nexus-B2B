"""P3-3 self-check with REAL WhatsApp sending: outreach tick → approve → send, to the team's test phones only.

    cd backend
    USE_MOCK_ADAPTERS=false uv run python -m scripts.try_outreach_send          # 3 fictional leads
    USE_MOCK_ADAPTERS=false uv run python -m scripts.try_outreach_send --cleanup  # delete the demo tenant

Needs in the private .env (never committed): USE_MOCK_LLM=false + LLM_*, ENCRYPTION_KEY,
WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_WABA_ID (or pass --phone-id/--waba-id), and
DEMO_TEST_PHONES (comma-separated, each one also on Meta's API Setup "To" list). Templates `intro` and
`followup` must be approved.

Creates one demo tenant ("WA send check (demo)") with demo_mode ON, so every message is redirected to a test
phone (CONTRACTS section 12) and never reaches the fictional leads' numbers. The tenant is kept so replies
sent to the webhook can be attributed (demo_routes); run with --cleanup to remove it.
"""

import asyncio
import json
import os
import sys
import uuid
from datetime import UTC, datetime, time
from pathlib import Path

from sqlalchemy import delete, select

from app.api.channels import sync_templates
from app.config import settings as app_settings
from app.core import lead_state
from app.core.crypto import encrypt_json
from app.db import SessionLocal
from app.models.enums import ChannelType, ContactType, LeadStatus, MessageStatus
from app.models.leads import Contact, Lead
from app.models.messaging import ChannelConnection, Message
from app.models.tenants import BusinessSettings, Tenant, User
from app.schemas.agent_io import ICP, CompanyProfile
from app.services import icp_service, messaging, outreach

TENANT_NAME = "WA send check (demo)"
ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_ICP = ROOT / "docs" / "examples" / "icp-demo-gemini.json"
LEADS = [  # fictional shops; their numbers are never messaged (demo mode redirects to the test phones)
    ("محل بيبي لاند (تجريبي)", "Nasr City", "+201000009101"),
    ("كيدز ستايل (تجريبي)", "Heliopolis", "+201000009102"),
    ("عالم الصغار (تجريبي)", "Dokki", "+201000009103"),
]


def private_env() -> dict[str, str]:
    """Values only this script needs, read from the repo-root .env (not app settings)."""
    out: dict[str, str] = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            out[key.strip()] = value.strip()
    out.update({k: v for k, v in os.environ.items() if k.startswith(("WHATSAPP_", "DEMO_"))})
    return out


def arg(name: str) -> str | None:
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else None


async def cleanup() -> None:
    async with SessionLocal() as session:
        ids = list((await session.execute(select(Tenant.id).where(Tenant.name == TENANT_NAME))).scalars())
        await session.execute(delete(Tenant).where(Tenant.id.in_(ids)))
        await session.commit()
    print(f"deleted {len(ids)} demo tenant(s)")


async def main() -> int:
    if "--cleanup" in sys.argv:
        await cleanup()
        return 0
    env = private_env()
    phones = [p.strip() for p in env.get("DEMO_TEST_PHONES", "").split(",") if p.strip()]
    phone_id = arg("--phone-id") or env.get("WHATSAPP_PHONE_NUMBER_ID")
    waba_id = arg("--waba-id") or env.get("WHATSAPP_WABA_ID")
    token = env.get("WHATSAPP_ACCESS_TOKEN")
    missing = [
        n
        for n, v in [
            ("DEMO_TEST_PHONES", phones),
            ("WHATSAPP_PHONE_NUMBER_ID", phone_id),
            ("WHATSAPP_WABA_ID", waba_id),
            ("WHATSAPP_ACCESS_TOKEN", token),
        ]
        if not v
    ]
    if missing or app_settings.USE_MOCK_ADAPTERS or app_settings.USE_MOCK_LLM:
        mocks = (app_settings.USE_MOCK_ADAPTERS, app_settings.USE_MOCK_LLM)
        print("missing:", missing or "-", "| mocks on (adapters, llm):", mocks)
        print("run with USE_MOCK_ADAPTERS=false and USE_MOCK_LLM=false, and fill the values above")
        return 1
    await cleanup()  # one demo tenant at a time (a phone number id belongs to one tenant)
    now = datetime.now(UTC)

    async with SessionLocal() as session:
        tenant = Tenant(name=TENANT_NAME)
        session.add(tenant)
        await session.flush()
        user = User(
            tenant_id=tenant.id,
            email=f"wa-check-{uuid.uuid4().hex[:8]}@example.com",
            password_hash="x",
            full_name="Demo owner",
        )
        session.add(user)
        session.add(
            BusinessSettings(
                tenant_id=tenant.id,
                company_name="مصنع نور لملابس الأطفال (شركة تجريبية)",
                description="مصنع ملابس أطفال في شبرا الخيمة، بيبيع جملة للمحلات.",
                first_touch_mode="api_template",
                autonomy_mode="approve_first_touch",
                agent_enabled=True,
                demo_mode=True,
                demo_whitelist=phones,
                quiet_hours_start=time(0, 0),  # test only: any hour, any day
                quiet_hours_end=time(23, 59),
                working_days=[0, 1, 2, 3, 4, 5, 6],
                onboarding_completed=True,
            )
        )
        example = json.loads(EXAMPLE_ICP.read_text(encoding="utf-8"))
        await icp_service.save_version(
            session,
            tenant.id,
            CompanyProfile.model_validate(example["company_profile"]),
            ICP.model_validate(example["icp"]),
            "user",
            notes="P3-3 send check (docs/examples)",
        )
        # connect WhatsApp the way PUT /channels/whatsapp does, then sync templates from Meta
        session.add(
            ChannelConnection(
                tenant_id=tenant.id,
                channel=ChannelType.WHATSAPP.value,
                status="connected",
                config={"phone_number_id": phone_id, "waba_id": waba_id},
                secrets_encrypted=encrypt_json({"access_token": token}),
                last_checked_at=now,
            )
        )
        await session.flush()
        templates = await sync_templates(session, tenant.id)
        print("templates:", ", ".join(f"{t.name}={t.status}/{t.purpose or '-'}" for t in templates))

        for name, city, phone in LEADS:
            lead = Lead(
                tenant_id=tenant.id,
                source="manual",
                name=name,
                category="Children's clothing store",
                city=city,
                governorate="Giza" if city == "Dokki" else "Cairo",
                score=8,
                score_reasons=["demo lead"],
            )
            session.add(lead)
            await session.flush()
            await lead_state.transition(session, lead, LeadStatus.QUALIFIED, reason="demo", actor="agent")
            session.add(
                Contact(
                    tenant_id=tenant.id,
                    lead_id=lead.id,
                    type=ContactType.MOBILE.value,
                    value=phone,
                    source="manual",
                    is_primary=True,
                    confidence=1.0,
                )
            )
            await lead_state.transition(session, lead, LeadStatus.ENRICHED, reason="demo", actor="agent")
        await session.commit()
        tenant_id, user_id = tenant.id, user.id

    # the tick: personalizes each first touch with the real model; approve_first_touch → pending approval
    async with SessionLocal() as session:
        bs = (
            await session.execute(select(BusinessSettings).where(BusinessSettings.tenant_id == tenant_id))
        ).scalar_one()
        tick = await outreach.tick_tenant(session, bs, now=now)
        print(f"tick: created={tick.created} skipped={dict(tick.skipped)} reason={tick.reason}")

    async def no_queue(*args: object, **kwargs: object) -> None:  # we send right here instead of the worker
        return None

    messaging.enqueue_send = no_queue
    async with SessionLocal() as session:
        pending = list(
            (
                await session.execute(
                    select(Message).where(
                        Message.tenant_id == tenant_id, Message.status == MessageStatus.PENDING_APPROVAL.value
                    )
                )
            ).scalars()
        )
        ids = [m.id for m in pending]
        for m in pending:
            await messaging.approve_message(session, tenant_id=tenant_id, message_id=m.id, user_id=user_id)
        await session.commit()

    for message_id in ids:
        async with SessionLocal() as session:
            outcome = await messaging.send_message_in(session, message_id)
            sent = await session.get(Message, message_id)
            assert sent is not None
            sent_lead = await session.get(Lead, sent.lead_id)
            assert sent_lead is not None
            print(
                f"\n{sent_lead.name}: send={outcome.status} message={sent.status} error={sent.error or '-'} "
                f"to={messaging.mask(sent.redirected_to)} lead_status={sent_lead.status}"
            )
            print("  ", sent.body)
    print(f"\ndemo tenant kept for replies: {tenant_id}  (remove with --cleanup)")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(asyncio.run(main()))
