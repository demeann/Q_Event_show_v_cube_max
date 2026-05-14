"""Хелперы для работы с временем.

Все игровые сущности фиксируются по МСК (Europe/Moscow), а в БД хранятся
как aware-datetime (UTC). Эти функции изолируют конверсии и не дают
работать с naive-datetime.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

MSK = ZoneInfo("Europe/Moscow")
UTC = ZoneInfo("UTC")


def now_utc() -> datetime:
    """Текущее время в UTC (aware)."""
    return datetime.now(tz=UTC)


def now_msk() -> datetime:
    """Текущее время в МСК (aware)."""
    return datetime.now(tz=MSK)


def to_msk(dt: datetime) -> datetime:
    """Перевести aware-datetime в МСК."""
    if dt.tzinfo is None:
        raise ValueError("naive datetime is not allowed; pass aware datetime")
    return dt.astimezone(MSK)


def to_utc(dt: datetime) -> datetime:
    """Перевести aware-datetime в UTC."""
    if dt.tzinfo is None:
        raise ValueError("naive datetime is not allowed; pass aware datetime")
    return dt.astimezone(UTC)


def msk_day_start(d: date) -> datetime:
    """00:00:00 указанной даты в МСК."""
    return datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=MSK)


def msk_day_end(d: date) -> datetime:
    """23:59:59.999999 указанной даты в МСК."""
    return datetime(d.year, d.month, d.day, 23, 59, 59, 999_999, tzinfo=MSK)


def msk_at(d: date, hour: int, minute: int = 0) -> datetime:
    """Конкретное время по МСК для указанной даты (для расписания рассылок)."""
    return datetime(d.year, d.month, d.day, hour, minute, tzinfo=MSK)


def add_days(d: date, days: int) -> date:
    """Прибавить дни к дате (без часовых поясов)."""
    return d + timedelta(days=days)


def round_index_for_date(start_date_msk: date, today_msk: date) -> int | None:
    """Какой тур активен на дату `today_msk` при старте игры `start_date_msk`.

    Тур 1 — четыре календарных дня (смещения 0..3), туры 2 и 3 — по три дня (4..6 и 7..9).
    Возвращает 1, 2, 3 или None (если дата вне игрового окна).
    """
    delta_days = (today_msk - start_date_msk).days
    if delta_days < 0 or delta_days > 9:
        return None
    if delta_days <= 3:
        return 1
    if delta_days <= 6:
        return 2
    return 3
