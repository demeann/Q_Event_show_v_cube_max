"""Доступ к механике только после подтверждённого email (whitelist доменов)."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject, Update

from app.bot.states import OnboardingStates
from app.core.config import get_settings
from app.db.base import get_session
from app.services.user_service import get_user_by_telegram_id

log = logging.getLogger(__name__)


def _user_id_from_update(update: Update) -> int | None:
    if update.message and update.message.from_user:
        return update.message.from_user.id
    if update.edited_message and update.edited_message.from_user:
        return update.edited_message.from_user.id
    if update.callback_query and update.callback_query.from_user:
        return update.callback_query.from_user.id
    return None


def _public_command_text(message: Message) -> str | None:
    if not message.text:
        return None
    first = message.text.split()[0]
    cmd = first.split("@", 1)[0].lower()
    return cmd


class AccessMiddleware(BaseMiddleware):
    """Пропускает /start, /play, админов и шаг ввода email; остальное — только с verified."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Update):
            return await handler(event, data)

        settings = get_settings()
        uid = _user_id_from_update(event)
        if uid is None:
            return await handler(event, data)

        if settings.is_admin(uid):
            return await handler(event, data)

        raw_state = data.get("raw_state")
        if raw_state == OnboardingStates.waiting_email.state:
            return await handler(event, data)

        msg = event.message
        if msg and msg.text:
            cmd = _public_command_text(msg)
            if cmd in ("/start", "/play", "/admin_reset"):
                return await handler(event, data)

        async with get_session() as session:
            user = await get_user_by_telegram_id(session, uid)

        if user is not None and user.email_verified_at is not None:
            if user.is_blocked:
                if msg:
                    await msg.answer(
                        "Доступ для этого аккаунта ограничен. "
                        "Если кажется, что это ошибка — напиши в поддержку Q CLUB."
                    )
                elif event.callback_query and event.callback_query.message:
                    await event.callback_query.answer(
                        "Доступ ограничен.",
                        show_alert=True,
                    )
                return None
            return await handler(event, data)

        text = (
            "Чтобы участвовать в «Конкурсе в кубе», нужен корпоративный email "
            "на домене <b>@pmru.com</b> или <b>@contracted.pmru.com</b>.\n\n"
            "Нажми /start — проверим адрес и откроем доступ."
        )
        if msg:
            await msg.answer(text)
        elif event.callback_query and event.callback_query.message:
            await event.callback_query.answer(
                "Сначала пройди регистрацию: /start",
                show_alert=True,
            )
        log.debug("access_denied uid=%s state=%s", uid, raw_state)
        return None
