"""Тесты для app.core.config (загрузка/валидация настроек)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


@pytest.fixture(autouse=True)
def _clear_cache():
    """Не давать singleton'у Settings утечь между тестами."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _set_required_env(monkeypatch):
    """Минимально необходимый набор обязательных переменных."""
    monkeypatch.setenv("BOT_TOKEN", "1234567890:test_token_value")
    monkeypatch.setenv("DB_NAME", "test_db")
    monkeypatch.setenv("DB_USER", "test_user")
    monkeypatch.setenv("DB_PASSWORD", "test_pass")
    monkeypatch.setenv("GAME_START_DATE_MSK", "2026-05-15")


def _make_settings() -> Settings:
    """Создать Settings БЕЗ чтения локального .env (только из process env)."""
    return Settings(_env_file=None)


def test_settings_load_with_required(monkeypatch):
    _set_required_env(monkeypatch)
    s = _make_settings()
    assert s.bot_token == "1234567890:test_token_value"
    assert s.db_name == "test_db"
    assert str(s.game_start_date_msk) == "2026-05-15"
    assert s.db_port == 3306  # default


def test_admin_ids_parsing(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.setenv("ADMIN_IDS", "111, 222 ,333")
    s = _make_settings()
    assert s.admin_ids == [111, 222, 333]
    assert s.is_admin(222) is True
    assert s.is_admin(999) is False


def test_admin_ids_empty(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.setenv("ADMIN_IDS", "")
    s = _make_settings()
    assert s.admin_ids == []
    assert s.is_admin(123) is False


def test_email_domains_parsing_lowercases_and_strips_at(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.setenv("ALLOWED_EMAIL_DOMAINS", "PMRU.com, @contracted.PMRU.com")
    s = _make_settings()
    assert s.allowed_email_domains == ["pmru.com", "contracted.pmru.com"]


def test_log_level_uppercased(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.setenv("LOG_LEVEL", "debug")
    s = _make_settings()
    assert s.log_level == "DEBUG"


def test_log_level_invalid_raises(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.setenv("LOG_LEVEL", "nonsense")
    with pytest.raises(ValidationError):
        _make_settings()


def test_run_mode_default_is_polling(monkeypatch):
    _set_required_env(monkeypatch)
    s = _make_settings()
    assert s.run_mode == "polling"


def test_run_mode_invalid_raises(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.setenv("RUN_MODE", "carrierpigeon")
    with pytest.raises(ValidationError):
        _make_settings()


def test_db_dsn_format(monkeypatch):
    _set_required_env(monkeypatch)
    s = _make_settings()
    assert s.db_dsn_async.startswith("mysql+aiomysql://test_user:test_pass@localhost:3306/test_db")
    assert s.db_dsn_sync.startswith("mysql+pymysql://test_user:test_pass@localhost:3306/test_db")
    assert "charset=utf8mb4" in s.db_dsn_async


def test_missing_required_field_raises(monkeypatch):
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.setenv("DB_NAME", "test_db")
    monkeypatch.setenv("DB_USER", "test_user")
    monkeypatch.setenv("DB_PASSWORD", "test_pass")
    monkeypatch.setenv("GAME_START_DATE_MSK", "2026-05-15")
    with pytest.raises(ValidationError):
        _make_settings()


def test_invite_settings(monkeypatch):
    _set_required_env(monkeypatch)
    s = _make_settings()
    assert s.invite_only is False
    assert s.invite_start_tokens == []
    assert s.invite_link_enforced() is False

    monkeypatch.setenv("INVITE_ONLY", "true")
    monkeypatch.setenv("INVITE_START_TOKENS", "-alpha, beta")
    s = _make_settings()
    assert s.invite_only is True
    assert s.invite_start_tokens == ["-alpha", "beta"]
    assert s.invite_link_enforced() is True
    assert s.invite_start_token_set == {"-alpha", "beta"}


def test_get_settings_is_cached(monkeypatch):
    _set_required_env(monkeypatch)
    a = get_settings()
    b = get_settings()
    assert a is b
