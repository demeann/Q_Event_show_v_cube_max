"""Стартовые пуши туров (константы и callback-строки)."""

from __future__ import annotations

from app.db.models.round import RoundCode
from app.services.tour_start_push import (
    CB_R1_GO,
    CB_R2_GO,
    CB_R3_GO,
    TOUR_PUSH_R1_TEXT,
    _kb_r1,
    _kb_r2,
    _kb_r3,
    _push_meta,
)


def test_callback_payloads_match_aiogram_pack():
    from app.bot.handlers.round1 import R1Forward
    from app.bot.handlers.round2 import R2Go
    from app.bot.handlers.round3 import R3Go

    assert R1Forward().pack() == CB_R1_GO
    assert R2Go().pack() == CB_R2_GO
    assert R3Go().pack() == CB_R3_GO


def test_push_meta_covers_all_rounds():
    for code in (RoundCode.R1, RoundCode.R2, RoundCode.R3):
        text, path, kb = _push_meta(code)
        assert text
        assert path.startswith("assets/")
        assert kb.inline_keyboard

    assert _kb_r1().inline_keyboard[0][0].text == "Вперёд"
    assert _kb_r2().inline_keyboard[0][0].text == "Начинаем"
    assert _kb_r3().inline_keyboard[0][0].text == "Поехали"

    assert "Поехали?👀" in TOUR_PUSH_R1_TEXT
