"""Окружение Alembic.

Использует sync-DSN (`mysql+pymysql://...`), metadata — из `app.db.base.Base`.

Порядок выбора URL (чтобы миграции не требовали `BOT_TOKEN` и прочего из бота):

1. :envvar:`ALEMBIC_DATABASE_URL` — явный URL (тесты, отладка).
2. Переменные :envvar:`DB_HOST` / :envvar:`DB_PORT` / :envvar:`DB_NAME` /
   :envvar:`DB_USER` / :envvar:`DB_PASSWORD` после загрузки корневого ``.env``
   (достаточно для ``alembic upgrade head``).
3. Полный :class:`app.core.config.Settings` (как у запущенного бота).
"""

from __future__ import annotations

import os
from logging.config import fileConfig
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

from alembic import context
from sqlalchemy import engine_from_config, pool

# Импорт моделей нужен, чтобы Base.metadata содержала все таблицы.
from app.db.base import Base
from app.db import models  # noqa: F401  -- регистрация моделей в metadata

# .../app/db/migrations/env.py → корень репозитория: migrations → db → app → корень
_PROJECT_ROOT = Path(__file__).resolve().parents[3]

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _load_env_files() -> None:
    """Подхватить переменные из .env (не перетирать уже выставленные в shell)."""
    root_env = _PROJECT_ROOT / ".env"
    cwd_env = Path.cwd() / ".env"
    if root_env.is_file():
        load_dotenv(root_env, override=False)
    if cwd_env.is_file() and cwd_env.resolve() != root_env.resolve():
        load_dotenv(cwd_env, override=False)
    # Последний шанс — «умный» поиск .env от текущей директории
    if not root_env.is_file() and not cwd_env.is_file():
        load_dotenv(override=False)


def _build_mysql_sync_dsn_from_db_env() -> str | None:
    """Собрать DSN из переменных окружения (без валидации всего Settings)."""
    db_name = os.getenv("DB_NAME")
    db_user = os.getenv("DB_USER")
    # пароль может быть пустой строкой на некоторых хостингах
    if db_name is None or db_user is None or "DB_PASSWORD" not in os.environ:
        return None

    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "3306")
    password = os.getenv("DB_PASSWORD", "")

    return (
        f"mysql+pymysql://{quote_plus(db_user)}:{quote_plus(password)}"
        f"@{host}:{port}/{quote_plus(db_name)}?charset=utf8mb4"
    )


def _resolve_sqlalchemy_url() -> str:
    _load_env_files()

    override_url = os.getenv("ALEMBIC_DATABASE_URL")
    if override_url:
        return override_url

    db_url = _build_mysql_sync_dsn_from_db_env()
    if db_url:
        return db_url

    from app.core.config import get_settings

    try:
        return get_settings().db_dsn_sync
    except Exception as e:
        root_env = _PROJECT_ROOT / ".env"
        cwd_env = Path.cwd() / ".env"
        checks = [
            f"ожидался .env в корне репозитория: {root_env} "
            f"({'есть' if root_env.is_file() else 'нет файла'})",
            f".env в текущей директории ({cwd_env}): "
            f"{'есть' if cwd_env.is_file() else 'нет файла'}",
            f"DB_NAME={'задан' if os.getenv('DB_NAME') else 'не задан'}",
            f"DB_USER={'задан' if os.getenv('DB_USER') else 'не задан'}",
            f"DB_PASSWORD={'ключ в окружении есть' if 'DB_PASSWORD' in os.environ else 'нет ключа DB_PASSWORD'}",
        ]
        raise RuntimeError(
            "Alembic: не удалось получить URL БД.\n"
            "Скопируй `.env.example` → `.env` в корень `Q_Event_show_v_cube`, "
            "заполни DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD и снова "
            "запусти `alembic upgrade head` из корня репозитория.\n"
            "Либо выставь одну переменную ALEMBIC_DATABASE_URL=mysql+pymysql://...\n"
            "\nПроверки:\n• "
            + "\n• ".join(checks)
        ) from e


config.set_main_option("sqlalchemy.url", _resolve_sqlalchemy_url())

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Сгенерировать SQL без подключения к БД."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Применить миграции к реальной БД."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
