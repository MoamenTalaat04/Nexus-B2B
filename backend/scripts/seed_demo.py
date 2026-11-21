# ruff: noqa: E501  (demo data: long Arabic strings)
"""Demo tenant + data (P4-4): `uv run poe seed-demo` (idempotent) or `uv run poe seed-demo --reset`.

Creates "Little Stars Kids Wear" (a fictional kids-clothing factory in 10th of Ramadan) with an owner login
demo@example.com (password printed once), full settings in api_template mode (the live demo shows the whole
automatic loop on the team phones), a knowledge file, an active ICP, ~80 fictional leads across Cairo/Giza spread
over the whole funnel, conversations in Egyptian Arabic for ~25 of them (every reply intent), 6 won + 4 lost
outcomes, 5 assisted messages waiting in /outreach → "To send", agent runs with steps/tokens/costs over the last
21 days, and one learned-insights version.

Only fictional names and fake +20 numbers in the 0100000xxxx range — never real businesses or numbers.

Options:
  --reset                  delete the demo tenant first (everything cascades) and seed again
  --password PW            the owner's password (default: a random one, printed)
  --whitelist +2010…,+2011…  the team's WhatsApp test phones for demo mode (or env DEMO_WHITELIST)
"""

import argparse
import asyncio
import importlib
import os
import random
import secrets
import uuid
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from argon2 import PasswordHasher
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as app_settings
from app.core.phones import normalize_eg_phone
from app.db import SessionLocal
from app.models.enums import (
    AgentRunKind,
    AgentRunStatus,
    ContactType,
    LeadStatus,
    MessageAuthor,
    MessageDirection,
    MessageKind,
    MessageStatus,
    OutreachPurpose,
    ReplyIntent,
    StepType,
)
from app.models.leads import Contact, Lead, LeadNote, LeadOutcome, LeadStatusHistory
from app.models.messaging import Conversation, Message, MessageTemplate
from app.models.notifications import Notification
from app.models.runs import AgentRun, AgentStep
from app.models.tenants import BusinessSettings, Tenant, User
from app.schemas.agent_io import FAQ, ICP, CompanyProfile, Product, RegionTarget
from app.services import icp_service, insights

DEMO_EMAIL = "demo@example.com"
DEMO_TENANT = "Little Stars Kids Wear"
DEFAULT_WHITELIST = ["+201000009001", "+201000009002"]
PROFILE_MD = Path(__file__).parent / "demo_data" / "little_stars_profile.md"
DAYS = 21

rng = random.Random(2026)
NOW = datetime.now(UTC).replace(microsecond=0)

# ---------------------------------------------------------------------------------------------- fictional data

SHOP_CORES = [
    "بيبي لاند",
    "كيدز زون",
    "ليتل برنس",
    "بامبينو",
    "جونيور",
    "توتي فروتي",
    "سمارت كيدز",
    "ماما وبيبي",
    "الأمل لملابس الأطفال",
    "النور كيدز",
    "ورد البنات",
    "فرحة",
    "بيبي ستار",
    "ميني مي",
    "كوكي كيدز",
    "سنو وايت",
    "بلو بيرد",
    "هابي فيس",
    "ماي بيبي",
    "تيدي",
    "كاندي",
    "بنوتة",
    "شطورة",
    "الفراشة",
    "الملاك الصغير",
    "روزي",
    "بيتي",
    "كيوت",
    "ليلى للأطفال",
    "عالم الطفل",
    "دنيا البيبي",
    "ستايل كيدز",
    "توينز",
    "بيبي شيك",
    "زهرة",
    "ريماس",
    "تالين كيدز",
    "لولي",
    "بون بون",
    "أطفالنا",
]
CATEGORIES = ["Children's clothing store", "Baby store", "Clothing store", "Kids wear boutique"]
AREAS = [
    ("Cairo", "Nasr City"),
    ("Cairo", "Heliopolis"),
    ("Cairo", "Shubra"),
    ("Cairo", "Maadi"),
    ("Cairo", "Ain Shams"),
    ("Giza", "Faisal"),
    ("Giza", "Haram"),
    ("Giza", "Dokki"),
    ("Giza", "6th of October"),
]
# status → how many leads (80 in total), in funnel order
FUNNEL: list[tuple[LeadStatus, int]] = [
    (LeadStatus.NEW, 8),
    (LeadStatus.QUALIFIED, 6),
    (LeadStatus.DISQUALIFIED, 8),
    (LeadStatus.NO_CONTACT, 4),
    (LeadStatus.ENRICHED, 6),
    (LeadStatus.QUEUED, 8),
    (LeadStatus.CONTACTED, 11),
    (LeadStatus.REPLIED, 3),
    (LeadStatus.INTERESTED, 4),
    (LeadStatus.NOT_INTERESTED, 3),
    (LeadStatus.WANTS_OFFER, 3),
    (LeadStatus.WANTS_MANAGEMENT, 2),
    (LeadStatus.LATER, 2),
    (LeadStatus.WRONG_CONTACT, 1),
    (LeadStatus.OPTED_OUT, 1),
    (LeadStatus.WON, 6),
    (LeadStatus.LOST, 4),
]
CONTACTED_OR_LATER = {
    LeadStatus.CONTACTED,
    LeadStatus.REPLIED,
    LeadStatus.INTERESTED,
    LeadStatus.NOT_INTERESTED,
    LeadStatus.WANTS_OFFER,
    LeadStatus.WANTS_MANAGEMENT,
    LeadStatus.LATER,
    LeadStatus.WRONG_CONTACT,
    LeadStatus.OPTED_OUT,
    LeadStatus.WON,
    LeadStatus.LOST,
}
STATUS_INTENT = {
    LeadStatus.INTERESTED: ReplyIntent.INTERESTED,
    LeadStatus.NOT_INTERESTED: ReplyIntent.NOT_INTERESTED,
    LeadStatus.WANTS_OFFER: ReplyIntent.WANTS_OFFER,
    LeadStatus.WANTS_MANAGEMENT: ReplyIntent.WANTS_MANAGEMENT,
    LeadStatus.LATER: ReplyIntent.LATER,
    LeadStatus.WRONG_CONTACT: ReplyIntent.WRONG_CONTACT,
    LeadStatus.OPTED_OUT: ReplyIntent.OPTED_OUT,
    LeadStatus.WON: ReplyIntent.INTERESTED,
    LeadStatus.LOST: ReplyIntent.NOT_INTERESTED,
}
LEAD_REPLIES: dict[ReplyIntent, list[str]] = {
    ReplyIntent.INTERESTED: [
        "أهلاً بيكم، مهتمين جداً. ممكن تبعتولي الكتالوج والأسعار؟",
        "تمام، المحل محتاج بيجامات شتوي. ابعتلي الأسعار لو سمحت",
    ],
    ReplyIntent.WANTS_OFFER: [
        "لو في خصم على أول طلبية ممكن ناخد ٥ دستة",
        "ابعتلي عرض سعر لـ ٣ دستة أوفرولات و٢ دستة بيجامات",
    ],
    ReplyIntent.WANTS_MANAGEMENT: ["عايز أتكلم مع حد من الإدارة عندكم قبل ما نتفق على حاجة"],
    ReplyIntent.NOT_INTERESTED: ["شكراً، إحنا متعاملين مع مصنع تاني ومش محتاجين دلوقتي"],
    ReplyIntent.LATER: ["ابعتلي بعد العيد، دلوقتي المحل مليان بضاعة"],
    ReplyIntent.WRONG_CONTACT: ["الرقم ده مش بتاع المحل، حضرتك غلطان"],
    ReplyIntent.OPTED_OUT: ["متبعتليش رسايل تاني لو سمحت"],
    ReplyIntent.QUESTION: ["التوصيل للهرم بياخد كام يوم؟", "هو أقل طلب كام قطعة؟"],
    ReplyIntent.OTHER: ["👍", "مين معايا؟"],
}
AGENT_REPLIES: dict[ReplyIntent, str] = {
    ReplyIntent.INTERESTED: "أهلاً بحضرتك 🌟 بعتلك الكتالوج. البيجامات القطن من ١٤٥ لـ ٢١٠ جنيه للقطعة، وأقل طلب دستة "
    "من الموديل. تحب أحجزلك عينة؟",
    ReplyIntent.WANTS_OFFER: "أكيد! على أول طلبية في خصم لحد ١٠٪. هبعت لحضرتك عرض السعر النهارده، وحد من فريق المبيعات "
    "هيتواصل معاك.",
    ReplyIntent.WANTS_MANAGEMENT: "تمام، بلّغت مدير المبيعات وهيتواصل مع حضرتك في أقرب وقت.",
    ReplyIntent.QUESTION: "التوصيل للقاهرة والجيزة من ٣ لـ ٥ أيام عمل، وأقل طلب دستة من الموديل ومقاسات متنوعة.",
    ReplyIntent.LATER: "ولا يهمك، هفكّر حضرتك بعد العيد إن شاء الله 🙏",
    ReplyIntent.OTHER: "معاك المساعد الذكي بتاع مصنع ليتل ستارز لملابس الأطفال 😊 أقدر أساعد حضرتك إزاي؟",
}
WON_VALUES = [Decimal(v) for v in ("18500.00", "42000.00", "12600.00", "27300.00", "63800.00", "9900.00")]
LOST_REASONS = [
    "السعر أعلى من المورد الحالي",
    "عايزين بالأجل ٦٠ يوم",
    "مش بيبيعوا مقاسات بيبي",
    "مقفولين للتجديد",
]
INSIGHTS = [
    "Kids clothing shops in Nasr City and Heliopolis converted best (4 of 5 won) — score them higher.",
    "Leads with 50+ Google reviews won 5 of 7 times; leads under 10 reviews won 0 of 3 — favour established shops.",
    "Score band 7-8 won 5 of 6 (83%) while 4-6 won 1 of 4 (25%) — keep the qualification threshold at 7.",
    "Shops with a website won 3 of 4, but most winners had none — do not penalise a missing website.",
]
CAVEATS = ["Only 10 outcomes so far (6 won, 4 lost); treat these as early signals."]


def fake_phone(i: int) -> str:
    return f"+20100000{i:04d}"  # 0100000xxxx — never a real number


def ago(days: float, hours: float = 0) -> datetime:
    return NOW - timedelta(days=days, hours=hours)


def clamp(when: datetime) -> datetime:
    """Never in the future (recent demo leads get their replies and outcomes "just now")."""
    return min(when, NOW - timedelta(minutes=5))


def model_name(fast: bool) -> str:
    configured = app_settings.LLM_MODEL_FAST if fast else app_settings.LLM_MODEL_SMART
    return configured or ("demo-fast-model" if fast else "demo-smart-model")


# ---------------------------------------------------------------------------------------------- seeding


def build_profile() -> CompanyProfile:
    return CompanyProfile(
        company_name="ليتل ستارز لملابس الأطفال",
        one_liner="مصنع ملابس أطفال في العاشر من رمضان بيبيع جملة لمحلات الأطفال في القاهرة والجيزة",
        products=[
            Product(
                name="بيجامات قطن",
                description="قطعتين، قطن ١٠٠٪",
                price_range="145-210 EGP",
                min_order="1 dozen",
            ),
            Product(
                name="أوفرولات بيبي", description="0-24 شهر", price_range="95-140 EGP", min_order="1 dozen"
            ),
            Product(
                name="تيشيرتات أطفال", description="مطبوعة", price_range="70-110 EGP", min_order="2 dozen"
            ),
            Product(
                name="فساتين مناسبات",
                description="للبنات",
                price_range="320-480 EGP",
                min_order="half a dozen",
            ),
        ],
        differentiators=[
            "أسعار المصنع من غير وسيط",
            "قطن مصري",
            "أقل طلب صغير ومقاسات متنوعة",
            "تبديل خلال ١٤ يوم",
        ],
        target_customer_summary="محلات ملابس الأطفال ومحلات البيبي في القاهرة والجيزة",
        allowed_offers="خصم لحد ١٠٪ على أول طلبية، وتوصيل مجاني فوق ٥٠ ألف جنيه",
        max_discount_percent=10,
        faqs=[
            FAQ(q="بتبيعوا قطاعي؟", a="لا، جملة بس."),
            FAQ(q="التوصيل بياخد قد إيه؟", a="القاهرة والجيزة من ٣ لـ ٥ أيام عمل."),
        ],
        tone="friendly",
        language="ar-EG",
    )


def build_icp() -> ICP:
    return ICP(
        summary="Independent kids-clothing shops and baby stores in Cairo and Giza that buy wholesale.",
        target_business_types=["kids clothing store", "محل ملابس اطفال", "baby store", "محل مستلزمات بيبي"],
        include_keywords=["ملابس اطفال", "بيبي", "kids wear", "ولادي وبناتي"],
        exclude_keywords=["جملة", "مصنع", "wholesale"],
        google_place_types=["clothing_store", "baby_store"],
        regions=[
            RegionTarget(
                governorate="Cairo", cities=["Nasr City", "Heliopolis", "Shubra", "Maadi", "Ain Shams"]
            ),
            RegionTarget(governorate="Giza", cities=[]),
        ],
        business_size="small",
        must_have=["sells children's clothing", "a physical shop"],
        nice_to_have=["50+ Google reviews", "two or more branches"],
        disqualifiers=["other factories or wholesalers", "second-hand clothes"],
        value_proposition="Factory prices, small minimum orders and fast re-stocking.",
        pain_points=["high wholesale prices", "large minimum orders", "slow re-stocking of best sellers"],
        outreach_angle="Introduce the new season collection with a first-order discount.",
        language="ar-EG",
    )


async def reset(session: AsyncSession) -> None:
    user = (await session.execute(select(User).where(User.email == DEMO_EMAIL))).scalar_one_or_none()
    tenant_ids = {user.tenant_id} if user else set()
    tenant_ids |= set((await session.execute(select(Tenant.id).where(Tenant.name == DEMO_TENANT))).scalars())
    for tid in tenant_ids:
        await session.execute(delete(Tenant).where(Tenant.id == tid))  # every tenant table cascades
    await session.commit()
    if tenant_ids:
        print(f"seed-demo: deleted {len(tenant_ids)} demo tenant(s)")


async def _save_knowledge(session: AsyncSession, tenant_id: uuid.UUID) -> str:
    text = PROFILE_MD.read_text(encoding="utf-8")
    folder = Path(app_settings.UPLOAD_DIR) / str(tenant_id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / PROFILE_MD.name
    path.write_text(text, encoding="utf-8")
    try:  # P1-1's table, when it is on main
        model = importlib.import_module("app.models.knowledge").KnowledgeFile
    except (ModuleNotFoundError, AttributeError):
        return f"{path} (knowledge_files table not available yet — upload it in the app)"
    session.add(
        model(
            tenant_id=tenant_id,
            filename=PROFILE_MD.name,
            mime_type="text/markdown",
            size_bytes=len(text.encode()),
            storage_path=str(path),
            extracted_text=text,
            char_count=len(text),
            status="ready",
        )
    )
    return str(path)


async def _runs(session: AsyncSession, tenant_id: uuid.UUID) -> dict[int, uuid.UUID]:
    """Agent runs with steps over the last 21 days; returns {day: sourcing_run_id}."""
    sourcing: dict[int, uuid.UUID] = {}
    plan = [
        (AgentRunKind.SOURCING, "schedule", 1),
        (AgentRunKind.SCORING, "chained", 1),
        (AgentRunKind.ENRICHMENT, "chained", 1),
        (AgentRunKind.OUTREACH_TICK, "schedule", 2),
        (AgentRunKind.REPLY, "webhook", 2),
    ]
    for day in range(DAYS, 0, -1):
        if (NOW - timedelta(days=day)).weekday() == 4:  # Friday: not a working day
            continue
        for kind, trigger, count in plan:
            for n in range(count):
                start = ago(day).replace(hour=7, minute=0, second=0) + timedelta(
                    minutes=37 * n + 11 * len(sourcing)
                )
                failed = kind == AgentRunKind.REPLY and day == 9 and n == 1
                run = AgentRun(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    kind=kind.value,
                    trigger=trigger,
                    status=(AgentRunStatus.FAILED if failed else AgentRunStatus.SUCCEEDED).value,
                    input={"demo": True},
                    created_at=start,
                    started_at=start,
                    finished_at=start + timedelta(seconds=rng.randint(4, 90)),
                    error="LLMOutputTruncated: the answer was cut off" if failed else None,
                )
                steps = _steps_for(kind, failed)
                run.total_input_tokens = sum(s["input_tokens"] for s in steps)
                run.total_output_tokens = sum(s["output_tokens"] for s in steps)
                run.total_cost_usd = Decimal(str(round(sum(s["cost_usd"] for s in steps), 6)))
                run.output_summary = {"demo": True, "steps": len(steps)}
                session.add(run)
                await session.flush()
                for seq, step in enumerate(steps, 1):
                    session.add(
                        AgentStep(
                            tenant_id=tenant_id,
                            run_id=run.id,
                            seq=seq,
                            created_at=start + timedelta(seconds=seq * 3),
                            **step,
                        )
                    )
                if kind == AgentRunKind.SOURCING:
                    sourcing[day] = run.id
    await session.flush()
    return sourcing


def _llm_step(name: str, fast: bool) -> dict[str, Any]:
    tokens_in, tokens_out = rng.randint(1800, 9000), rng.randint(200, 1500)
    price_in, price_out = (0.10, 0.40) if fast else (1.25, 10.0)  # USD per 1M tokens (estimated, demo)
    return {
        "step_type": StepType.LLM_CALL.value,
        "name": name,
        "input": {"demo": True},
        "output": {"demo": True},
        "model": model_name(fast),
        "input_tokens": tokens_in,
        "output_tokens": tokens_out,
        "cache_read_tokens": rng.randint(0, tokens_in // 2),
        "cost_usd": Decimal(str(round((tokens_in * price_in + tokens_out * price_out) / 1_000_000, 6))),
        "latency_ms": rng.randint(800, 9000),
    }


def _plain_step(step_type: StepType, name: str, output: dict[str, Any]) -> dict[str, Any]:
    return {
        "step_type": step_type.value,
        "name": name,
        "input": None,
        "output": output,
        "model": None,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cost_usd": Decimal("0"),
        "latency_ms": rng.randint(50, 1200),
    }


def _steps_for(kind: AgentRunKind, failed: bool) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]]
    if kind == AgentRunKind.SOURCING:
        steps = [_llm_step("query_generator.plan", True)]
        steps += [
            _plain_step(StepType.EXTERNAL_API, "google_places.search", {"results": 20, "requests": 1})
        ] * 3
        steps.append(_plain_step(StepType.DECISION, "sourcing.totals", {"created": rng.randint(3, 8)}))
    elif kind == AgentRunKind.SCORING:
        steps = [
            _llm_step("lead_scorer.batch", True),
            _plain_step(StepType.DECISION, "threshold", {"qualified": 4}),
        ]
    elif kind == AgentRunKind.ENRICHMENT:
        steps = [_plain_step(StepType.EXTERNAL_API, "website_crawler.fetch", {"pages": 3})]
    elif kind == AgentRunKind.OUTREACH_TICK:
        steps = [
            _llm_step("message_personalizer.opening", True),
            _plain_step(StepType.EXTERNAL_API, "whatsapp.send", {"ok": True}),
        ]
    else:
        steps = [_llm_step("reply_classifier.classify", True), _llm_step("reply_agent.turn", False)]
    if failed:
        steps.append(_plain_step(StepType.ERROR, "LLMOutputTruncated", {"error": "the answer was cut off"}))
    return steps


async def seed(*, password: str, whitelist: list[str]) -> None:
    async with SessionLocal() as session:
        existing = (await session.execute(select(User).where(User.email == DEMO_EMAIL))).scalar_one_or_none()
        if existing is not None:
            print(
                "seed-demo: the demo account already exists (demo@example.com). Use --reset to recreate it."
            )
            return

        tenant = Tenant(name=DEMO_TENANT)
        session.add(tenant)
        await session.flush()
        tid = tenant.id
        session.add(
            User(
                tenant_id=tid,
                email=DEMO_EMAIL,
                password_hash=PasswordHasher().hash(password),
                full_name="Ahmed (demo owner)",
                role="owner",
            )
        )
        profile, icp = build_profile(), build_icp()
        session.add(
            BusinessSettings(
                tenant_id=tid,
                company_name=DEMO_TENANT,
                website="https://littlestars.example",
                description="مصنع ملابس أطفال في العاشر من رمضان، بنبيع جملة لمحلات الأطفال في القاهرة والجيزة.",
                ideal_customer_text="محلات ملابس الأطفال ومحلات البيبي في القاهرة والجيزة، خصوصاً مدينة نصر "
                "ومصر الجديدة وفيصل والهرم.",
                products=[p.model_dump() for p in profile.products],
                target_regions=[r.model_dump() for r in icp.regions],
                language="ar-EG",
                tone="friendly",
                allowed_offers=profile.allowed_offers,
                max_discount_percent=10,
                autonomy_mode="approve_first_touch",
                first_touch_mode="api_template",
                agent_enabled=True,
                daily_new_leads_target=30,
                daily_send_cap=20,
                quiet_hours_start=time(10, 0),
                quiet_hours_end=time(20, 0),
                working_days=[0, 1, 2, 3, 5, 6],
                score_threshold=6,
                demo_mode=True,
                demo_whitelist=whitelist,
                onboarding_completed=True,
            )
        )
        session.add_all(
            [
                MessageTemplate(
                    tenant_id=tid,
                    name="intro",
                    language="ar",
                    category="MARKETING",
                    purpose="intro",
                    body_text="أهلاً {{1}} 👋 معاك {{2}}. حابين نعرّفكم على تشكيلتنا الجديدة لملابس الأطفال.",
                    param_count=2,
                    status="approved",
                ),
                MessageTemplate(
                    tenant_id=tid,
                    name="followup",
                    language="ar",
                    category="MARKETING",
                    purpose="followup",
                    body_text="أهلاً تاني {{1}}، لسه مستنيين ردكم على التشكيلة الجديدة.",
                    param_count=1,
                    status="approved",
                ),
            ]
        )
        await session.flush()
        knowledge_where = await _save_knowledge(session, tid)
        icp_version = await icp_service.save_version(
            session, tid, profile, icp, source="agent", notes="Seeded for the demo"
        )
        active_icp = await icp_service.get_active_icp(session, tid)
        sourcing_runs = await _runs(session, tid)
        run_days = sorted(sourcing_runs)

        counts = {"leads": 0, "conversations": 0, "messages": 0}
        index = 0
        won_i = lost_i = 0
        question_cycle = [ReplyIntent.QUESTION, ReplyIntent.OTHER, ReplyIntent.QUESTION]
        for status, how_many in FUNNEL:
            for k in range(how_many):
                index += 1
                governorate, city = AREAS[index % len(AREAS)]
                day = run_days[index % len(run_days)] if run_days else 1
                created = ago(day, hours=-1)
                strong = status in (LeadStatus.WON, LeadStatus.INTERESTED, LeadStatus.WANTS_OFFER)
                score = (
                    None
                    if status == LeadStatus.NEW
                    else (
                        rng.randint(1, 3)
                        if status == LeadStatus.DISQUALIFIED
                        else rng.randint(7, 9)
                        if strong
                        else rng.randint(5, 8)
                    )
                )
                core = SHOP_CORES[index % len(SHOP_CORES)]
                name = core if index <= len(SHOP_CORES) else f"{core} - فرع {city}"
                lead = Lead(
                    tenant_id=tid,
                    source="google_places",
                    source_ref=f"demo-place-{index:03d}",
                    name=name,
                    category=CATEGORIES[index % len(CATEGORIES)],
                    address=f"شارع {rng.randint(1, 90)}، {city}",
                    city=city,
                    governorate=governorate,
                    lat=30.0 + rng.random() / 10,
                    lng=31.2 + rng.random() / 10,
                    website=f"https://shop-{index:03d}.example" if index % 4 == 0 else None,
                    google_maps_url=f"https://maps.google.com/?cid=demo{index:03d}",
                    rating=round(rng.uniform(4.3, 4.9) if strong else rng.uniform(3.4, 4.6), 1),
                    reviews_count=rng.randint(60, 400) if strong else rng.randint(2, 120),
                    raw={"demo": True},
                    status=status.value,
                    score=score,
                    score_reasons=(
                        ["محل ملابس أطفال في منطقة مستهدفة", f"{rng.randint(40, 300)} تقييم على جوجل"]
                        if score
                        else []
                    ),
                    disqualify_reason="مصنع منافس / بيبيع جملة"
                    if status == LeadStatus.DISQUALIFIED
                    else None,
                    icp_version_id=active_icp.id if active_icp else None,
                    sourcing_run_id=sourcing_runs.get(day),
                    sequence_step=1 if status in CONTACTED_OR_LATER else 0,
                    next_action_at=ago(-3) if status == LeadStatus.CONTACTED else None,
                    agent_paused=status in (LeadStatus.INTERESTED, LeadStatus.WANTS_MANAGEMENT),
                    dedupe_key=f"google_places:demo-place-{index:03d}",
                    created_at=created,
                )
                session.add(lead)
                await session.flush()
                counts["leads"] += 1
                session.add(
                    LeadStatusHistory(
                        tenant_id=tid,
                        lead_id=lead.id,
                        from_status=None,
                        to_status=status.value,
                        reason="demo seed",
                        actor="system",
                        created_at=created,
                    )
                )
                if status not in (
                    LeadStatus.NEW,
                    LeadStatus.QUALIFIED,
                    LeadStatus.DISQUALIFIED,
                    LeadStatus.NO_CONTACT,
                ):
                    session.add(
                        Contact(
                            tenant_id=tid,
                            lead_id=lead.id,
                            type=ContactType.MOBILE.value,
                            value=fake_phone(index),
                            source="google_places",
                            is_primary=True,
                            confidence=0.9,
                        )
                    )
                await session.flush()

                # queued: 5 assisted "To send" + 3 waiting for approval
                if status == LeadStatus.QUEUED:
                    conv = Conversation(
                        tenant_id=tid, lead_id=lead.id, channel="whatsapp", contact_value=fake_phone(index)
                    )
                    session.add(conv)
                    await session.flush()
                    assisted = k < 5
                    session.add(
                        Message(
                            tenant_id=tid,
                            conversation_id=conv.id,
                            lead_id=lead.id,
                            direction=MessageDirection.OUTBOUND.value,
                            channel="whatsapp",
                            author=MessageAuthor.AGENT.value,
                            kind=(MessageKind.ASSISTED if assisted else MessageKind.TEMPLATE).value,
                            purpose=OutreachPurpose.FIRST_TOUCH.value,
                            template_name=None if assisted else "intro",
                            template_params=None if assisted else [lead.name[:40], "ليتل ستارز"],
                            body=(
                                f"أهلاً {lead.name} 👋 معاك أحمد من مصنع ليتل ستارز لملابس الأطفال في العاشر. "
                                "عندنا تشكيلة الشتا الجديدة بأسعار المصنع وأقل طلب دستة. ولو حابب تشوف الكتالوج "
                                "والأسعار، كلّم المساعد بتاعنا هنا: https://wa.me/201000000000?text=%23"
                                + lead.ref_code
                                if assisted
                                else f"أهلاً {lead.name[:40]} 👋 معاك ليتل ستارز. حابين نعرّفكم على تشكيلتنا الجديدة لملابس الأطفال."
                            ),
                            status=(
                                MessageStatus.AWAITING_MANUAL_SEND
                                if assisted
                                else MessageStatus.PENDING_APPROVAL
                            ).value,
                            created_at=ago(0, hours=2 + k),
                        )
                    )
                    if not assisted:
                        session.add(
                            Notification(
                                tenant_id=tid,
                                lead_id=lead.id,
                                kind="needs_approval",
                                title=f"رسالة لـ {lead.name} مستنية موافقتك",
                                body="افتح صفحة التواصل للموافقة",
                                created_at=ago(0, hours=2 + k),
                            )
                        )
                    counts["messages"] += 1
                    continue
                if status not in CONTACTED_OR_LATER:
                    continue

                # contacted and beyond: a first touch, and for ~25 leads a conversation
                contacted_at = clamp(created + timedelta(hours=20))
                lead.first_contacted_at = contacted_at
                lead.last_outbound_at = contacted_at
                conv = Conversation(
                    tenant_id=tid, lead_id=lead.id, channel="whatsapp", contact_value=fake_phone(index)
                )
                session.add(conv)
                await session.flush()
                counts["conversations"] += 1
                session.add(
                    Message(
                        tenant_id=tid,
                        conversation_id=conv.id,
                        lead_id=lead.id,
                        direction=MessageDirection.OUTBOUND.value,
                        channel="whatsapp",
                        author=MessageAuthor.AGENT.value,
                        kind=MessageKind.TEMPLATE.value,
                        purpose=OutreachPurpose.FIRST_TOUCH.value,
                        template_name="intro",
                        template_params=[lead.name[:40], "ليتل ستارز"],
                        body=f"أهلاً {lead.name[:40]} 👋 معاك ليتل ستارز. حابين نعرّفكم على تشكيلتنا الجديدة لملابس الأطفال.",
                        status=rng.choice([MessageStatus.READ, MessageStatus.DELIVERED]).value,
                        provider_message_id=f"wamid.demo.out.{index:03d}",
                        sent_at=contacted_at,
                        redirected_to=whitelist[index % len(whitelist)] if whitelist else None,
                        created_at=contacted_at,
                    )
                )
                counts["messages"] += 1
                if status == LeadStatus.CONTACTED:
                    continue
                intent = STATUS_INTENT.get(status) or question_cycle[k % len(question_cycle)]
                replied_at = clamp(contacted_at + timedelta(hours=rng.randint(1, 30)))
                session.add(
                    Message(
                        tenant_id=tid,
                        conversation_id=conv.id,
                        lead_id=lead.id,
                        direction=MessageDirection.INBOUND.value,
                        channel="whatsapp",
                        author=MessageAuthor.LEAD.value,
                        kind=MessageKind.TEXT.value,
                        body=rng.choice(LEAD_REPLIES[intent]),
                        status=MessageStatus.RECEIVED.value,
                        provider_message_id=f"wamid.demo.in.{index:03d}",
                        sent_at=replied_at,
                        reply_intent=intent.value,
                        created_at=replied_at,
                    )
                )
                counts["messages"] += 1
                lead.last_inbound_at = replied_at
                conv.window_expires_at = replied_at + timedelta(hours=24)
                answer = AGENT_REPLIES.get(intent)
                if answer and status != LeadStatus.OPTED_OUT:
                    session.add(
                        Message(
                            tenant_id=tid,
                            conversation_id=conv.id,
                            lead_id=lead.id,
                            direction=MessageDirection.OUTBOUND.value,
                            channel="whatsapp",
                            author=MessageAuthor.AGENT.value,
                            kind=MessageKind.TEXT.value,
                            purpose=OutreachPurpose.REPLY.value,
                            body=answer,
                            status=MessageStatus.READ.value,
                            provider_message_id=f"wamid.demo.reply.{index:03d}",
                            sent_at=replied_at + timedelta(minutes=1),
                            created_at=replied_at + timedelta(minutes=1),
                        )
                    )
                    counts["messages"] += 1
                if status in (LeadStatus.INTERESTED, LeadStatus.WANTS_OFFER, LeadStatus.WANTS_MANAGEMENT):
                    kind = {"interested": "hot_lead"}.get(status.value, status.value)
                    session.add(
                        Notification(
                            tenant_id=tid,
                            lead_id=lead.id,
                            kind=kind,
                            title=f"{lead.name}: {status.value.replace('_', ' ')}",
                            body=LEAD_REPLIES[intent][0],
                            created_at=replied_at,
                        )
                    )
                if status == LeadStatus.WON:
                    session.add(
                        LeadOutcome(
                            tenant_id=tid,
                            lead_id=lead.id,
                            outcome="won",
                            value_egp=WON_VALUES[won_i % len(WON_VALUES)],
                            reason="أول طلبية",
                            created_at=clamp(replied_at + timedelta(days=2)),
                        )
                    )
                    session.add(
                        LeadNote(
                            tenant_id=tid, lead_id=lead.id, body="اتفقنا على أول طلبية، التوصيل الأحد الجاي."
                        )
                    )
                    won_i += 1
                elif status == LeadStatus.LOST:
                    session.add(
                        LeadOutcome(
                            tenant_id=tid,
                            lead_id=lead.id,
                            outcome="lost",
                            reason=LOST_REASONS[lost_i % len(LOST_REASONS)],
                            created_at=clamp(replied_at + timedelta(days=2)),
                        )
                    )
                    lost_i += 1
        await session.flush()

        stats = await insights.compute_stats(session, tid)
        await insights.save_version(
            session,
            tid,
            insights=INSIGHTS,
            stats={
                "computed": stats,
                "icp_suggestions": ["Add Nasr City and Heliopolis as priority cities in Cairo."],
                "caveats": CAVEATS,
                "prompt_version": "feedback@1",
                "run_id": None,
            },
        )
        await session.commit()

    print("seed-demo: created the demo tenant")
    print(f"  login     {DEMO_EMAIL}")
    print(f"  password  {password}")
    print(
        f"  data      {counts['leads']} leads, {counts['conversations']} conversations, {counts['messages']} messages"
    )
    print(f"  ICP       version {icp_version} · demo phones {', '.join(whitelist) or '(none)'}")
    print(f"  knowledge {knowledge_where}")


def parse_whitelist(raw: str | None) -> list[str]:
    if not raw:
        return list(DEFAULT_WHITELIST)
    phones = [normalize_eg_phone(p) for p in raw.split(",") if p.strip()]
    valid = [p for p in phones if p]
    if len(valid) > 5:
        raise SystemExit("seed-demo: at most 5 demo phones (the WhatsApp test-number limit)")
    return valid


async def main_async(args: argparse.Namespace) -> None:
    if args.reset:
        async with SessionLocal() as session:
            await reset(session)
    await seed(password=args.password or secrets.token_urlsafe(9), whitelist=parse_whitelist(args.whitelist))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--reset", action="store_true", help="delete the demo tenant first")
    parser.add_argument("--password", help="owner password (default: random, printed)")
    parser.add_argument(
        "--whitelist", default=os.environ.get("DEMO_WHITELIST"), help="comma-separated test phones"
    )
    asyncio.run(main_async(parser.parse_args(argv)))


if __name__ == "__main__":
    main()
