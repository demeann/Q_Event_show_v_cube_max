"""Проверки «можно ли играть» для зарегистрированного пользователя."""

from __future__ import annotations

from app.core.config import get_settings
from app.db.models import User
from app.services.user_service import get_user_by_telegram_id


async def gate_playable_user(session, from_user_id: int) -> tuple[User | None, str | None]:
    settings = get_settings()
    user = await get_user_by_telegram_id(session, from_user_id)
    if user is None:
        return None, "Сначала нажми /start."
    if user.is_blocked:
        return None, "Доступ для этого аккаунта ограничен."
    if user.email_verified_at is None and not settings.is_admin(from_user_id):
        return None, "Сначала подтверди корпоративный email: /start"
    return user, None
