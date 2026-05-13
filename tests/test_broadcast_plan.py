"""Тесты планирования рассылок (слоты по турам)."""

from __future__ import annotations

from datetime import datetime

from app.db.models.round import RoundCode, RoundStatus
from app.services.broadcast_plan import slots_for_round


def test_slots_for_round_four_entries():
    from app.db.models.round import Round

    r = Round(
        code=RoundCode.R1,
        name="T",
        starts_at=datetime(2026, 5, 1, 21, 0, 0),
        ends_at=datetime(2026, 5, 4, 20, 59, 59),
        status=RoundStatus.SCHEDULED,
    )
    slots = slots_for_round(r)
    assert len(slots) == 4
    codes = [s.template_code for s in slots]
    assert codes[0] == "ANNOUNCE_R1"
    assert "REMINDER_R1_NOT_STARTED" in codes
    assert "REMINDER_R1_NOT_FINISHED" in codes
    assert codes[-1] == "RESULT_R1"


def test_result_r3_uses_all_rounds_finished_segment():
    from app.db.models.round import Round

    r = Round(
        code=RoundCode.R3,
        name="T3",
        starts_at=datetime(2026, 5, 20, 21, 0, 0),
        ends_at=datetime(2026, 5, 22, 20, 59, 59),
        status=RoundStatus.SCHEDULED,
    )
    slots = slots_for_round(r)
    assert slots[-1].template_code == "RESULT_R3"
    assert slots[-1].segment_code == "ALL_ROUNDS_FINISHED"


def test_result_r1_uses_all_verified_segment():
    from app.db.models.round import Round

    r = Round(
        code=RoundCode.R1,
        name="T",
        starts_at=datetime(2026, 5, 1, 21, 0, 0),
        ends_at=datetime(2026, 5, 4, 20, 59, 59),
        status=RoundStatus.SCHEDULED,
    )
    slots = slots_for_round(r)
    assert slots[-1].segment_code == "ALL_VERIFIED"


def test_parse_segment_round_code():
    from app.services.broadcast_segments import parse_round_code_from_segment

    assert parse_round_code_from_segment("ALL_VERIFIED") is None
    assert parse_round_code_from_segment("ALL_ROUNDS_FINISHED") is None
    assert parse_round_code_from_segment("R2_NOT_STARTED").value == "R2"
