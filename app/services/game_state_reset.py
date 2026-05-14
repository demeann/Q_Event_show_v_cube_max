"""Сброс игровой активности в БД (общая логика для CLI-скриптов)."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Broadcast,
    BroadcastRecipient,
    UserAnswer,
    UserRoundProgress,
    UserTopicProgress,
    WinnerSelection,
)


async def count_player_activity_rows(session: AsyncSession) -> dict[str, int]:
    """Количество строк в таблицах, которые очищает :func:`delete_all_player_activity`."""
    out: dict[str, int] = {}
    for m in (
        UserAnswer,
        UserTopicProgress,
        UserRoundProgress,
        BroadcastRecipient,
        Broadcast,
        WinnerSelection,
    ):
        key = m.__tablename__
        c = await session.scalar(select(func.count()).select_from(m))
        out[key] = int(c or 0)
    return out


async def delete_all_player_activity(session: AsyncSession) -> None:
    """Удалить ответы, прогресс, рассылки и отборы победителей (без ``commit``)."""
    await session.execute(delete(BroadcastRecipient))
    await session.execute(delete(Broadcast))
    await session.execute(delete(WinnerSelection))
    await session.execute(delete(UserAnswer))
    await session.execute(delete(UserTopicProgress))
    await session.execute(delete(UserRoundProgress))
