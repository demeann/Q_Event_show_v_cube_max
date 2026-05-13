"""Конфигурация приложения через pydantic-settings.

Источник значений: переменные окружения и `.env`-файл в корне проекта.
Все обязательные поля валидируются при создании `Settings`.

Пример использования::

    from app.core.config import get_settings

    settings = get_settings()
    print(settings.api_access_token[:8])
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Путь к корню проекта (на 3 уровня выше: app/core/config.py -> ../../..).
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Все настройки бота, загружаемые из окружения / .env."""

    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------- Мессенджер ----------
    # MAX: токен из кабинета MAX → Чат-боты → Интеграция (Authorization).
    max_access_token: str = Field(default="", validation_alias="MAX_ACCESS_TOKEN")
    # Telegram (наследие схемы; для инстанса MAX можно не задавать, если есть MAX_ACCESS_TOKEN).
    bot_token: str = Field(default="", validation_alias="BOT_TOKEN")
    messenger_platform: Literal["telegram", "max"] = Field(
        default="telegram",
        validation_alias="MESSENGER_PLATFORM",
    )

    # ---------- MySQL ----------
    db_host: str = "localhost"
    db_port: int = 3306
    db_name: str
    db_user: str
    db_password: str

    # ---------- Game ----------
    # Дата начала Дня 1 Тура 1 в МСК. Расписание остальных туров и рассылок
    # высчитывается от этой даты.
    game_start_date_msk: date
    # NoDecode отключает встроенный JSON-парсер pydantic-settings для list-полей,
    # чтобы наш `field_validator(mode="before")` получил сырую CSV-строку.
    allowed_email_domains: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # ---------- Access (invite link) ----------
    # INVITE_ONLY=true и непустой INVITE_START_TOKENS: первый вход только по ссылке с ?start=<token>.
    # Telegram: https://t.me/<bot>?start=<token>
    # MAX: https://max.ru/<ник_бота>?start=<token> (см. dev.max.ru — deeplinks).
    invite_only: bool = False
    invite_start_tokens: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # ---------- Admin ----------
    admin_ids: Annotated[list[int], NoDecode] = Field(default_factory=list)

    # ---------- Logging ----------
    log_level: str = "INFO"
    log_dir: Path = Path("logs")

    # ---------- Runtime ----------
    run_mode: Literal["polling", "webhook"] = "polling"
    webhook_base_url: str = ""
    webhook_path: str = "/qclub/webhook"
    # Секрет для заголовка X-Telegram-Bot-Api-Secret-Token (рекомендуется в бою).
    webhook_secret: str = ""
    webhook_listen_host: str = "127.0.0.1"
    webhook_listen_port: int = 8081

    @model_validator(mode="after")
    def _tokens_for_platform(self) -> Settings:
        bt = self.bot_token.strip()
        mt = self.max_access_token.strip()
        if self.messenger_platform == "telegram":
            if len(bt) < 10:
                raise ValueError(
                    "Для MESSENGER_PLATFORM=telegram укажите BOT_TOKEN "
                    "(строка не короче 10 символов)."
                )
        elif self.messenger_platform == "max":
            if len(mt) < 10:
                raise ValueError(
                    "Для MESSENGER_PLATFORM=max укажите MAX_ACCESS_TOKEN "
                    "(строка не короче 10 символов)."
                )
        return self

    # ---------------- Validators ----------------

    @field_validator("allowed_email_domains", mode="before")
    @classmethod
    def _parse_email_domains(cls, value):
        """Принимаем список или CSV-строку. Нормализуем в lowercase, без `@`."""
        if value is None or value == "":
            return []
        if isinstance(value, str):
            parts = [p.strip().lower().lstrip("@") for p in value.split(",")]
            return [p for p in parts if p]
        if isinstance(value, list):
            return [str(p).strip().lower().lstrip("@") for p in value if str(p).strip()]
        return value

    @field_validator("invite_start_tokens", mode="before")
    @classmethod
    def _parse_invite_tokens(cls, value):
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [p.strip() for p in value.split(",") if p.strip()]
        if isinstance(value, list):
            return [str(p).strip() for p in value if str(p).strip()]
        return value

    @field_validator("admin_ids", mode="before")
    @classmethod
    def _parse_admin_ids(cls, value):
        """Принимаем список int или CSV-строку с числами."""
        if value is None or value == "":
            return []
        if isinstance(value, str):
            parts = [p.strip() for p in value.split(",") if p.strip()]
            return [int(p) for p in parts]
        if isinstance(value, list):
            return [int(p) for p in value]
        return value

    @field_validator("log_level")
    @classmethod
    def _normalize_log_level(cls, value: str) -> str:
        normalized = value.strip().upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if normalized not in allowed:
            raise ValueError(
                f"Invalid LOG_LEVEL: {value!r}. Allowed: {sorted(allowed)}"
            )
        return normalized

    # ---------------- Computed properties ----------------

    @property
    def db_dsn_async(self) -> str:
        """DSN для async-движка SQLAlchemy (используется приложением)."""
        return (
            f"mysql+aiomysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )

    @property
    def db_dsn_sync(self) -> str:
        """DSN для sync-движка (используется Alembic-миграциями)."""
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )

    def is_admin(self, telegram_user_id: int) -> bool:
        return telegram_user_id in set(self.admin_ids)

    @property
    def api_access_token(self) -> str:
        """Токен для HTTP API мессенджера: приоритет MAX, иначе legacy BOT_TOKEN."""
        m = self.max_access_token.strip()
        if len(m) >= 10:
            return m
        return self.bot_token.strip()

    @property
    def invite_start_token_set(self) -> set[str]:
        return set(self.invite_start_tokens)

    def invite_link_enforced(self) -> bool:
        """Нужна валидная ссылка с ?start= для новых участников (без подтверждённого email)."""
        return self.invite_only and bool(self.invite_start_tokens)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Закэшированный singleton настроек.

    В тестах используется `get_settings.cache_clear()` для пересоздания
    с подменёнными `monkeypatch.setenv`.
    """
    return Settings()
