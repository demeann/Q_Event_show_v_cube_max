"""Smoke-тесты полной схемы: проверяем, что метадата собрана корректно
(имена таблиц, ключевые UNIQUE, FK, индексы) и что её можно создать
в реальной БД (используем SQLite в памяти — без MySQL-специфики)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine


@pytest.fixture(autouse=True)
def _required_env(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "1234567890:test_token_value")
    monkeypatch.setenv("DB_NAME", "test_db")
    monkeypatch.setenv("DB_USER", "test_user")
    monkeypatch.setenv("DB_PASSWORD", "test_pass")
    monkeypatch.setenv("GAME_START_DATE_MSK", "2026-05-15")
    from app.core.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


EXPECTED_TABLES = {
    "users",
    "rounds",
    "round_questions",
    "user_round_progress",
    "user_topic_progress",
    "user_answers",
    "winner_selections",
    "winners",
    "broadcast_templates",
    "broadcasts",
    "broadcast_recipients",
    "email_validation_log",
}


def test_metadata_contains_all_expected_tables():
    from app.db.base import Base
    from app.db import models  # noqa: F401  -- регистрирует модели

    actual = set(Base.metadata.tables.keys())
    missing = EXPECTED_TABLES - actual
    assert not missing, f"Missing tables: {missing}. Actual: {actual}"


def test_metadata_can_create_all_in_sqlite():
    """Грубая проверка консистентности схемы: ORM-метадата создаётся в SQLite без ошибок."""
    from app.db.base import Base
    from app.db import models  # noqa: F401

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        from sqlalchemy import inspect

        names = set(inspect(engine).get_table_names())
        assert EXPECTED_TABLES.issubset(names), f"Missing in DB: {EXPECTED_TABLES - names}"
    finally:
        engine.dispose()


def test_unique_constraints_critical_paths():
    from app.db.base import Base
    from app.db import models  # noqa: F401

    md = Base.metadata.tables

    def has_unique(table, names):
        wanted = tuple(names)
        for cons in md[table].constraints:
            if cons.__class__.__name__ != "UniqueConstraint":
                continue
            if tuple(c.name for c in cons.columns) == wanted:
                return True
        return False

    # «Одна попытка» — гарантируется UNIQUE(user_id, question_id)
    assert has_unique("user_answers", ["user_id", "question_id"])
    # Один прогресс на (user, round)
    assert has_unique("user_round_progress", ["user_id", "round_id"])
    # Один прогресс на (user, round, topic)
    assert has_unique("user_topic_progress", ["user_id", "round_id", "topic_code"])
    # Одна селекция победителей на тур
    assert has_unique("winner_selections", ["round_id"])
    # Победитель уникален по позиции и по пользователю
    assert has_unique("winners", ["winner_selection_id", "user_id"])
    assert has_unique("winners", ["winner_selection_id", "position"])
    # Идемпотентность рассылки
    assert has_unique("broadcast_recipients", ["broadcast_id", "user_id"])


def test_enums_values():
    from app.db.models import (
        BroadcastStatus,
        BroadcastTemplateType,
        RecipientStatus,
        RoundProgressStatus,
        TopicStatus,
    )

    assert {e.value for e in RoundProgressStatus} == {
        "NOT_STARTED",
        "IN_PROGRESS",
        "FINISHED",
    }
    assert {e.value for e in TopicStatus} == {"OPEN", "CLOSED"}
    assert {e.value for e in BroadcastTemplateType} == {
        "ANNOUNCE",
        "REMINDER",
        "RESULT",
        "CUSTOM",
    }
    assert {e.value for e in BroadcastStatus} == {"PLANNED", "RUNNING", "DONE", "FAILED"}
    assert {e.value for e in RecipientStatus} == {"QUEUED", "SENT", "FAILED", "SKIPPED"}


def test_alembic_upgrade_runs_on_sqlite(tmp_path, monkeypatch):
    """Прокатываем настоящие миграции 0001 + 0002 на чистой SQLite-БД.

    Это не заменяет MySQL-проверку, но ловит синтаксические/ссылочные ошибки в миграциях.
    """
    import os
    from alembic import command
    from alembic.config import Config

    db_file = tmp_path / "alembic_test.db"
    sync_dsn = f"sqlite:///{db_file}"

    # env.py читает ALEMBIC_DATABASE_URL приоритетно, если задана.
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", sync_dsn)

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    cfg = Config(os.path.join(project_root, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(project_root, "app/db/migrations"))

    command.upgrade(cfg, "head")

    from sqlalchemy import inspect

    engine = create_engine(sync_dsn)
    try:
        names = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
    assert EXPECTED_TABLES.issubset(names), f"Missing after upgrade: {EXPECTED_TABLES - names}"
