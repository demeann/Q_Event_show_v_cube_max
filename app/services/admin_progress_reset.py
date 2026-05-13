"""Полный сброс игрового прогресса пользователя (для админов и быстрого просмотра туров)."""

from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UserAnswer, UserRoundProgress, UserTopicProgress, Winner


def _rowcount(result) -> int:
    rc = getattr(result, "rowcount", None)
    if rc is None:
        return 0
    return int(rc) if rc >= 0 else 0


async def reset_all_game_progress_for_user(
    session: AsyncSession,
    user_id: int,
) -> dict[str, int]:
    """Удаляет ответы, прогресс по турам и темам, строки победителя для ``user_id``.

    Email, пользователь, рассылки и audit не затрагиваются.
    """
    ra = await session.execute(delete(UserAnswer).where(UserAnswer.user_id == user_id))
    rt = await session.execute(delete(UserTopicProgress).where(UserTopicProgress.user_id == user_id))
    rr = await session.execute(
        delete(UserRoundProgress).where(UserRoundProgress.user_id == user_id)
    )
    rw = await session.execute(delete(Winner).where(Winner.user_id == user_id))

    return {
        "answers": _rowcount(ra),
        "topic_progress": _rowcount(rt),
        "round_progress": _rowcount(rr),
        "winners": _rowcount(rw),
    }
