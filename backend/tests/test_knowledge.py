import uuid
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from docx import Document
from pypdf import PdfWriter
from starlette.datastructures import UploadFile

import app.api.knowledge as knowledge_api
import app.services.knowledge as knowledge_service
from app.core.errors import AppError
from app.core.security import CurrentUser
from app.schemas.knowledge import KnowledgeFileOut
from app.services.knowledge import (
    _build_knowledge_text,
    _KnowledgeBlock,
    _split_paragraphs,
    extract_knowledge_text,
    is_scanned_pdf,
    normalize_search_text,
)


def test_extract_markdown_preserves_arabic(tmp_path: Path) -> None:
    path = tmp_path / "arabic.md"
    path.write_text("شركة النجم\nملابس أطفال\n", encoding="utf-8")
    assert extract_knowledge_text(path, "text/markdown") == "شركة النجم\nملابس أطفال"


def test_extract_docx_preserves_arabic(tmp_path: Path) -> None:
    path = tmp_path / "company.docx"
    document = Document()
    document.add_paragraph("شركة النجم")
    document.add_paragraph("ملابس أطفال بالجملة")
    document.save(path)
    assert extract_knowledge_text(path, "application/docx") == "شركة النجم\nملابس أطفال بالجملة"


def test_extract_txt_preserves_arabic(tmp_path: Path) -> None:
    path = tmp_path / "arabic.txt"
    path.write_text("الملابس بالجملة\nشركة النجم", encoding="utf-8")
    assert extract_knowledge_text(path, "text/plain") == "الملابس بالجملة\nشركة النجم"


def test_extract_pdf_with_actual_text(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "company.pdf"
    path.write_bytes(b"%PDF-1.4\n")

    class FakePage:
        @staticmethod
        def extract_text() -> str:
            return "شركة النجم\nملابس أطفال"

    class FakeReader:
        def __init__(self, _: str) -> None:
            self.pages = [FakePage()]

    monkeypatch.setattr(knowledge_service, "PdfReader", FakeReader)
    assert extract_knowledge_text(path, "application/pdf") == "شركة النجم\nملابس أطفال"


def test_extract_blank_pdf_is_scanned(tmp_path: Path) -> None:
    path = tmp_path / "scanned.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    with path.open("wb") as output:
        writer.write(output)

    text = extract_knowledge_text(path, "application/pdf")
    assert text == ""
    assert is_scanned_pdf(text)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", True),
        ("x" * 19, True),
        ("x" * 20, False),
    ],
)
def test_scanned_pdf_threshold(text: str, expected: bool) -> None:
    assert is_scanned_pdf(text) is expected


def test_arabic_normalization_uses_real_unicode() -> None:
    source = "أخبار وإعلانات وآراء الأطفال ةى"
    assert normalize_search_text(source) == "اخبار واعلانات واراء الاطفال هي"


@pytest.mark.parametrize(
    ("variant", "equivalent"),
    [
        ("أمل", "امل"),
        ("إدارة", "اداره"),
        ("آمان", "امان"),
        ("مدرسة", "مدرسه"),
        ("مكتبة", "مكتبه"),
        ("مستشفى", "مستشفي"),
    ],
)
def test_arabic_spelling_variants_normalize(variant: str, equivalent: str) -> None:
    assert normalize_search_text(variant) == normalize_search_text(equivalent)


def test_arabic_diacritics_are_removed() -> None:
    assert normalize_search_text("مَلَابِسُ أَطْفَال") == "ملابس اطفال"


def test_english_is_lowercased() -> None:
    assert normalize_search_text("Kids Clothing") == "kids clothing"


def test_long_paragraph_split_preserves_text_and_limit() -> None:
    original = ("ملابس أطفال بالجملة وخدمة عملاء سريعة. " * 30) + "\n\n" + ("٢ سعر وتسليم" * 30)
    chunks = _split_paragraphs(original)
    assert chunks
    assert all(chunk and len(chunk) <= 800 for chunk in chunks)
    assert "".join(chunks) == original


def test_short_paragraph_is_one_chunk() -> None:
    text = "شركة النجم لملابس الأطفال."
    assert _split_paragraphs(text) == [text]


def test_knowledge_text_prioritizes_complete_blocks() -> None:
    blocks = [
        _KnowledgeBlock("أول.md", "نص كامل"),
        _KnowledgeBlock("ثاني.md", "نص آخر"),
    ]
    result = _build_knowledge_text(blocks, max_chars=200)
    assert result == "### أول.md\nنص كامل\n\n### ثاني.md\nنص آخر"


def test_knowledge_text_never_exceeds_limit_or_includes_partial_block() -> None:
    blocks = [
        _KnowledgeBlock("أول.md", "A" * 60),
        _KnowledgeBlock("ثاني.md", "B" * 60),
    ]
    result = _build_knowledge_text(blocks, max_chars=80)
    assert len(result) <= 80
    assert "ثاني.md" not in result
    assert "A" * 61 not in result


def test_knowledge_text_zero_limit() -> None:
    assert _build_knowledge_text([_KnowledgeBlock("a.md", "text")], max_chars=0) == ""


def test_complete_omission_note_is_included_when_it_fits() -> None:
    blocks = [
        _KnowledgeBlock("a.md", "A" * 10),
        _KnowledgeBlock("b.md", "B" * 100),
    ]
    result = _build_knowledge_text(blocks, max_chars=45)
    assert len(result) <= 45
    assert "[Omitted files: b.md]" in result
    assert "B" not in result


def test_omission_note_is_added_by_removing_trailing_block() -> None:
    blocks = [
        _KnowledgeBlock("a.md", "A" * 30),
        _KnowledgeBlock("b.md", "B" * 30),
        _KnowledgeBlock("c.md", "C" * 30),
    ]
    result = _build_knowledge_text(blocks, max_chars=75)
    assert "### a.md" in result
    assert "### b.md" not in result
    assert "### c.md" not in result
    assert "[Omitted files:" in result
    assert "b.md" in result
    assert "c.md" in result
    assert len(result) <= 75


def test_omission_note_is_not_partial_or_over_limit() -> None:
    blocks = [
        _KnowledgeBlock("a.md", "A" * 20),
        _KnowledgeBlock("b.md", "B" * 20),
        _KnowledgeBlock("c.md", "C" * 20),
    ]
    result = _build_knowledge_text(blocks, max_chars=60)
    assert len(result) <= 60
    if "[Omitted files:" in result:
        assert result.endswith("]")


def test_knowledge_file_out_accepts_orm_attributes() -> None:
    row = SimpleNamespace(
        id=uuid.uuid4(),
        filename="شركة.md",
        mime_type="text/markdown",
        size_bytes=100,
        char_count=50,
        status="ready",
        error=None,
        created_at=datetime.now(UTC),
    )
    output = KnowledgeFileOut.model_validate(row)
    assert output.filename == "شركة.md"


class _FakeField:
    def __init__(self, name: str) -> None:
        self.name = name

    def __eq__(self, other: object) -> tuple[str, object]:
        return (self.name, other)

    def asc(self) -> tuple[str, str]:
        return (self.name, "asc")


class _FakeKnowledgeModel:
    tenant_id = _FakeField("tenant_id")
    status = _FakeField("status")
    created_at = _FakeField("created_at")
    id = _FakeField("id")


class _FakeSelect:
    def __init__(self) -> None:
        self.criteria: list[object] = []
        self.ordering: list[object] = []

    def where(self, *criteria: object) -> "_FakeSelect":
        self.criteria.extend(criteria)
        return self

    def order_by(self, *ordering: object) -> "_FakeSelect":
        self.ordering.extend(ordering)
        return self


class _FakeScalars:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self.rows = rows

    def all(self) -> list[SimpleNamespace]:
        return self.rows


class _FakeResult:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self.rows = rows

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self.rows)


class _TenantRowsSession:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self.rows = rows
        self.last_query: _FakeSelect | None = None

    async def execute(self, query: _FakeSelect) -> _FakeResult:
        self.last_query = query
        tenant_id = None
        for criterion in query.criteria:
            if isinstance(criterion, tuple) and criterion[0] == "tenant_id":
                tenant_id = criterion[1]
        matching = [
            row
            for row in self.rows
            if (tenant_id is None or row.tenant_id == tenant_id)
            and getattr(row, "status", "ready") == "ready"
        ]
        matching.sort(key=lambda row: (row.created_at, str(row.id)))
        return _FakeResult(matching)


@pytest.fixture
def mock_knowledge_queries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(knowledge_service, "_knowledge_model", lambda: _FakeKnowledgeModel)
    monkeypatch.setattr(knowledge_service, "select", lambda _: _FakeSelect())


@pytest.mark.asyncio
async def test_get_knowledge_text_preserves_created_at_order(mock_knowledge_queries: None) -> None:
    tenant_id = uuid.uuid4()
    older = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        filename="old.md",
        extracted_text="النص الأول",
        status="ready",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    newer = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        filename="new.md",
        extracted_text="النص الثاني",
        status="ready",
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    session = _TenantRowsSession([newer, older])

    result = await knowledge_service.get_knowledge_text(session, tenant_id, max_chars=200)

    assert result.index("النص الأول") < result.index("النص الثاني")
    assert "### old.md" in result
    assert "### new.md" in result
    assert session.last_query is not None


@pytest.mark.asyncio
async def test_get_knowledge_text_tenant_isolation(mock_knowledge_queries: None) -> None:
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    session = _TenantRowsSession(
        [
            SimpleNamespace(
                id=uuid.uuid4(),
                tenant_id=tenant_a,
                filename="same.md",
                extracted_text="بيانات العميل A",
                status="ready",
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            ),
            SimpleNamespace(
                id=uuid.uuid4(),
                tenant_id=tenant_b,
                filename="same.md",
                extracted_text="بيانات العميل B",
                status="ready",
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            ),
        ]
    )

    tenant_a_text = await knowledge_service.get_knowledge_text(session, tenant_a)
    tenant_b_text = await knowledge_service.get_knowledge_text(session, tenant_b)

    assert "بيانات العميل A" in tenant_a_text
    assert "بيانات العميل B" not in tenant_a_text
    assert "بيانات العميل B" in tenant_b_text
    assert "بيانات العميل A" not in tenant_b_text


@pytest.mark.asyncio
async def test_search_knowledge_real_arabic_and_ranking(mock_knowledge_queries: None) -> None:
    tenant_id = uuid.uuid4()
    session = _TenantRowsSession(
        [
            SimpleNamespace(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                filename="general.md",
                extracted_text="ملابس أطفال، توجد أسعار الجملة والتوصيل.",
                status="ready",
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            ),
            SimpleNamespace(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                filename="prices.md",
                extracted_text="أسعار ملابس الأطفال بالجملة في القاهرة.",
                status="ready",
                created_at=datetime(2026, 1, 2, tzinfo=UTC),
            ),
        ]
    )

    results = await knowledge_service.search_knowledge(session, tenant_id, "أسعار ملابس أطفال", k=2)

    assert results
    assert "ملابس" in results[0]
    assert all("الأطفال" not in result or "ملابس" in result for result in results)


@pytest.mark.asyncio
async def test_search_knowledge_respects_k_and_deterministic_ranking(mock_knowledge_queries: None) -> None:
    tenant_id = uuid.uuid4()
    rows = [
        SimpleNamespace(
            id=uuid.UUID("00000000-0000-0000-0000-000000000003"),
            tenant_id=tenant_id,
            filename="z.md",
            extracted_text="ملابس أطفال",
            status="ready",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
        SimpleNamespace(
            id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            tenant_id=tenant_id,
            filename="a.md",
            extracted_text="ملابس أطفال",
            status="ready",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
        SimpleNamespace(
            id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
            tenant_id=tenant_id,
            filename="b.md",
            extracted_text="ملابس",
            status="ready",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
    ]
    session = _TenantRowsSession(rows)

    results = await knowledge_service.search_knowledge(session, tenant_id, "ملابس أطفال", k=2)

    assert len(results) == 2
    assert results[0].startswith("a.md:")
    assert results[1].startswith("z.md:")


@pytest.mark.asyncio
async def test_search_knowledge_tenant_isolation(mock_knowledge_queries: None) -> None:
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    session = _TenantRowsSession(
        [
            SimpleNamespace(
                id=uuid.uuid4(),
                tenant_id=tenant_a,
                filename="same.md",
                extracted_text="ملابس أطفال خاصة بعميل ألف",
                status="ready",
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            ),
            SimpleNamespace(
                id=uuid.uuid4(),
                tenant_id=tenant_b,
                filename="same.md",
                extracted_text="ملابس أطفال خاصة بعميل باء",
                status="ready",
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            ),
        ]
    )

    tenant_a_results = await knowledge_service.search_knowledge(session, tenant_a, "ملابس")
    tenant_b_results = await knowledge_service.search_knowledge(session, tenant_b, "ملابس")

    assert any("ألف" in result for result in tenant_a_results)
    assert not any("باء" in result for result in tenant_a_results)
    assert any("باء" in result for result in tenant_b_results)
    assert not any("ألف" in result for result in tenant_b_results)


class _FakeKnowledgeRow:
    def __init__(self, **kwargs: Any) -> None:
        self.id = kwargs.get("id", uuid.uuid4())
        self.tenant_id = kwargs["tenant_id"]
        self.filename = kwargs["filename"]
        self.mime_type = kwargs["mime_type"]
        self.size_bytes = kwargs["size_bytes"]
        self.storage_path = kwargs["storage_path"]
        self.extracted_text = kwargs.get("extracted_text")
        self.char_count = kwargs.get("char_count", 0)
        self.status = kwargs.get("status", "processing")
        self.error = kwargs.get("error")
        self.created_at = kwargs.get("created_at", datetime.now(UTC))


class _FakeKnowledgeSession:
    def __init__(self) -> None:
        self.added: list[_FakeKnowledgeRow] = []
        self.deleted: list[_FakeKnowledgeRow] = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, row: _FakeKnowledgeRow) -> None:
        self.added.append(row)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1

    async def refresh(self, row: _FakeKnowledgeRow) -> None:
        return None

    async def delete(self, row: _FakeKnowledgeRow) -> None:
        self.deleted.append(row)


def _upload_file(filename: str, data: bytes) -> UploadFile:
    return UploadFile(filename=filename, file=BytesIO(data))


def _user(tenant_id: uuid.UUID) -> CurrentUser:
    return CurrentUser(user_id=uuid.uuid4(), tenant_id=tenant_id, role="owner")


@pytest.mark.asyncio
async def test_upload_markdown(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    tenant_id = uuid.uuid4()
    session = _FakeKnowledgeSession()
    monkeypatch.setattr(knowledge_api.settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(knowledge_api, "_count_tenant_files", lambda *_: _async_value(0))
    monkeypatch.setattr(knowledge_api, "_knowledge_model", lambda: _FakeKnowledgeRow)

    output = await knowledge_api.upload_knowledge(
        file=_upload_file("شركة.md", "شركة النجم\nملابس أطفال".encode()),
        user=_user(tenant_id),
        session=session,
    )

    assert output.filename == "شركة.md"
    assert output.status == "ready"
    assert output.char_count > 0
    assert output.preview
    assert session.commits == 1
    assert session.added


def _async_value(value: Any):
    async def run(*_: Any, **__: Any) -> Any:
        return value

    return run()


@pytest.mark.asyncio
async def test_short_txt_is_not_marked_scanned(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    tenant_id = uuid.uuid4()
    session = _FakeKnowledgeSession()
    monkeypatch.setattr(knowledge_api.settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(knowledge_api, "_count_tenant_files", lambda *_: _async_value(0))
    monkeypatch.setattr(knowledge_api, "_knowledge_model", lambda: _FakeKnowledgeRow)

    output = await knowledge_api.upload_knowledge(
        file=_upload_file("short.txt", b"Hi"),
        user=_user(tenant_id),
        session=session,
    )

    assert output.status == "ready"
    assert output.error is None


@pytest.mark.asyncio
async def test_failed_extraction_preserves_failed_row(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tenant_id = uuid.uuid4()
    session = _FakeKnowledgeSession()
    monkeypatch.setattr(knowledge_api.settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(knowledge_api, "_count_tenant_files", lambda *_: _async_value(0))
    monkeypatch.setattr(knowledge_api, "_knowledge_model", lambda: _FakeKnowledgeRow)
    monkeypatch.setattr(
        knowledge_api,
        "extract_knowledge_text",
        lambda *_: (_ for _ in ()).throw(knowledge_api.KnowledgeExtractionError("extraction_failed")),
    )

    output = await knowledge_api.upload_knowledge(
        file=_upload_file("broken.pdf", b"%PDF-1.4 broken"),
        user=_user(tenant_id),
        session=session,
    )

    assert output.status == "failed"
    assert output.error == "extraction_failed"
    assert session.commits == 1


@pytest.mark.asyncio
async def test_model_integration_failure_removes_moved_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tenant_id = uuid.uuid4()
    session = _FakeKnowledgeSession()
    monkeypatch.setattr(knowledge_api.settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(knowledge_api, "_count_tenant_files", lambda *_: _async_value(0))

    def missing_model() -> type[Any]:
        raise ModuleNotFoundError("app.models.knowledge")

    monkeypatch.setattr(knowledge_api, "_knowledge_model", missing_model)

    with pytest.raises(AppError) as exc:
        await knowledge_api.upload_knowledge(
            file=_upload_file("company.md", b"company"),
            user=_user(tenant_id),
            session=session,
        )

    assert exc.value.code == "knowledge_integration_error"
    tenant_dir = tmp_path / str(tenant_id)
    assert tenant_dir.exists() is False or list(tenant_dir.iterdir()) == []


@pytest.mark.asyncio
async def test_upload_rejects_invalid_type(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(knowledge_api.settings, "UPLOAD_DIR", str(tmp_path))
    with pytest.raises(AppError) as exc:
        await knowledge_api.upload_knowledge(
            file=_upload_file("notes.exe", b"bad"),
            user=_user(uuid.uuid4()),
            session=_FakeKnowledgeSession(),
        )
    assert exc.value.code == "unsupported_file_type"


@pytest.mark.asyncio
async def test_upload_rejects_over_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid.uuid4()
    monkeypatch.setattr(knowledge_api.settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(knowledge_api, "_count_tenant_files", lambda *_: _async_value(0))
    data = b"x" * (10 * 1024 * 1024 + 1)

    with pytest.raises(AppError) as exc:
        await knowledge_api.upload_knowledge(
            file=_upload_file("large.txt", data),
            user=_user(tenant_id),
            session=_FakeKnowledgeSession(),
        )
    assert exc.value.code == "file_too_large"


@pytest.mark.asyncio
async def test_upload_rejects_tenant_quota(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(knowledge_api.settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(knowledge_api, "_count_tenant_files", lambda *_: _async_value(20))

    with pytest.raises(AppError) as exc:
        await knowledge_api.upload_knowledge(
            file=_upload_file("one.md", b"test"),
            user=_user(uuid.uuid4()),
            session=_FakeKnowledgeSession(),
        )
    assert exc.value.code == "knowledge_file_limit_reached"


@pytest.mark.asyncio
async def test_list_knowledge_has_preview_and_no_full_text(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid.uuid4()
    row = _FakeKnowledgeRow(
        tenant_id=tenant_id,
        filename="company.md",
        mime_type="text/markdown",
        size_bytes=500,
        storage_path="/tmp/never-exposed",
        extracted_text="A" * 500,
        char_count=500,
        status="ready",
        error=None,
    )
    seen: list[uuid.UUID] = []

    async def fake_list(_: Any, tenant: uuid.UUID) -> list[_FakeKnowledgeRow]:
        seen.append(tenant)
        return [row]

    monkeypatch.setattr(knowledge_api, "_list_tenant_files", fake_list)

    output = await knowledge_api.list_knowledge(
        user=_user(tenant_id),
        session=_FakeKnowledgeSession(),
    )

    assert seen == [tenant_id]
    assert output.total == 1
    assert len(output.items[0].preview or "") == 300
    assert "extracted_text" not in output.model_dump()
    assert "/tmp/" not in str(output.model_dump())


@pytest.mark.asyncio
async def test_delete_missing_knowledge_file(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_find(*_: Any) -> None:
        return None

    monkeypatch.setattr(knowledge_api, "_find_tenant_file", fake_find)

    with pytest.raises(AppError) as exc:
        await knowledge_api.delete_knowledge(
            file_id=uuid.uuid4(),
            user=_user(uuid.uuid4()),
            session=_FakeKnowledgeSession(),
        )
    assert exc.value.code == "knowledge_file_not_found"


@pytest.mark.asyncio
async def test_delete_tenant_owned_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    tenant_id = uuid.uuid4()
    stored = tmp_path / "company.md"
    stored.write_text("company", encoding="utf-8")
    row = _FakeKnowledgeRow(
        tenant_id=tenant_id,
        filename="company.md",
        mime_type="text/markdown",
        size_bytes=7,
        storage_path=str(stored),
        extracted_text="company",
        char_count=7,
        status="ready",
        error=None,
    )
    seen: list[tuple[uuid.UUID, uuid.UUID]] = []

    async def fake_find(_: Any, tenant: uuid.UUID, file_id: uuid.UUID) -> _FakeKnowledgeRow:
        seen.append((tenant, file_id))
        return row

    monkeypatch.setattr(knowledge_api, "_find_tenant_file", fake_find)
    session = _FakeKnowledgeSession()

    await knowledge_api.delete_knowledge(
        file_id=row.id,
        user=_user(tenant_id),
        session=session,
    )

    assert seen == [(tenant_id, row.id)]
    assert session.deleted == [row]
    assert session.commits == 1
    assert not stored.exists()
