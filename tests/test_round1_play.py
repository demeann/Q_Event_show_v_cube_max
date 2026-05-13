"""Юнит-тесты вспомогательной логики Тура 1."""

from __future__ import annotations

import pytest

from app.services.round1_play import correct_index, format_correct_answer_line


def test_format_correct_answer_line() -> None:
    payload = {
        "text": "Q?",
        "options": ["alpha", "beta", "gamma"],
        "correct_index": 1,
    }
    line = format_correct_answer_line(payload)
    assert "beta" in line
    assert "Правильный" in line


def test_correct_index_cast() -> None:
    assert correct_index({"options": ["a", "b"], "correct_index": 0}) == 0


def test_correct_index_missing() -> None:
    with pytest.raises(ValueError):
        correct_index({"options": ["a"]})
