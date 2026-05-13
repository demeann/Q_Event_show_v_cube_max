"""Интро туров с опциональной картинкой (подпись + inline-клавиатура)."""

from __future__ import annotations

from pathlib import Path

from aiogram.types import FSInputFile, InlineKeyboardMarkup, Message

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Положите файлы рядом с репозиторием; без файла уходит только текст.
INTRO_R1_IMAGE = "assets/round1/intro.jpg"
INTRO_R2_IMAGE = "assets/round2/intro.jpg"
INTRO_R3_IMAGE = "assets/round3/intro.jpg"


def _resolve_media_path(rel_path: str) -> Path | None:
    p = _PROJECT_ROOT / str(rel_path).lstrip("/")
    return p if p.is_file() else None


async def answer_intro_with_optional_photo(
    message: Message,
    *,
    rel_image_path: str,
    caption: str,
    reply_markup: InlineKeyboardMarkup,
) -> None:
    img = _resolve_media_path(rel_image_path)
    if img is not None:
        await message.answer_photo(
            photo=FSInputFile(img),
            caption=caption,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
    else:
        await message.answer(
            caption, reply_markup=reply_markup, parse_mode="HTML"
        )


async def send_intro_push_to_user(
    bot,
    *,
    chat_id: int,
    rel_image_path: str,
    caption: str,
    reply_markup: InlineKeyboardMarkup,
) -> None:
    """Пуш участнику: как интро в /play (фото опционально)."""
    from aiogram import Bot

    if not isinstance(bot, Bot):
        raise TypeError("Expected aiogram.Bot")
    img = _resolve_media_path(rel_image_path)
    if img is not None:
        await bot.send_photo(
            chat_id,
            photo=FSInputFile(img),
            caption=caption,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
    else:
        await bot.send_message(
            chat_id,
            caption,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
