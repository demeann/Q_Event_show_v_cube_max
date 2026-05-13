"""Команда /play: маршрутизация по активному туру."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.gates import gate_playable_user
from app.bot.handlers.round1 import play_round1_entry
from app.bot.handlers.round2 import play_round2_entry
from app.bot.handlers.round3 import play_round3_entry
from app.db.base import get_session
from app.db.models import RoundCode
from app.services.round_schedule import get_playable_round_now

router = Router(name="play")


@router.message(Command("play"))
async def cmd_play(message: Message) -> None:
    if message.from_user is None:
        return
    async with get_session() as session:
        user, err = await gate_playable_user(session, message.from_user.id)
        if err:
            await message.answer(err)
            return

        active = await get_playable_round_now(session)
        if active is None:
            await message.answer(
                "Сейчас нет активного тура.\n\n"
                "Даты игры совпадают с настройкой внутри Q CLUB — загляни в объявления "
                "или к организаторам."
            )
            return

        if active.code == RoundCode.R1:
            await play_round1_entry(message, session, user, active)
        elif active.code == RoundCode.R2:
            await play_round2_entry(message, session, user, active)
        elif active.code == RoundCode.R3:
            await play_round3_entry(message, session, user, active)
        else:
            await message.answer("Неизвестный тур. Сообщи организаторам.")
