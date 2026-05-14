"""Онбординг: /start, ввод email, аудит валидации."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.filters.command import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bot.logic.onboarding_core import (
    handle_need_text_only_email,
    handle_start,
    handle_waiting_email_text,
)
from app.bot.states import OnboardingStates
from app.core.config import get_settings
from app.db.base import get_session
from app.messaging.broadcast_adapter import TelegramBroadcastAdapter
from app.services.tour_start_push import send_r1_intro_immediately_after_email_verified

router = Router(name="onboarding")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, command: CommandObject) -> None:
    settings = get_settings()
    if message.from_user is None:
        return
    start_payload = (command.args or "").strip()

    async def reply_html(text: str) -> None:
        await message.answer(text, parse_mode="HTML")

    async def state_set_waiting_email() -> None:
        await state.set_state(OnboardingStates.waiting_email)

    async with get_session() as session:
        await handle_start(
            session,
            settings,
            user_id=message.from_user.id,
            username=message.from_user.username,
            start_payload=start_payload,
            reply_html=reply_html,
            state_clear=state.clear,
            state_set_waiting_email=state_set_waiting_email,
        )


@router.message(OnboardingStates.waiting_email, F.text)
async def process_email(message: Message, state: FSMContext) -> None:
    settings = get_settings()
    if message.from_user is None:
        return
    raw = message.text or ""

    async def reply_html(text: str) -> None:
        await message.answer(text, parse_mode="HTML")

    async def after_verified() -> None:
        if message.bot is None or message.from_user is None:
            return
        await send_r1_intro_immediately_after_email_verified(
            TelegramBroadcastAdapter(message.bot),
            platform_user_id=message.from_user.id,
        )

    async with get_session() as session:
        await handle_waiting_email_text(
            session,
            settings,
            user_id=message.from_user.id,
            username=message.from_user.username,
            raw_email_text=raw,
            reply_html=reply_html,
            state_clear=state.clear,
            after_email_verified=after_verified,
        )


@router.message(OnboardingStates.waiting_email)
async def need_text_email(message: Message) -> None:
    async def reply_html(t: str) -> None:
        await message.answer(t, parse_mode="HTML")

    await handle_need_text_only_email(reply_html)
