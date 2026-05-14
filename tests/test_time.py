"""Тесты для app.core.time (МСК-хелперы)."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.core import time as t


def test_msk_constant():
    assert str(t.MSK) == "Europe/Moscow"
    assert str(t.UTC) == "UTC"


def test_now_msk_is_aware():
    n = t.now_msk()
    assert n.tzinfo is not None
    assert n.utcoffset() is not None


def test_now_utc_is_aware():
    n = t.now_utc()
    assert n.tzinfo is not None
    assert n.utcoffset().total_seconds() == 0


def test_to_msk_from_utc_offset_plus_3():
    # МСК круглый год = UTC+3 (без перехода на летнее время с 2014).
    utc_dt = datetime(2026, 5, 15, 7, 0, 0, tzinfo=timezone.utc)
    msk_dt = t.to_msk(utc_dt)
    assert msk_dt.hour == 10
    assert str(msk_dt.tzinfo) == "Europe/Moscow"


def test_to_utc_from_msk_offset_minus_3():
    msk_dt = datetime(2026, 5, 15, 10, 0, 0, tzinfo=t.MSK)
    utc_dt = t.to_utc(msk_dt)
    assert utc_dt.hour == 7
    assert str(utc_dt.tzinfo) == "UTC"


def test_to_msk_naive_raises():
    naive = datetime(2026, 5, 15, 7, 0, 0)
    with pytest.raises(ValueError):
        t.to_msk(naive)


def test_to_utc_naive_raises():
    naive = datetime(2026, 5, 15, 7, 0, 0)
    with pytest.raises(ValueError):
        t.to_utc(naive)


def test_msk_day_start():
    d = date(2026, 5, 15)
    s = t.msk_day_start(d)
    assert (s.hour, s.minute, s.second, s.microsecond) == (0, 0, 0, 0)
    assert s.tzinfo == t.MSK


def test_msk_day_end():
    d = date(2026, 5, 15)
    e = t.msk_day_end(d)
    assert (e.hour, e.minute, e.second) == (23, 59, 59)
    assert e.microsecond == 999_999
    assert e.tzinfo == t.MSK


def test_msk_at_specific_hour():
    d = date(2026, 5, 15)
    assert t.msk_at(d, 10) == datetime(2026, 5, 15, 10, 0, tzinfo=t.MSK)
    assert t.msk_at(d, 19, 30) == datetime(2026, 5, 15, 19, 30, tzinfo=t.MSK)


def test_add_days():
    d = date(2026, 5, 15)
    assert t.add_days(d, 0) == d
    assert t.add_days(d, 3) == date(2026, 5, 18)
    assert t.add_days(d, -1) == date(2026, 5, 14)


@pytest.mark.parametrize(
    "today_offset,expected_round",
    [
        (-1, None),
        (0, 1),
        (1, 1),
        (2, 1),
        (3, 1),
        (4, 2),
        (5, 2),
        (6, 2),
        (7, 3),
        (8, 3),
        (9, 3),
        (10, None),
        (100, None),
    ],
)
def test_round_index_for_date(today_offset, expected_round):
    start = date(2026, 5, 15)
    today = t.add_days(start, today_offset)
    assert t.round_index_for_date(start, today) == expected_round
