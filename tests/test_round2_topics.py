"""Минимальные проверки констант Тура 2."""

from __future__ import annotations

from app.bot.handlers.round2 import R2_TOPIC_TITLES


def test_r2_topic_titles_match_yaml_topics() -> None:
    assert set(R2_TOPIC_TITLES) == {"T1", "T2", "T3"}
