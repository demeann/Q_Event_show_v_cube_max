"""Тесты Тура 3: YAML, callback R3Pick, хелперы хендлера."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from app.bot.handlers.round3 import (
    R3Pick,
    _options_from_payload,
    _question_caption,
    _resolve_image_file,
    _r3_keyboard,
)

_CONTENT = Path(__file__).resolve().parents[1] / "content"


def test_round3_yaml_question_codes_order_points() -> None:
    """Дополняет test_seed_yaml: коды вопросов, порядок, баллы."""
    data = yaml.safe_load((_CONTENT / "round3.yaml").read_text(encoding="utf-8"))
    qs = data["questions"]
    codes = [q["code"] for q in qs]
    assert codes == [f"R3Q{i}" for i in range(1, 4)]
    for i, q in enumerate(qs, start=1):
        assert q["order_index"] == i
        assert q["points"] == 100


@pytest.mark.parametrize("qid,idx", [(1, 0), (999, 1)])
def test_r3_pick_pack_unpack_roundtrip(qid: int, idx: int) -> None:
    packed = R3Pick(qid=qid, idx=idx).pack()
    assert packed == f"r3:{qid}:{idx}"
    parsed = R3Pick.unpack(packed)
    assert parsed.qid == qid and parsed.idx == idx


def test_options_from_payload_variants() -> None:
    assert _options_from_payload({}) == []
    assert _options_from_payload({"options": []}) == []
    assert _options_from_payload({"options": ["A", "B"]}) == ["A", "B"]


def test_question_caption() -> None:
    q = SimpleNamespace(
        order_index=2,
        payload={"text": "Текст задачи", "options": ["А", "Б"]},
    )
    cap = _question_caption(q)
    assert "Вопрос №2" in cap
    assert "Варианты ответа" in cap
    assert "1. А" in cap
    assert "2. Б" in cap


def test_r3_keyboard_two_buttons_distinct_callbacks() -> None:
    q = SimpleNamespace(
        id=77,
        order_index=1,
        payload={"text": "?", "options": ["Левый", "Правый"]},
    )
    kb = _r3_keyboard(q)
    assert len(kb.inline_keyboard) == 1
    row0 = kb.inline_keyboard[0]
    assert len(row0) == 2
    assert row0[0].text == "1" and row0[1].text == "2"
    d0 = R3Pick.unpack(row0[0].callback_data)
    d1 = R3Pick.unpack(row0[1].callback_data)
    assert d0.qid == d1.qid == 77
    assert d0.idx == 0 and d1.idx == 1


def test_resolve_image_file_missing_path_returns_none(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "app.bot.handlers.round3._PROJECT_ROOT",
        tmp_path,
        raising=False,
    )
    assert _resolve_image_file({"image_path": "assets/round3/nope.jpg"}) is None


def test_resolve_image_file_no_image_key_returns_none(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "app.bot.handlers.round3._PROJECT_ROOT",
        tmp_path,
        raising=False,
    )
    assert _resolve_image_file({"text": "x"}) is None


def test_resolve_image_file_when_exists(monkeypatch, tmp_path) -> None:
    rel = Path("assets/round3/q1.jpg")
    full = tmp_path / rel
    full.parent.mkdir(parents=True)
    full.write_bytes(b"\xff\xd8\xff")  # минимальная сигнатура JPEG для is_file()

    monkeypatch.setattr(
        "app.bot.handlers.round3._PROJECT_ROOT",
        tmp_path,
        raising=False,
    )
    got = _resolve_image_file({"image_path": str(rel)})
    assert got == full
    assert got.is_file()
