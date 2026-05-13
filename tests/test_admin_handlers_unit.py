"""Юнит-тесты вспомогательной логики админ-хендлеров (без Telegram)."""

from __future__ import annotations

import pytest

from app.bot.handlers import admin as admin_handlers
from app.core.config import get_settings
from app.db.models import RoundCode


def test_parse_round_none_and_whitespace():
    assert admin_handlers._parse_round(None) is None
    assert admin_handlers._parse_round("") is None
    assert admin_handlers._parse_round("   ") is None


def test_parse_round_codes():
    assert admin_handlers._parse_round("r1") is RoundCode.R1
    assert admin_handlers._parse_round(" R2 ") is RoundCode.R2
    assert admin_handlers._parse_round("R3") is RoundCode.R3


def test_parse_round_invalid():
    assert admin_handlers._parse_round("nope") is None
    assert admin_handlers._parse_round("R99") is None


@pytest.fixture
def admin_env(monkeypatch):
    monkeypatch.setenv("ADMIN_IDS", "1001,1002")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_is_admin_positive(admin_env):
    assert admin_handlers._is_admin(1001) is True
    assert admin_handlers._is_admin(1002) is True


def test_is_admin_negative(admin_env):
    assert admin_handlers._is_admin(999) is False


def test_admin_main_menu_keyboard_callbacks():
    kb = admin_handlers.admin_main_menu_kb()
    datas = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert datas == [
        "adm:stats",
        "adm:help",
        "adm:csv:R1",
        "adm:csv:R2",
        "adm:csv:R3",
        "adm:xlsx:R1",
        "adm:xlsx:R2",
        "adm:xlsx:R3",
        "adm:win:R1",
        "adm:win:R2",
        "adm:win:R3",
        "adm:reset_prompt",
    ]
    assert all(len(d) <= 64 for d in datas)
