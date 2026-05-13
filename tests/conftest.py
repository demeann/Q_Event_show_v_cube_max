"""Общие async-фикстуры: in-memory SQLite со схемой всех моделей."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Изолированная БД на время теста (commit не требуется для чтения после flush)."""
    import app.db.models  # noqa: F401 — регистрация таблиц в Base.metadata

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with Session() as session:
        yield session

    await engine.dispose()


@pytest.fixture(autouse=True)
def _env_for_settings(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "1234567890:test_token_value")
    monkeypatch.setenv("DB_NAME", "test_db")
    monkeypatch.setenv("DB_USER", "test_user")
    monkeypatch.setenv("DB_PASSWORD", "test_pass")
    monkeypatch.setenv("GAME_START_DATE_MSK", "2026-05-15")
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
