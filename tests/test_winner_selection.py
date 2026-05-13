"""Тесты ранжирования и отбора по фиксированным местам в рейтинге."""

from __future__ import annotations

from datetime import datetime

from app.db.models import RoundCode
from app.services.winner_ranking import (
    WINNER_LIST_RANKS_BY_ROUND,
    RankedParticipant,
    pick_winners_by_fixed_list_ranks,
    selection_note_ru,
    sort_participant_rows,
)


def test_sort_by_score_then_last_answer_then_user_id() -> None:
    t1 = datetime(2026, 1, 1, 12, 0, 0)
    t2 = datetime(2026, 1, 1, 13, 0, 0)
    rows = [
        RankedParticipant(2, 10, t2, False),
        RankedParticipant(1, 10, t1, False),
        RankedParticipant(3, 5, t1, False),
    ]
    s = sort_participant_rows(rows)
    assert [p.user_id for p in s] == [1, 2, 3]


def test_sort_tie_score_no_last_answer_sorts_by_user_id() -> None:
    rows = [
        RankedParticipant(3, 10, None, False),
        RankedParticipant(1, 10, None, False),
        RankedParticipant(2, 10, None, False),
    ]
    s = sort_participant_rows(rows)
    assert [p.user_id for p in s] == [1, 2, 3]


def test_pick_winners_fixed_ranks() -> None:
    ids = list(range(1, 101))
    ranks = [3, 10, 99]
    w, filled, missing = pick_winners_by_fixed_list_ranks(ids, ranks)
    assert w == [3, 10, 99]
    assert filled == ranks
    assert missing == []


def test_pick_winners_missing_ranks() -> None:
    ids = [10, 20, 30]
    ranks = [1, 2, 3, 5, 10]
    w, filled, missing = pick_winners_by_fixed_list_ranks(ids, ranks)
    assert w == [10, 20, 30]
    assert filled == [1, 2, 3]
    assert missing == [5, 10]


def test_selection_note_ru_none_when_complete() -> None:
    assert selection_note_ru([3], []) is None


def test_selection_note_ru_when_partial() -> None:
    s = selection_note_ru([3, 97], [189, 277])
    assert "3, 97" in s
    assert "189, 277" in s


def test_winner_list_ranks_nine_per_round() -> None:
    for code in (RoundCode.R1, RoundCode.R2, RoundCode.R3):
        assert len(WINNER_LIST_RANKS_BY_ROUND[code]) == 9
