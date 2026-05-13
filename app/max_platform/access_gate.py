"""Проверка доступа для MAX (аналог ``AccessMiddleware``)."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from app.bot.logic.onboarding_core import is_waiting_email_state
from app.core.config import get_settings
from app.db.base import get_session
from app.services.user_service import get_user_by_telegram_id

log = logging.getLogger(__name__)


def _public_command_text(text: str | None) -> str | None:
    if not text:
        return None
    first = text.split()[0]
    return first.split("@", 1)[0].lower()


async def max_access_gate(
    user_id: int,
    text: str | None,
    fsm_raw_state: str | None,
    *,
    reply_html: Callable[[str], Awaitable[None]],
    reply_callback_alert: Callable[[str], Awaitable[None]] | None = None,
) -> bool:
    """Возвращает ``True``, если событие можно обрабатывать дальше."""
    settings = get_settings()

    if settings.is_admin(user_id):
        return True

    if is_waiting_email_state(fsm_raw_state):
        return True

    cmd = _public_command_text(text)
    if cmd in ("/start", "/play", "/admin_reset"):
        return True

    async with get_session() as session:
        user = await get_user_by_telegram_id(session, user_id)

    if user is not None and user.email_verified_at is not None:
        if user.is_blocked:
            await reply_html(
                "Доступ для этого аккаунта ограничен. "
                "Если кажется, что это ошибка — напиши в поддержку Q CLUB."
            )
            return False
        return True

    msg = (
        "Чтобы участвовать в «Конкурсе в кубе», нужен корпоративный email "
        "на домене <b>@pmru.com</b> или <b>@contracted.pmru.com</b>.\n\n"
        "Нажми /start — проверим адрес и откроем доступ."
    )
    if text is not None:
        await reply_html(msg)
    elif reply_callback_alert is not None:
        await reply_callback_alert("Сначала пройди регистрацию: /start")
    log.debug("max_access_denied uid=%s state=%s", user_id, fsm_raw_state)
    return False
