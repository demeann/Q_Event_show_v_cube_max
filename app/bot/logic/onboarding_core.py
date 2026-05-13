"""Общая логика онбординга для Telegram и MAX (без привязки к транспорту)."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.bot.states import OnboardingStates
from app.core.config import Settings
from app.db.models import EmailValidationLog
from app.services.email_validation import check_corporate_email
from app.services.user_service import get_or_create_user

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


log = logging.getLogger(__name__)

_WELCOME_NEW = (
    'Добро пожаловать в чат-бот для сотрудников Компании ООО "ФМСМ".\n\n'
    "Внимание! Не передавайте полученный QR-код посторонним лицам.\n\n"
    "Чтобы начать - введи свою почту в поле ввода сообщения:"
)

_EMAIL_ACCEPTED = (
    'Добро пожаловать в "Конкурс в кубе"!🧡\n\n'
    "Ты можешь вспомнить лучшие моменты яркой трёхлетней истории программы лояльности "
    "Q CLUB — и получить шанс выиграть классный приз!\n\n"
    "📆Тебя ждут три тура: <b>14.05</b>, <b>18.05</b> и <b>20.05</b>. Мы пришлём напоминания, "
    "чтобы ты не пропустил начало.\n\n"
    "Участвуй в каждом туре и зарабатывай баллы. Удачи!"
)

_WELCOME_BACK = (
    "С возвращением! Ты уже в игре с email <b>{email}</b>.\n\n"
    "Туры «Конкурса в кубе» доступны через /play — следи за датами старта в Q CLUB.\n\n"
    "О старте следующего тура, мы пришлём уведомление."
)

_INVITE_REQUIRED = (
    "Бот доступен только по пригласительной ссылке.\n\n"
    "Открой ссылку из письма или сообщения от организаторов (формат: "
    "<code>t.me/...</code> с параметром <code>start</code>). "
    "Если ссылка есть, нажми её ещё раз и затем «Запустить» / Start."
)


async def handle_start(
    session: AsyncSession,
    settings: Settings,
    *,
    user_id: int,
    username: str | None,
    start_payload: str,
    reply_html: Callable[[str], Awaitable[None]],
    state_clear: Callable[[], Awaitable[None]],
    state_set_waiting_email: Callable[[], Awaitable[None]],
) -> None:
    if settings.is_admin(user_id):
        user = await get_or_create_user(session, user_id, username)
        user.is_admin = True
        if user.is_blocked:
            await reply_html(
                "Доступ для этого аккаунта ограничен. "
                "Если кажется, что это ошибка — напиши в поддержку Q CLUB."
            )
            await state_clear()
            return
        await state_clear()
        await reply_html(
            "Ты в списке <b>администраторов</b> — доступ без проверки email. "
            "Обычным участникам по-прежнему нужен корпоративный адрес.\n\n"
            "Дальше здесь появятся админка и туры."
        )
        return

    user = await get_or_create_user(session, user_id, username)

    if user.is_blocked:
        await reply_html(
            "Доступ для этого аккаунта ограничен. "
            "Если кажется, что это ошибка — напиши в поддержку Q CLUB."
        )
        await state_clear()
        return

    if user.email_verified_at is not None and user.email:
        await state_clear()
        await reply_html(_WELCOME_BACK.format(email=user.email))
        return

    if settings.invite_only and not settings.invite_start_tokens:
        log.error("INVITE_ONLY=true, но INVITE_START_TOKENS пуст — закройте дыру в конфиге.")
        await reply_html(
            "Регистрация через бота временно недоступна. Напиши в поддержку Q CLUB."
        )
        await state_clear()
        return

    if settings.invite_link_enforced():
        if user.invite_gate_passed_at is None:
            if start_payload not in settings.invite_start_token_set:
                await reply_html(_INVITE_REQUIRED)
                await state_clear()
                return
            user.invite_gate_passed_at = datetime.now(UTC).replace(tzinfo=None)

    await state_set_waiting_email()
    await reply_html(_WELCOME_NEW)


async def handle_waiting_email_text(
    session: AsyncSession,
    settings: Settings,
    *,
    user_id: int,
    username: str | None,
    raw_email_text: str,
    reply_html: Callable[[str], Awaitable[None]],
    state_clear: Callable[[], Awaitable[None]],
    after_email_verified: Callable[[], Awaitable[None]] | None = None,
) -> None:
    result = check_corporate_email(raw_email_text, settings.allowed_email_domains)

    user = await get_or_create_user(session, user_id, username)
    if settings.is_admin(user.telegram_user_id):
        user.is_admin = True

    masked = (
        result.normalized_email
        if result.normalized_email
        else (raw_email_text.strip() if raw_email_text.strip() else "(empty)")
    )
    log_row = EmailValidationLog(
        telegram_user_id=user_id,
        email=masked[:255],
        is_valid=result.ok,
        reason=result.reason[:64],
    )
    session.add(log_row)

    if not result.ok:
        if result.reason == "empty":
            await reply_html("Похоже, адрес пустой. Пришли email текстом.")
        elif result.reason == "invalid_format":
            await reply_html(
                "Не похоже на email. Проверь опечатки и пришли снова, например: "
                "<code>ivanov@pmru.com</code>"
            )
        elif result.reason == "domain_not_allowed":
            await reply_html(
                "Этот домен не подходит. Нужен корпоративный адрес на "
                "<code>@pmru.com</code> или <code>@contracted.pmru.com</code>.\n"
                "Попробуй другой email."
            )
        else:
            await reply_html("Не удалось проверить адрес. Попробуй ещё раз.")
        log.info("email_reject uid=%s reason=%s", user_id, result.reason)
        return

    now = datetime.now(UTC).replace(tzinfo=None)
    user.email = result.normalized_email
    user.email_domain = result.domain
    user.email_verified_at = now

    await state_clear()
    await reply_html(_EMAIL_ACCEPTED)
    if after_email_verified is not None:
        await after_email_verified()


async def handle_need_text_only_email(
    reply_html: Callable[[str], Awaitable[None]],
) -> None:
    await reply_html(
        "Пожалуйста, отправь email обычным текстом (без фото и стикеров)."
    )


def is_waiting_email_state(raw: str | None) -> bool:
    return raw == OnboardingStates.waiting_email.state
