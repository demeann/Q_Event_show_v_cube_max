"""Заглушка для пользователей с подтверждённым email (туры — шаги 7+)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message

router = Router(name="main_menu")


@router.message(F.text)
async def placeheld_tours(message: Message) -> None:
    await message.answer(
        "Чтобы сыграть в активный тур, отправь команду /play.\n\n"
        "Если сейчас не игровое окно, бот подскажет — следи за датами «Конкурса в кубе» в Q CLUB."
    )
