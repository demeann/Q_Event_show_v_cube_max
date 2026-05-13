"""Порядок обработки update MAX: bot_started до message_created в одной пачке."""

from __future__ import annotations

from app.max_platform.update_batch import ordered_updates


def test_bot_started_before_message_created_in_batch():
    raw = [
        {"update_type": "message_created", "x": 1},
        {"update_type": "bot_started", "x": 2},
        {"update_type": "message_callback", "x": 3},
    ]
    ordered = ordered_updates(raw)
    assert [u["update_type"] for u in ordered] == [
        "bot_started",
        "message_callback",
        "message_created",
    ]


def test_unknown_type_last():
    raw: list[object] = [
        {"update_type": "message_created"},
        {"update_type": "weird_future_event"},
        {"update_type": "bot_started"},
    ]
    ordered = ordered_updates(raw)
    assert ordered[0]["update_type"] == "bot_started"
    assert ordered[1]["update_type"] == "message_created"
    assert ordered[2]["update_type"] == "weird_future_event"
