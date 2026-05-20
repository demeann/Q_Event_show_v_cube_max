"""Какой тур сейчас доступен по времени (UTC в БД)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import now_utc
from app.db.models import Round


async def get_playable_round_now(session: AsyncSession) -> Round | None:
    """Тур, чьё окно [starts_at, ends_at] содержит текущий момент (UTC naive)."""
    now = now_utc().replace(tzinfo=None)
    result = await session.execute(
        select(Round)
        .where(Round.starts_at <= now, Round.ends_at >= now)
        .order_by(Round.starts_at.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()
