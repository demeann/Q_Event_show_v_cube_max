"""Smoke-тесты ORM-моделей: проверяем, что метадата собрана корректно
и таблицы заявлены в нужной форме."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _required_env(monkeypatch):
    """Минимальные env-переменные, чтобы Settings не падал при импорте моделей."""
    monkeypatch.setenv("BOT_TOKEN", "1234567890:test_token_value")
    monkeypatch.setenv("DB_NAME", "test_db")
    monkeypatch.setenv("DB_USER", "test_user")
    monkeypatch.setenv("DB_PASSWORD", "test_pass")
    monkeypatch.setenv("GAME_START_DATE_MSK", "2026-05-15")
    from app.core.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_metadata_has_expected_tables():
    from app.db.base import Base
    from app.db import models  # noqa: F401  -- регистрирует модели в metadata

    table_names = set(Base.metadata.tables.keys())
    assert {"users", "rounds"}.issubset(table_names), table_names


def test_users_columns():
    from app.db.base import Base
    from app.db import models  # noqa: F401

    users = Base.metadata.tables["users"]
    cols = {c.name for c in users.columns}
    expected = {
        "id",
        "telegram_user_id",
        "tg_username",
        "email",
        "email_domain",
        "email_verified_at",
        "is_admin",
        "is_blocked",
        "created_at",
        "updated_at",
    }
    assert expected.issubset(cols), f"missing: {expected - cols}"

    # `unique=True` в mapped_column создаёт UNIQUE-индекс на колонке.
    assert users.columns["telegram_user_id"].unique is True


def test_rounds_columns():
    from app.db.base import Base
    from app.db import models  # noqa: F401

    rounds = Base.metadata.tables["rounds"]
    cols = {c.name for c in rounds.columns}
    expected = {"id", "code", "name", "starts_at", "ends_at", "status", "created_at", "updated_at"}
    assert expected.issubset(cols), f"missing: {expected - cols}"

    assert rounds.columns["code"].unique is True


def test_round_enums_present():
    from app.db.models import RoundCode, RoundStatus

    assert {e.value for e in RoundCode} == {"R1", "R2", "R3"}
    assert {e.value for e in RoundStatus} == {"SCHEDULED", "ACTIVE", "FINISHED"}


def test_user_default_admin_blocked_false():
    from app.db.models import User

    u = User(telegram_user_id=12345)
    # Python-side defaults срабатывают на flush, но столбцы должны иметь default=False.
    col_admin = User.__table__.columns["is_admin"]
    col_blocked = User.__table__.columns["is_blocked"]
    assert col_admin.default.arg is False
    assert col_blocked.default.arg is False
