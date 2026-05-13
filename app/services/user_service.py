"""Операции с участниками в БД."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


async def get_user_by_telegram_id(
    session: AsyncSession, telegram_user_id: int
) -> User | None:
    q = await session.execute(
        select(User).where(User.telegram_user_id == telegram_user_id)
    )
    return q.scalar_one_or_none()


async def get_or_create_user(
    session: AsyncSession,
    telegram_user_id: int,
    tg_username: str | None,
) -> User:
    user = await get_user_by_telegram_id(session, telegram_user_id)
    if user is None:
        user = User(
            telegram_user_id=telegram_user_id,
            tg_username=tg_username,
        )
        session.add(user)
        await session.flush()
    else:
        if tg_username != user.tg_username:
            user.tg_username = tg_username
    return user
