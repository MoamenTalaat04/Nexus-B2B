"""Shared test fixtures.

- Mocks are forced on (no real external APIs in unit tests).
- A separate database `<name>_test` is created once per test session; the schema is built from the models.
- Each test runs inside a transaction that is rolled back, so tests never see each other's data.
- `client` is an httpx AsyncClient wired to the app, using the same rolled-back session.
"""

import os

# Force safe settings BEFORE the app (and its settings) are imported.
os.environ["USE_MOCK_ADAPTERS"] = "true"
os.environ["USE_MOCK_LLM"] = "true"
os.environ.setdefault("JWT_SECRET", "test-secret")

from collections.abc import AsyncIterator

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app import models  # noqa: F401  (register all models)
from app.config import settings
from app.db import get_session
from app.main import app
from app.models.base import Base

_base_url = make_url(settings.DATABASE_URL)
TEST_DB_NAME = f"{_base_url.database}_test"
TEST_DATABASE_URL = _base_url.set(database=TEST_DB_NAME)


async def _ensure_test_database() -> None:
    conn = await asyncpg.connect(
        user=_base_url.username,
        password=_base_url.password,
        host=_base_url.host,
        port=_base_url.port or 5432,
        database="postgres",
    )
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", TEST_DB_NAME)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
    finally:
        await conn.close()


@pytest.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    await _ensure_test_database()
    eng = create_async_engine(TEST_DATABASE_URL)
    async with eng.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """A session whose work is rolled back after the test (commits become savepoints)."""
    async with engine.connect() as conn:
        trans = await conn.begin()
        sess = AsyncSession(bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint")
        try:
            yield sess
        finally:
            await sess.close()
            await trans.rollback()


@pytest.fixture
async def client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def _override() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = _override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_session, None)
