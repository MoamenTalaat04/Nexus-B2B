"""P0-2: the Alembic chain upgrades an empty database to the models' schema and downgrades back to nothing."""

import asyncio

import asyncpg
import pytest
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command
from app.config import settings
from app.models.base import Base

BACKEND_DIR = __import__("pathlib").Path(__file__).resolve().parents[1]


async def _recreate(url_str: str) -> None:
    url = make_url(url_str)
    conn = await asyncpg.connect(
        user=url.username, password=url.password, host=url.host, port=url.port or 5432, database="postgres"
    )
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{url.database}"')
        await conn.execute(f'CREATE DATABASE "{url.database}"')
    finally:
        await conn.close()


async def _tables(url_str: str) -> set[str]:
    engine = create_async_engine(url_str)
    try:
        async with engine.connect() as conn:
            names = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
    finally:
        await engine.dispose()
    return names - {"alembic_version"}


@pytest.fixture
def migration_url(monkeypatch: pytest.MonkeyPatch) -> str:
    url = make_url(settings.DATABASE_URL)
    test_url = url.set(database=f"{url.database}_migrations").render_as_string(hide_password=False)
    monkeypatch.setattr(settings, "DATABASE_URL", test_url)
    return test_url


async def test_upgrade_and_downgrade_on_empty_db(migration_url: str) -> None:
    await _recreate(migration_url)
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    # env.py calls asyncio.run(), so run Alembic in a worker thread (outside this event loop).
    await asyncio.to_thread(command.upgrade, cfg, "head")
    assert await _tables(migration_url) == set(Base.metadata.tables)
    await asyncio.to_thread(command.downgrade, cfg, "base")
    assert await _tables(migration_url) == set()
    await asyncio.to_thread(command.upgrade, cfg, "head")  # and up again: downgrades leave nothing behind
    assert await _tables(migration_url) == set(Base.metadata.tables)
