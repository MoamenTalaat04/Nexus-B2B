"""Deterministic seed data for Mock API mode."""
# ruff: noqa: E501

from __future__ import annotations

import uuid
from datetime import UTC, datetime, time, timedelta
from typing import Any

from app.mock_api.state import (
    MockAgentRun,
    MockAgentStep,
    MockBusinessSettings,
    MockChannelConnection,
    MockContact,
    MockConversation,
    MockIcpVersion,
    MockKnowledgeFile,
    MockLead,
    MockLeadNote,
    MockLeadOutcome,
    MockLearnedInsight,
    MockMessage,
    MockMessageTemplate,
    MockNotification,
    MockStore,
    MockTenant,
    MockUser,
)
from app.models.enums import (
    AgentRunKind,
    AgentRunStatus,
    AutonomyMode,
    ChannelType,
    ContactType,
    FirstTouchMode,
    LeadStatus,
    MessageAuthor,
    MessageDirection,
    MessageKind,
    MessageStatus,
    OutreachPurpose,
    ReplyIntent,
    StepType,
)

# Deterministic UUIDs for reproducible tests and screenshots
T1_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
T1_OWNER_ID = uuid.UUID("11111111-1111-1111-1111-111111111101")
T1_MEMBER1_ID = uuid.UUID("11111111-1111-1111-1111-111111111102")
T1_MEMBER2_ID = uuid.UUID("11111111-1111-1111-1111-111111111103")

T2_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
T2_OWNER_ID = uuid.UUID("22222222-2222-2222-2222-222222222201")

BASE_TIME = datetime(2026, 11, 19, 9, 0, 0, tzinfo=UTC)


def _uid(prefix: str, idx: int) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_DNS, f"nexus-b2b.{prefix}.{idx}")


def _ts(days_offset: int = 0, hours_offset: int = 0, minutes_offset: int = 0) -> datetime:
    return BASE_TIME + timedelta(days=days_offset, hours=hours_offset, minutes=minutes_offset)


def _little_stars_profile() -> dict[str, Any]:
    return {
        "company_name": "Little Stars Kids Wear",
        "one_liner": "مصنع مصري متخصص في تصنيع وتوريد ملابس الأطفال بالجملة لمحلات التجزئة.",
        "products": [
            {
                "name": "أطقم خروج أطفال (Kids Clothing Sets)",
                "description": "أطقم قطنية صيفية وشتوية للأولاد والبنات من سن 2 إلى 12 سنة",
                "price_range": "220 - 380 EGP / piece",
                "min_order": "24 pieces",
            },
            {
                "name": "ملابس حديثي الولادة (Baby Clothes)",
                "description": "سالوبيت وباديهات قطن 100% من 0 إلى 24 شهر",
                "price_range": "140 - 250 EGP / piece",
                "min_order": "30 pieces",
            },
            {
                "name": "يونيفورم ومدارس (School Clothing)",
                "description": "تيشيرتات بولو وبناطيل جينز وجبردين للمدارس",
                "price_range": "180 - 310 EGP / piece",
                "min_order": "50 pieces",
            },
            {
                "name": "باكدجات جملة موسمية (Wholesale Packages)",
                "description": "سيريهات كاملة مشكلة بألوان ومقاسات متعددة للمحلات",
                "price_range": "6500 - 14000 EGP / package",
                "min_order": "2 packages",
            },
        ],
        "differentiators": [
            "قطن مصري 100% معالج ضد الانكماش",
            "أقل كمية طلب مرنة للمحلات الجديدة (24 قطعة)",
            "توصيل سريع خلال 48 ساعة للقاهرة والجيزة",
            "استبدال المقاسات غير المباعة خلال 30 يوم",
        ],
        "target_customer_summary": "محلات ملابس الأطفال، معارض مستلزمات البيبي، وتجار التجزئة في القاهرة والجيزة.",
        "allowed_offers": "خصم 5% لأول طلب، وشحن مجاني داخل القاهرة والجيزة للطلبات فوق 15,000 جنيه، وخصم حتى 10% للكميات فوق 200 قطعة.",
        "max_discount_percent": 10,
        "faqs": [
            {"q": "ما هو أقل حد للطلب؟", "a": "أقل كمية طلب هي 24 قطعة مشكلة أو باكدجين جملة."},
            {
                "q": "هل متاح الشحن للمحافظات؟",
                "a": "نعم، شحن خلال 48 ساعة للقاهرة والجيزة و72 ساعة لباقي المحافظات.",
            },
        ],
        "tone": "friendly",
        "language": "ar-EG",
    }


def _little_stars_icp() -> dict[str, Any]:
    return {
        "summary": "Retail kids clothing shops, baby boutiques, and family apparel stores in Cairo and Giza with strong local foot traffic.",
        "target_business_types": [
            "kids clothing store",
            "baby store",
            "children apparel shop",
            "محل ملابس أطفال",
            "معرض مستلزمات أطفال وبيبي",
        ],
        "include_keywords": ["ملابس أطفال", "بيبي", "kids wear", "children clothing", "baby shop", "أطفال"],
        "exclude_keywords": ["حريمي فقط", "رجالي فقط", "مطعم", "صيدلية", "مستعمل", "بالة"],
        "google_place_types": ["clothing_store", "baby_store"],
        "regions": [
            {"governorate": "Cairo", "cities": ["Nasr City", "Heliopolis", "Maadi", "Shubra", "New Cairo"]},
            {"governorate": "Giza", "cities": ["Dokki", "Mohandessin", "Haram", "Faisal", "6th of October"]},
        ],
        "business_size": "small",
        "must_have": [
            "Active retail storefront or showroom",
            "Sells children's or baby apparel",
            "Located in Cairo or Giza",
        ],
        "nice_to_have": [
            "Google rating >= 4.0",
            "More than 20 Google reviews",
            "Active website or WhatsApp link",
        ],
        "disqualifiers": [
            "Permanently closed business",
            "Adult-only clothing store",
            "Competing wholesale garment factory",
        ],
        "value_proposition": "100% Egyptian cotton kids wear with low 24-piece MOQ and 48h Cairo/Giza delivery.",
        "pain_points": [
            "High minimum order quantities from factories",
            "Inconsistent fabric quality",
            "Slow restocking",
        ],
        "outreach_angle": "Introduce our flexible 24-piece seasonal kids wear packages with free Cairo/Giza delivery on first order.",
        "language": "ar-EG",
    }


def populate_seed_data(store: MockStore) -> None:
    """Populate deterministic seed data for Little Stars Kids Wear and a second isolated tenant."""
    # --- Tenant 1: Little Stars Kids Wear ---
    store.tenants[T1_ID] = MockTenant(id=T1_ID, name="Little Stars Kids Wear", created_at=_ts(-30))
    store.users[T1_OWNER_ID] = MockUser(
        id=T1_OWNER_ID,
        tenant_id=T1_ID,
        email="demo@littlestars.eg",
        password="DemoPass123!",
        full_name="أحمد محمود (Ahmed Mahmoud)",
        role="owner",
        created_at=_ts(-30),
    )
    store.users[T1_MEMBER1_ID] = MockUser(
        id=T1_MEMBER1_ID,
        tenant_id=T1_ID,
        email="sara@littlestars.eg",
        password="DemoPass123!",
        full_name="سارة حسن (Sara Hassan)",
        role="member",
        created_at=_ts(-28),
    )
    store.users[T1_MEMBER2_ID] = MockUser(
        id=T1_MEMBER2_ID,
        tenant_id=T1_ID,
        email="karim@littlestars.eg",
        password="DemoPass123!",
        full_name="كريم عادل (Karim Adel)",
        role="member",
        created_at=_ts(-25),
    )

    profile = _little_stars_profile()
    icp = _little_stars_icp()

    s1_id = _uid("settings", 1)
    store.settings[s1_id] = MockBusinessSettings(
        id=s1_id,
        tenant_id=T1_ID,
        company_name="Little Stars Kids Wear",
        website="https://littlestars.example.com",
        description="مصنع ملابس أطفال بالجملة في العاشر من رمضان — توريد لأرقى محلات القاهرة والجيزة.",
        ideal_customer_text="محلات ملابس الأطفال ومستلزمات البيبي في القاهرة والجيزة التي تبحث عن خامات قطن ممتازة وبدايات طلب مرنة.",
        products=profile["products"],
        target_regions=icp["regions"],
        language="ar-EG",
        tone="friendly",
        allowed_offers=profile["allowed_offers"],
        max_discount_percent=10,
        autonomy_mode=AutonomyMode.APPROVE_ALL.value,
        first_touch_mode=FirstTouchMode.API_TEMPLATE.value,
        agent_enabled=True,
        daily_new_leads_target=30,
        daily_send_cap=20,
        quiet_hours_start=time(10, 0),
        quiet_hours_end=time(20, 0),
        working_days=[0, 1, 2, 3, 5, 6],
        score_threshold=6,
        demo_mode=True,
        demo_whitelist=["+201000009901", "+201000009902"],
        telegram_chat_id="987654321",
        onboarding_completed=True,
        updated_at=_ts(-2),
    )

    # Knowledge docs
    k1_id = _uid("knowledge", 1)
    k1_text = (
        "### كتالوج مصنع لتل ستارز لملابس الأطفال\n"
        "الموقع: المنطقة الصناعية الثالثة، العاشر من رمضان، الشرقية.\n"
        "المنتجات: أطقم خروج أطفال (220-380 ج)، ملابس بيبي قطن 100% (140-250 ج)، يونيفورم مدارس، باكدجات جملة.\n"
        "الحد الأدنى للطلب: 24 قطعة مشكلة. الشحن مجاني للقاهرة والجيزة للطلبات فوق 15000 جنيه."
    )
    store.knowledge[k1_id] = MockKnowledgeFile(
        id=k1_id,
        tenant_id=T1_ID,
        filename="little-stars-catalog-ar.md",
        mime_type="text/markdown",
        size_bytes=len(k1_text.encode("utf-8")),
        extracted_text=k1_text,
        char_count=len(k1_text),
        status="ready",
        created_at=_ts(-20),
    )
    k2_id = _uid("knowledge", 2)
    k2_text = (
        "Little Stars Wholesale Price List & Terms 2026.\n"
        "MOQ: 24 pcs per order. Payment: Cash on delivery or bank transfer.\n"
        "Max discount: up to 10% for orders exceeding 200 pieces."
    )
    store.knowledge[k2_id] = MockKnowledgeFile(
        id=k2_id,
        tenant_id=T1_ID,
        filename="wholesale-terms-2026.pdf",
        mime_type="application/pdf",
        size_bytes=245120,
        extracted_text=k2_text,
        char_count=len(k2_text),
        status="ready",
        created_at=_ts(-18),
    )

    # ICP versions (v1 historical agent, v2 historical user, v3 active)
    icp1_id = _uid("icp", 1)
    icp2_id = _uid("icp", 2)
    icp3_id = _uid("icp", 3)
    store.icp_versions[icp1_id] = MockIcpVersion(
        id=icp1_id,
        tenant_id=T1_ID,
        version=1,
        company_profile=profile,
        icp=icp,
        source="agent",
        is_active=False,
        notes="Initial AI-generated ICP",
        created_at=_ts(-15),
    )
    store.icp_versions[icp2_id] = MockIcpVersion(
        id=icp2_id,
        tenant_id=T1_ID,
        version=2,
        company_profile=profile,
        icp=icp,
        source="user",
        is_active=False,
        notes="Added New Cairo & 6th of October",
        created_at=_ts(-10),
    )
    store.icp_versions[icp3_id] = MockIcpVersion(
        id=icp3_id,
        tenant_id=T1_ID,
        version=3,
        company_profile=profile,
        icp=icp,
        source="agent",
        is_active=True,
        notes="Refined keywords after first sourcing batch",
        created_at=_ts(-5),
    )

    # Channel connection & templates
    ch_id = _uid("channel", 1)
    store.channels[ch_id] = MockChannelConnection(
        id=ch_id,
        tenant_id=T1_ID,
        channel=ChannelType.WHATSAPP.value,
        status="connected",
        config={
            "phone_number_id": "109876543210987",
            "waba_id": "209876543210987",
            "display_phone_number": "+20 100 000 0000",
        },
        last_checked_at=_ts(0, -1),
    )
    tpl1_id = _uid("tpl", 1)
    tpl2_id = _uid("tpl", 2)
    store.templates[tpl1_id] = MockMessageTemplate(
        id=tpl1_id,
        tenant_id=T1_ID,
        channel=ChannelType.WHATSAPP.value,
        name="intro",
        language="ar",
        category="MARKETING",
        purpose="intro",
        body_text="أهلاً {{1}}! معكم مصنع لتل ستارز لملابس الأطفال بالجملة. لاحظنا {{2}} وحابين نعرض عليكم أحدث تشكيلة قطن 100% بحد أدنى مرن 24 قطعة. للرد بالإلغاء ابعت STOP.",
        param_count=2,
        status="approved",
    )
    store.templates[tpl2_id] = MockMessageTemplate(
        id=tpl2_id,
        tenant_id=T1_ID,
        channel=ChannelType.WHATSAPP.value,
        name="followup",
        language="ar",
        category="MARKETING",
        purpose="followup",
        body_text="مساء الخير {{1}}، متابعة سريعة بخصوص كتالوج ملابس الأطفال الجملة من لتل ستارز — متاح شحن مجاني للقاهرة والجيزة هذا الأسبوع. تحب نبعتلك الأسعار؟",
        param_count=1,
        status="approved",
    )

    # Agent Runs (12 runs across different kinds & statuses)
    sourcing_run_1 = _uid("run", 1)
    sourcing_run_2 = _uid("run", 2)
    scoring_run_1 = _uid("run", 3)
    enrich_run_1 = _uid("run", 4)
    outreach_run_1 = _uid("run", 5)
    reply_run_1 = _uid("run", 6)
    feedback_run_1 = _uid("run", 7)
    icp_run_1 = _uid("run", 8)
    failed_run_1 = _uid("run", 9)
    outreach_run_2 = _uid("run", 10)
    reply_run_2 = _uid("run", 11)
    sourcing_run_3 = _uid("run", 12)

    runs_spec: list[
        tuple[
            uuid.UUID,
            AgentRunKind,
            AgentRunStatus,
            str,
            int,
            dict[str, Any] | None,
            str | None,
            int,
            int,
            float,
        ]
    ] = [
        (
            icp_run_1,
            AgentRunKind.ICP_BUILD,
            AgentRunStatus.SUCCEEDED,
            "manual",
            -5,
            {"version": 3},
            None,
            1450,
            620,
            0.0042,
        ),
        (
            sourcing_run_1,
            AgentRunKind.SOURCING,
            AgentRunStatus.SUCCEEDED,
            "schedule",
            -4,
            {"created": 24, "duplicates": 3},
            None,
            980,
            410,
            0.0015,
        ),
        (
            scoring_run_1,
            AgentRunKind.SCORING,
            AgentRunStatus.SUCCEEDED,
            "chained",
            -4,
            {"qualified": 18, "disqualified": 6},
            None,
            4200,
            1100,
            0.0038,
        ),
        (
            enrich_run_1,
            AgentRunKind.ENRICHMENT,
            AgentRunStatus.SUCCEEDED,
            "chained",
            -4,
            {"enriched": 16, "no_contact": 2},
            None,
            0,
            0,
            0.0,
        ),
        (
            outreach_run_1,
            AgentRunKind.OUTREACH_TICK,
            AgentRunStatus.SUCCEEDED,
            "schedule",
            -3,
            {"queued": 10, "assisted": 3},
            None,
            2100,
            780,
            0.0024,
        ),
        (
            reply_run_1,
            AgentRunKind.REPLY,
            AgentRunStatus.SUCCEEDED,
            "webhook",
            -2,
            {"intent": "interested", "escalated": True},
            None,
            1300,
            320,
            0.0019,
        ),
        (
            reply_run_2,
            AgentRunKind.REPLY,
            AgentRunStatus.SUCCEEDED,
            "webhook",
            -1,
            {"intent": "wants_offer", "escalated": True},
            None,
            1420,
            350,
            0.0021,
        ),
        (
            outreach_run_2,
            AgentRunKind.OUTREACH_TICK,
            AgentRunStatus.SUCCEEDED,
            "schedule",
            -1,
            {"queued": 5, "assisted": 2},
            None,
            1600,
            540,
            0.0018,
        ),
        (
            feedback_run_1,
            AgentRunKind.FEEDBACK,
            AgentRunStatus.SUCCEEDED,
            "manual",
            -1,
            {"insights_count": 4, "version": 2},
            None,
            2600,
            890,
            0.0061,
        ),
        (
            sourcing_run_2,
            AgentRunKind.SOURCING,
            AgentRunStatus.SUCCEEDED,
            "manual",
            0,
            {"created": 12, "duplicates": 2},
            None,
            890,
            340,
            0.0012,
        ),
        (
            failed_run_1,
            AgentRunKind.SOURCING,
            AgentRunStatus.FAILED,
            "manual",
            -2,
            None,
            "Google Places rate limit exceeded (429)",
            400,
            120,
            0.0005,
        ),
        (
            sourcing_run_3,
            AgentRunKind.ENRICHMENT,
            AgentRunStatus.SUCCEEDED,
            "chained",
            0,
            {"enriched": 8, "no_contact": 1},
            None,
            0,
            0,
            0.0,
        ),
    ]
    for idx, (rid, kind, status, trig, d_off, summary, err, in_tok, out_tok, cost) in enumerate(
        runs_spec, start=1
    ):
        started = _ts(d_off, -2)
        finished = _ts(d_off, -2, 3) if status != AgentRunStatus.RUNNING else None
        store.runs[rid] = MockAgentRun(
            id=rid,
            tenant_id=T1_ID,
            kind=kind.value,
            status=status.value,
            trigger=trig,
            input={"tenant": "Little Stars Kids Wear", "batch": idx},
            output_summary=summary,
            error=err,
            created_at=started,
            started_at=started,
            finished_at=finished,
            total_input_tokens=in_tok,
            total_output_tokens=out_tok,
            total_cost_usd=cost,
        )

    # Steps for key runs
    step_defs = [
        (
            sourcing_run_1,
            1,
            StepType.LLM_CALL,
            "query_generator",
            {"icp_version": 3},
            {"queries_count": 6},
            "gemini-3.5-flash-lite",
            980,
            410,
            400,
            0.0015,
            820,
            None,
        ),
        (
            sourcing_run_1,
            2,
            StepType.EXTERNAL_API,
            "google_places.search",
            {"query": "محل ملابس أطفال مدينة نصر"},
            {"results": 15},
            None,
            0,
            0,
            0,
            0.0,
            450,
            None,
        ),
        (
            sourcing_run_1,
            3,
            StepType.DECISION,
            "leads_ingest.summary",
            {"raw_places": 27},
            {"created": 24, "duplicates": 3},
            None,
            0,
            0,
            0,
            0.0,
            35,
            None,
        ),
        (
            scoring_run_1,
            1,
            StepType.LLM_CALL,
            "lead_scorer.batch_1",
            {"count": 15},
            {"qualified": 12, "disqualified": 3},
            "gemini-3.5-flash-lite",
            2200,
            600,
            1200,
            0.0020,
            1150,
            None,
        ),
        (
            scoring_run_1,
            2,
            StepType.LLM_CALL,
            "lead_scorer.batch_2",
            {"count": 9},
            {"qualified": 6, "disqualified": 3},
            "gemini-3.5-flash-lite",
            2000,
            500,
            1200,
            0.0018,
            940,
            None,
        ),
        (
            scoring_run_1,
            3,
            StepType.DECISION,
            "scoring.summary",
            {"total": 24},
            {"qualified": 18, "disqualified": 6},
            None,
            0,
            0,
            0,
            0.0,
            20,
            None,
        ),
        (
            failed_run_1,
            1,
            StepType.LLM_CALL,
            "query_generator",
            {"icp_version": 3},
            {"queries_count": 4},
            "gemini-3.5-flash-lite",
            400,
            120,
            0,
            0.0005,
            610,
            None,
        ),
        (
            failed_run_1,
            2,
            StepType.ERROR,
            "google_places.search",
            {"query": "kids wear Maadi"},
            {"error": "429 Too Many Requests"},
            None,
            0,
            0,
            0,
            0.0,
            300,
            None,
        ),
        (
            reply_run_1,
            1,
            StepType.LLM_CALL,
            "reply_classifier",
            {"text": "مهتم جداً، ابعتلي الأسعار والكتالوج"},
            {"intent": "interested", "confidence": 0.96},
            "gemini-3.5-flash-lite",
            450,
            80,
            200,
            0.0004,
            390,
            _uid("lead", 10),
        ),
        (
            reply_run_1,
            2,
            StepType.TOOL_CALL,
            "search_knowledge",
            {"query": "أسعار الجملة الحد الأدنى"},
            {"matches": 2},
            None,
            0,
            0,
            0,
            0.0,
            15,
            _uid("lead", 10),
        ),
        (
            reply_run_1,
            3,
            StepType.LLM_CALL,
            "reply_agent",
            {"intent": "interested"},
            {"reply_sent": True, "escalated": True},
            "gemini-4-hydrogen",
            850,
            240,
            400,
            0.0015,
            980,
            _uid("lead", 10),
        ),
    ]
    for s_idx, (rid, seq, stype, name, inp, outp, model, itok, otok, ctok, cost, lat, lid) in enumerate(
        step_defs, start=1
    ):
        sid = _uid("step", s_idx)
        store.steps[sid] = MockAgentStep(
            id=sid,
            tenant_id=T1_ID,
            run_id=rid,
            seq=seq,
            step_type=stype.value,
            name=name,
            input=inp,
            output=outp,
            model=model,
            input_tokens=itok,
            output_tokens=otok,
            cache_read_tokens=ctok,
            cost_usd=cost,
            latency_ms=lat,
            lead_id=lid,
            created_at=_ts(-3, 0, s_idx),
        )

    # 36 Fictional Egyptian Leads across statuses
    lead_catalog: list[
        tuple[str, str, str, str, float, int, LeadStatus, int | None, list[str], str | None, bool, int]
    ] = [
        (
            "كيدز زون لملابس الأطفال - Kids Zone",
            "kids clothing store",
            "Cairo",
            "Nasr City",
            4.7,
            142,
            LeadStatus.WON,
            9,
            ["Dedicated kids clothing store in Nasr City", "High customer rating (4.7) with 142 reviews"],
            None,
            True,
            -4,
        ),
        (
            "محلات ميني ستار - Mini Star Baby",
            "baby store",
            "Cairo",
            "Heliopolis",
            4.6,
            89,
            LeadStatus.INTERESTED,
            9,
            ["Sells baby and kids apparel in Heliopolis", "Active website and WhatsApp link"],
            None,
            True,
            -4,
        ),
        (
            "كوكو كيدز - Coco Kids Boutique",
            "kids clothing store",
            "Giza",
            "Mohandessin",
            4.8,
            210,
            LeadStatus.WANTS_OFFER,
            9,
            ["Prime retail boutique in Mohandessin", "Strong review volume (210)"],
            None,
            True,
            -3,
        ),
        (
            "بيبي هاوس - Baby House Maadi",
            "baby store",
            "Cairo",
            "Maadi",
            4.5,
            76,
            LeadStatus.WANTS_MANAGEMENT,
            8,
            ["Established baby store in Maadi", "Matches target business type"],
            None,
            True,
            -3,
        ),
        (
            "أولادنا لملابس الأطفال",
            "kids clothing store",
            "Cairo",
            "Shubra",
            4.3,
            54,
            LeadStatus.REPLIED,
            8,
            ["Kids apparel retailer in Shubra", "Good Google rating (4.3)"],
            None,
            True,
            -3,
        ),
        (
            "جونيور ستايل - Junior Style",
            "clothing store",
            "Giza",
            "Dokki",
            4.4,
            67,
            LeadStatus.CONTACTED,
            8,
            ["Kids & junior clothing shop in Dokki", "Target region match"],
            None,
            True,
            -3,
        ),
        (
            "عالم الطفولة - Childhood World",
            "kids clothing store",
            "Cairo",
            "New Cairo",
            4.6,
            112,
            LeadStatus.CONTACTED,
            9,
            ["High-end kids clothing store in New Cairo", "Strong foot traffic indicators"],
            None,
            True,
            -2,
        ),
        (
            "سمايل كيدز - Smile Kids Wear",
            "kids clothing store",
            "Giza",
            "Haram",
            4.2,
            43,
            LeadStatus.QUEUED,
            7,
            ["Kids store on Haram St.", "Has verified mobile contact"],
            None,
            True,
            -2,
        ),
        (
            "فرحة بيبي - Farha Baby Shop",
            "baby store",
            "Cairo",
            "Nasr City",
            4.5,
            95,
            LeadStatus.QUEUED,
            8,
            ["Baby & newborn retail shop", "Nasr City target area"],
            None,
            True,
            -2,
        ),
        (
            "توم آند جيري لملابس الأطفال",
            "kids clothing store",
            "Giza",
            "Faisal",
            4.1,
            38,
            LeadStatus.ENRICHED,
            7,
            ["Kids wear shop in Faisal", "Mobile number discovered"],
            None,
            True,
            -2,
        ),
        (
            "مارينا كيدز - Marina Kids",
            "kids clothing store",
            "Cairo",
            "Heliopolis",
            4.4,
            61,
            LeadStatus.ENRICHED,
            8,
            ["Boutique kids apparel in Heliopolis", "Good reviews"],
            None,
            True,
            -2,
        ),
        (
            "بيبي لاند - Baby Land October",
            "baby store",
            "Giza",
            "6th of October",
            4.3,
            84,
            LeadStatus.ENRICHED,
            8,
            ["Large baby store in 6th of October", "Active online presence"],
            None,
            True,
            -1,
        ),
        (
            "نور كيدز - Nour Kids Fashion",
            "kids clothing store",
            "Cairo",
            "Ain Shams",
            4.0,
            29,
            LeadStatus.ENRICHED,
            7,
            ["Kids retail shop in Ain Shams", "Mobile verified"],
            None,
            True,
            -1,
        ),
        (
            "تيجي كيدز - Tigi Kids",
            "kids clothing store",
            "Cairo",
            "Maadi",
            4.5,
            48,
            LeadStatus.QUALIFIED,
            8,
            ["Kids fashion store in Maadi", "Needs contact enrichment"],
            None,
            False,
            -1,
        ),
        (
            "بونبون لملابس الأطفال",
            "kids clothing store",
            "Giza",
            "Sheikh Zayed",
            4.7,
            91,
            LeadStatus.QUALIFIED,
            9,
            ["Premium kids boutique in Zayed", "High rating 4.7"],
            None,
            False,
            -1,
        ),
        (
            "الأميرة الصغيرة - Little Princess",
            "kids clothing store",
            "Cairo",
            "Downtown",
            4.2,
            52,
            LeadStatus.NO_CONTACT,
            7,
            ["Kids clothing shop in Downtown", "No mobile found on website"],
            None,
            False,
            -3,
        ),
        (
            "أجيال للملابس المدرسية",
            "clothing store",
            "Giza",
            "Imbaba",
            4.0,
            19,
            LeadStatus.NO_CONTACT,
            6,
            ["Sells school uniforms", "Landline only on Google Maps"],
            None,
            False,
            -3,
        ),
        (
            "سنو وايت كيدز - Snow White",
            "kids clothing store",
            "Cairo",
            "Mokattam",
            4.3,
            35,
            LeadStatus.LATER,
            7,
            ["Kids clothing shop in Mokattam", "Asked to follow up next month"],
            None,
            True,
            -4,
        ),
        (
            "كيدي كلوب - Kiddy Club",
            "kids clothing store",
            "Giza",
            "Dokki",
            4.4,
            41,
            LeadStatus.NOT_INTERESTED,
            7,
            ["Kids apparel store in Dokki", "Has existing exclusive supplier"],
            None,
            True,
            -4,
        ),
        (
            "دريم كيدز - Dream Kids",
            "kids clothing store",
            "Cairo",
            "Shubra",
            4.1,
            27,
            LeadStatus.LOST,
            7,
            ["Kids shop in Shubra", "Lost on payment terms"],
            None,
            True,
            -4,
        ),
        (
            "أبطال الموضة - Fashion Heroes",
            "clothing store",
            "Cairo",
            "Nasr City",
            4.2,
            64,
            LeadStatus.WRONG_CONTACT,
            7,
            ["Listed number belongs to personal residence"],
            None,
            True,
            -4,
        ),
        (
            "هلال كيدز - Helal Kids",
            "kids clothing store",
            "Giza",
            "Haram",
            4.0,
            22,
            LeadStatus.OPTED_OUT,
            6,
            ["Requested opt-out via WhatsApp"],
            None,
            True,
            -4,
        ),
        (
            "بوتيك سمارت مان - Smart Man",
            "mens clothing store",
            "Cairo",
            "Nasr City",
            4.5,
            110,
            LeadStatus.DISQUALIFIED,
            2,
            ["Adult menswear only, no kids section"],
            "Adult-only clothing store",
            False,
            -4,
        ),
        (
            "مطعم البركة للمشويات",
            "restaurant",
            "Giza",
            "Faisal",
            4.3,
            340,
            LeadStatus.DISQUALIFIED,
            0,
            ["Restaurant, unrelated to apparel"],
            "Unrelated category (restaurant)",
            False,
            -4,
        ),
        (
            "صيدلية الأمل الحديثة",
            "pharmacy",
            "Cairo",
            "Maadi",
            4.6,
            88,
            LeadStatus.DISQUALIFIED,
            0,
            ["Pharmacy, outside target business types"],
            "Unrelated category (pharmacy)",
            False,
            -4,
        ),
        (
            "البيت الإيطالي للبدل",
            "mens clothing store",
            "Cairo",
            "Downtown",
            4.4,
            75,
            LeadStatus.DISQUALIFIED,
            1,
            ["Men's suits only"],
            "Adult-only clothing store",
            False,
            -3,
        ),
        (
            "محل السعادة (مغلق)",
            "kids clothing store",
            "Giza",
            "Imbaba",
            3.8,
            12,
            LeadStatus.DISQUALIFIED,
            0,
            ["Marked permanently closed"],
            "Permanently closed business",
            False,
            -3,
        ),
        (
            "مصنع النصر للملابس الجاهزة",
            "clothing manufacturer",
            "Qalyubia",
            "Shubra El Kheima",
            4.1,
            15,
            LeadStatus.DISQUALIFIED,
            2,
            ["Competing garment factory"],
            "Competing wholesale garment factory",
            False,
            -3,
        ),
        (
            "كوكو بيبي - Coco Baby",
            "baby store",
            "Cairo",
            "New Cairo",
            4.5,
            58,
            LeadStatus.NEW,
            None,
            [],
            None,
            True,
            0,
        ),
        (
            "هابي كيدز - Happy Kids",
            "kids clothing store",
            "Giza",
            "6th of October",
            4.4,
            49,
            LeadStatus.NEW,
            None,
            [],
            None,
            True,
            0,
        ),
        (
            "بيبي ستايل - Baby Style",
            "baby store",
            "Cairo",
            "Heliopolis",
            4.6,
            73,
            LeadStatus.NEW,
            None,
            [],
            None,
            False,
            0,
        ),
        (
            "مملكة الأطفال - Kids Kingdom",
            "kids clothing store",
            "Cairo",
            "Nasr City",
            4.3,
            62,
            LeadStatus.NEW,
            None,
            [],
            None,
            True,
            0,
        ),
        (
            "ستارز جونيور - Stars Junior",
            "kids clothing store",
            "Giza",
            "Mohandessin",
            4.7,
            94,
            LeadStatus.WON,
            9,
            ["Multi-branch kids store in Mohandessin", "Placed initial 120-piece order"],
            None,
            True,
            -4,
        ),
        (
            "كيدي لاند - Kiddy Land",
            "kids clothing store",
            "Cairo",
            "Maadi",
            4.5,
            81,
            LeadStatus.INTERESTED,
            8,
            ["Popular Maadi kids shop", "Requested winter catalog"],
            None,
            True,
            -2,
        ),
        (
            "لؤلؤة بيبي - Pearl Baby",
            "baby store",
            "Giza",
            "Sheikh Zayed",
            4.6,
            44,
            LeadStatus.ENRICHED,
            8,
            ["Zayed baby boutique", "WhatsApp number verified"],
            None,
            True,
            -1,
        ),
        (
            "ألفا كيدز - Alpha Kids",
            "kids clothing store",
            "Cairo",
            "Zamalek",
            4.8,
            129,
            LeadStatus.CONTACTED,
            9,
            ["High-end boutique in Zamalek", "First template sent"],
            None,
            True,
            -2,
        ),
    ]

    for idx, (name, cat, gov, city, rating, rev, l_status, score, reasons, disq, has_mob, d_off) in enumerate(
        lead_catalog, start=1
    ):
        lid = _uid("lead", idx)
        run_ref = sourcing_run_2 if d_off == 0 else sourcing_run_1
        first_c = (
            _ts(d_off, 1)
            if l_status
            in {
                LeadStatus.CONTACTED,
                LeadStatus.REPLIED,
                LeadStatus.INTERESTED,
                LeadStatus.WANTS_OFFER,
                LeadStatus.WANTS_MANAGEMENT,
                LeadStatus.LATER,
                LeadStatus.NOT_INTERESTED,
                LeadStatus.LOST,
                LeadStatus.WON,
                LeadStatus.OPTED_OUT,
                LeadStatus.WRONG_CONTACT,
            }
            else None
        )
        last_in = (
            _ts(d_off, 3)
            if l_status
            in {
                LeadStatus.REPLIED,
                LeadStatus.INTERESTED,
                LeadStatus.WANTS_OFFER,
                LeadStatus.WANTS_MANAGEMENT,
                LeadStatus.LATER,
                LeadStatus.NOT_INTERESTED,
                LeadStatus.LOST,
                LeadStatus.WON,
                LeadStatus.OPTED_OUT,
            }
            else None
        )
        lead = MockLead(
            id=lid,
            tenant_id=T1_ID,
            name=name,
            source="google_places",
            source_ref=f"ChIJ_mock_{idx:03d}",
            category=cat,
            address=f"{10 + idx} شارع رئيسي، {city}، {gov}",
            city=city,
            governorate=gov,
            lat=30.0444 + (idx * 0.004),
            lng=31.2357 + (idx * 0.004),
            website=f"https://shop{idx}.example.com" if idx % 2 == 0 else None,
            domain=f"shop{idx}.example.com" if idx % 2 == 0 else None,
            google_maps_url=f"https://maps.google.com/?q=30.0444,31.2357&cid={idx}",
            rating=rating,
            reviews_count=rev,
            status=l_status.value,
            score=score,
            score_reasons=reasons,
            disqualify_reason=disq,
            icp_version_id=icp3_id,
            sourcing_run_id=run_ref,
            sequence_step=1 if first_c else 0,
            agent_paused=l_status
            in {LeadStatus.WON, LeadStatus.LOST, LeadStatus.WANTS_MANAGEMENT, LeadStatus.OPTED_OUT},
            first_contacted_at=first_c,
            last_outbound_at=first_c,
            last_inbound_at=last_in,
            ref_code=f"NX{idx:04d}",
            dedupe_key=f"google_places:ChIJ_mock_{idx:03d}",
            created_at=_ts(d_off),
        )
        store.leads[lid] = lead

        if has_mob:
            cid = _uid("contact", idx)
            store.contacts[cid] = MockContact(
                id=cid,
                tenant_id=T1_ID,
                lead_id=lid,
                type=ContactType.MOBILE.value,
                value=f"+20100000{idx:04d}",
                source="google_places",
                is_primary=True,
                confidence=0.92,
                created_at=_ts(d_off),
            )
            if idx % 3 == 0:
                wid = _uid("contact_web", idx)
                store.contacts[wid] = MockContact(
                    id=wid,
                    tenant_id=T1_ID,
                    lead_id=lid,
                    type=ContactType.EMAIL.value,
                    value=f"sales@shop{idx}.example.com",
                    source="website",
                    is_primary=False,
                    confidence=0.8,
                    created_at=_ts(d_off),
                )

    # Conversations + messages for active/replied/queued leads
    conv_specs = [
        (1, "مهتم جداً بالأسعار، ابعتلي الكتالوج.", ReplyIntent.INTERESTED),
        (2, "ممكن تفاصيل أكتر عن أقل كمية للطلب؟", ReplyIntent.INTERESTED),
        (3, "عايز أعرف لو في خصم 10% على 250 قطعة؟", ReplyIntent.WANTS_OFFER),
        (4, "عايز أكلم صاحب المصنع أو مدير المبيعات ضروري.", ReplyIntent.WANTS_MANAGEMENT),
        (5, "مقاسات الشتوي عندكم متوفرة لحد سن كام؟", ReplyIntent.QUESTION),
        (18, "شكراً، كلمني الشهر الجاي قبل موسم العيد.", ReplyIntent.LATER),
        (19, "مش مهتم حالياً شكراً لتواصلكم.", ReplyIntent.NOT_INTERESTED),
        (22, "STOP", ReplyIntent.OPTED_OUT),
    ]
    for c_idx, (lead_num, inbound_text, intent) in enumerate(conv_specs, start=1):
        lid = _uid("lead", lead_num)
        conv_id = _uid("conv", c_idx)
        phone = f"+20100000{lead_num:04d}"
        store.conversations[conv_id] = MockConversation(
            id=conv_id,
            tenant_id=T1_ID,
            lead_id=lid,
            channel=ChannelType.WHATSAPP.value,
            contact_value=phone,
            window_expires_at=_ts(1),
            created_at=_ts(-3),
        )
        m_out = _uid("msg_out", c_idx)
        store.messages[m_out] = MockMessage(
            id=m_out,
            tenant_id=T1_ID,
            conversation_id=conv_id,
            lead_id=lid,
            direction=MessageDirection.OUTBOUND.value,
            channel=ChannelType.WHATSAPP.value,
            author=MessageAuthor.AGENT.value,
            kind=MessageKind.TEMPLATE.value,
            purpose=OutreachPurpose.FIRST_TOUCH.value,
            template_name="intro",
            template_params=[store.leads[lid].name[:25], f"فرعكم في {store.leads[lid].city}"],
            body=f"أهلاً {store.leads[lid].name[:25]}! معكم مصنع لتل ستارز لملابس الأطفال بالجملة...",
            status=MessageStatus.READ.value,
            provider_message_id=f"wamid.mock.out.{c_idx}",
            sent_at=_ts(-3, 1),
            redirected_to="+201000009901",
            agent_run_id=outreach_run_1,
            rationale="Matched target category and high rating in Cairo/Giza.",
            created_at=_ts(-3, 1),
        )
        m_in = _uid("msg_in", c_idx)
        store.messages[m_in] = MockMessage(
            id=m_in,
            tenant_id=T1_ID,
            conversation_id=conv_id,
            lead_id=lid,
            direction=MessageDirection.INBOUND.value,
            channel=ChannelType.WHATSAPP.value,
            author=MessageAuthor.LEAD.value,
            kind=MessageKind.TEXT.value,
            body=inbound_text,
            status=MessageStatus.RECEIVED.value,
            provider_message_id=f"wamid.mock.in.{c_idx}",
            reply_intent=intent.value,
            sent_at=_ts(-2, 2),
            created_at=_ts(-2, 2),
        )

    # Pending approval outreach messages (for leads 8, 9 -> QUEUED)
    for q_idx, lead_num in enumerate((8, 9, 10), start=1):
        lid = _uid("lead", lead_num)
        conv_id = _uid("conv_q", q_idx)
        store.conversations[conv_id] = MockConversation(
            id=conv_id,
            tenant_id=T1_ID,
            lead_id=lid,
            channel=ChannelType.WHATSAPP.value,
            contact_value=f"+20100000{lead_num:04d}",
            created_at=_ts(-1),
        )
        mid = _uid("msg_pending", q_idx)
        lead_obj = store.leads[lid]
        p1 = lead_obj.name.split("-")[0].strip()[:25]
        p2 = f"تقييمكم المميز ({lead_obj.rating}★) في {lead_obj.city}"
        store.messages[mid] = MockMessage(
            id=mid,
            tenant_id=T1_ID,
            conversation_id=conv_id,
            lead_id=lid,
            direction=MessageDirection.OUTBOUND.value,
            channel=ChannelType.WHATSAPP.value,
            author=MessageAuthor.AGENT.value,
            kind=MessageKind.TEMPLATE.value,
            purpose=OutreachPurpose.FIRST_TOUCH.value,
            template_name="intro",
            template_params=[p1, p2],
            body=f"أهلاً {p1}! معكم مصنع لتل ستارز لملابس الأطفال بالجملة. لاحظنا {p2} وحابين نعرض عليكم أحدث تشكيلة قطن 100% بحد أدنى مرن 24 قطعة. للرد بالإلغاء ابعت STOP.",
            status=MessageStatus.PENDING_APPROVAL.value,
            agent_run_id=outreach_run_2,
            rationale=f"High-fit kids store in {lead_obj.city} ({lead_obj.governorate}), score {lead_obj.score}/10.",
            created_at=_ts(-1, q_idx),
        )

    # Assisted messages awaiting manual send (leads 11, 12)
    for a_idx, lead_num in enumerate((11, 12), start=1):
        lid = _uid("lead", lead_num)
        conv_id = _uid("conv_a", a_idx)
        store.conversations[conv_id] = MockConversation(
            id=conv_id,
            tenant_id=T1_ID,
            lead_id=lid,
            channel=ChannelType.WHATSAPP.value,
            contact_value=f"+20100000{lead_num:04d}",
            created_at=_ts(-1),
        )
        mid = _uid("msg_assisted", a_idx)
        lead_obj = store.leads[lid]
        store.messages[mid] = MockMessage(
            id=mid,
            tenant_id=T1_ID,
            conversation_id=conv_id,
            lead_id=lid,
            direction=MessageDirection.OUTBOUND.value,
            channel=ChannelType.WHATSAPP.value,
            author=MessageAuthor.AGENT.value,
            kind=MessageKind.ASSISTED.value,
            purpose=OutreachPurpose.FIRST_TOUCH.value,
            body=f"أهلاً بحضرتك في {lead_obj.name.split('-')[0].strip()}! معاكم أحمد من مصنع لتل ستارز لملابس الأطفال في العاشر من رمضان. عندنا تشكيلة قطن جديدة بحد أدنى 24 قطعة وشحن مجاني لـ {lead_obj.city}. تحب أبعتلك الكتالوج؟",
            status=MessageStatus.AWAITING_MANUAL_SEND.value,
            agent_run_id=outreach_run_2,
            rationale=f"Personalized assisted opener referencing {lead_obj.city}.",
            created_at=_ts(0, -1),
        )

    # Notifications (unread + read)
    notif_specs = [
        (
            "wants_management",
            "عميل يطلب التحدث مع الإدارة",
            "Baby House Maadi طلب التواصل مع صاحب المصنع.",
            _uid("lead", 4),
            False,
            -1,
        ),
        (
            "wants_offer",
            "طلب عرض سعر وخصم",
            "Coco Kids Boutique يسأل عن خصم 10% لـ 250 قطعة.",
            _uid("lead", 3),
            False,
            -1,
        ),
        (
            "hot_lead",
            "عميل مهتم جداً (Hot Lead)",
            "Mini Star Baby طلب تفاصيل أقل كمية والأسعار.",
            _uid("lead", 2),
            False,
            -2,
        ),
        (
            "needs_approval",
            "3 رسائل بانتظار الموافقة",
            "توجد 3 رسائل تواصل جاهزة للمراجعة في قائمة الاعتماد.",
            None,
            False,
            -1,
        ),
        (
            "run_failed",
            "فشل تشغيل مهمة البحث",
            "توقف البحث في Google Places بسبب حد الاستخدام (429).",
            None,
            True,
            -2,
        ),
    ]
    for n_idx, (n_kind, title, body, lid, is_read, d_off) in enumerate(notif_specs, start=1):
        nid = _uid("notif", n_idx)
        store.notifications[nid] = MockNotification(
            id=nid,
            tenant_id=T1_ID,
            kind=n_kind,
            title=title,
            body=body,
            lead_id=lid,
            read_at=_ts(d_off, 2) if is_read else None,
            telegram_sent_at=_ts(d_off, 1),
            created_at=_ts(d_off, 1),
        )

    # Notes & Outcomes
    note_specs = [
        (_uid("lead", 1), "تم تأكيد أول طلب جملة بـ 100 قطعة قطن أطفال مع التوصيل لمدينة نصر."),
        (_uid("lead", 3), "العميل مهتم بكمية كبيرة (250 قطعة)، يحتاج عرض سعر رسمي بخصم 8%."),
        (_uid("lead", 4), "يرجى اتصال المدير العام بالعميل اليوم الساعة 3 عصراً."),
    ]
    for idx, (lid, body) in enumerate(note_specs, start=1):
        nid = _uid("note", idx)
        store.notes[nid] = MockLeadNote(
            id=nid,
            tenant_id=T1_ID,
            lead_id=lid,
            author_user_id=T1_OWNER_ID,
            body=body,
            created_at=_ts(-2, idx),
        )

    outcome_specs = [
        (_uid("lead", 1), "won", 28500.0, "اول طلب جملة 100 قطعة أطقم خروج"),
        (_uid("lead", 33), "won", 42000.0, "طلب موسمي 150 قطعة لفروع المهندسين"),
        (_uid("lead", 20), "lost", None, "العميل يفضل التعامل بالآجل لمدة 60 يوم"),
    ]
    for idx, (lid, out, val, reason) in enumerate(outcome_specs, start=1):
        oid = _uid("outcome", idx)
        store.outcomes[oid] = MockLeadOutcome(
            id=oid,
            tenant_id=T1_ID,
            lead_id=lid,
            outcome=out,
            value_egp=val,
            reason=reason,
            created_at=_ts(-1, idx),
        )

    # Learned Insights (v1 historical, v2 active)
    ins1_id = _uid("insight", 1)
    ins2_id = _uid("insight", 2)
    store.insights[ins1_id] = MockLearnedInsight(
        id=ins1_id,
        tenant_id=T1_ID,
        version=1,
        insights=[
            "محلات ملابس الأطفال في مدينة نصر والمهندسين حققت أعلى معدل رد (45%).",
            "المتاجر التي لديها أكثر من 50 تقييم على Google Maps تستجيب أسرع بمعدل الضعف.",
        ],
        stats={"total_outcomes": 2, "win_rate": 0.5},
        is_active=False,
        created_at=_ts(-5),
    )
    store.insights[ins2_id] = MockLearnedInsight(
        id=ins2_id,
        tenant_id=T1_ID,
        version=2,
        insights=[
            "المحلات المتخصصة (kids clothing store / baby store) تحقق معدل تحويل أعلى بـ 3 أضعاف من محلات الملابس العامة.",
            "ذكر الحد الأدنى المرن للطلب (24 قطعة) في الرسالة الأولى رفع الردود الإيجابية إلى 38%.",
            "المحلات ذات التقييم 4.5+ في القاهرة الجديدة والمهندسين تميل لطلبات باكدجات الجملة الكبيرة.",
            "العملاء في شبرا يفضلون الدفع عند الاستلام عن التحويل البنكي المسبق.",
        ],
        stats={"total_outcomes": 3, "win_rate": 0.67, "avg_reply_minutes": 42},
        is_active=True,
        created_at=_ts(-1),
    )

    # --- Tenant 2: Isolated second tenant for tenant-isolation tests ---
    store.tenants[T2_ID] = MockTenant(id=T2_ID, name="Cairo MedTech Supplies", created_at=_ts(-10))
    store.users[T2_OWNER_ID] = MockUser(
        id=T2_OWNER_ID,
        tenant_id=T2_ID,
        email="medtech@example.com",
        password="MedTech123!",
        full_name="د. طارق منصور (Dr. Tarek Mansour)",
        role="owner",
        created_at=_ts(-10),
    )
    s2_id = _uid("settings", 2)
    store.settings[s2_id] = MockBusinessSettings(
        id=s2_id,
        tenant_id=T2_ID,
        company_name="Cairo MedTech Supplies",
        description="توريد المستلزمات الطبية للعيادات والمراكز الطبية.",
        onboarding_completed=True,
        updated_at=_ts(-5),
    )
    t2_lead_id = _uid("lead_t2", 1)
    store.leads[t2_lead_id] = MockLead(
        id=t2_lead_id,
        tenant_id=T2_ID,
        name="عيادة النور التخصصية",
        category="medical clinic",
        governorate="Cairo",
        city="Dokki",
        status=LeadStatus.NEW.value,
        ref_code="MT0001",
        dedupe_key="manual:mt-1",
        created_at=_ts(-2),
    )
