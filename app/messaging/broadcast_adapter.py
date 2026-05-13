"""Адаптеры рассылок: aiogram Bot и MAX Platform API."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import FSInputFile, InlineKeyboardMarkup

from app.bot.intro_media import send_intro_push_to_user
from app.messaging.errors import MessengerBadRequestError, MessengerForbiddenError

if TYPE_CHECKING:
    from app.max_platform.client import MaxPlatformClient

log = logging.getLogger(__name__)


class BroadcastAdapter(Protocol):
    async def send_text_user(
        self, user_id: int, text: str, *, chat_id: int | None = None
    ) -> None: ...

    async def send_photo_user(
        self,
        user_id: int,
        photo_path: Path,
        caption: str,
        *,
        chat_id: int | None = None,
    ) -> None: ...

    async def send_tour_intro_with_keyboard(
        self,
        user_id: int,
        *,
        rel_image_path: str,
        caption: str,
        reply_markup: InlineKeyboardMarkup,
        chat_id: int | None = None,
    ) -> None: ...


class TelegramBroadcastAdapter:
    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def send_text_user(
        self, user_id: int, text: str, *, chat_id: int | None = None
    ) -> None:
        del chat_id
        try:
            await self._bot.send_message(user_id, text)
        except TelegramForbiddenError as e:
            raise MessengerForbiddenError(str(e)) from e
        except TelegramBadRequest as e:
            raise MessengerBadRequestError(str(e)) from e

    async def send_photo_user(
        self,
        user_id: int,
        photo_path: Path,
        caption: str,
        *,
        chat_id: int | None = None,
    ) -> None:
        del chat_id
        cap = caption if len(caption) <= 1024 else (caption[:1021] + "…")
        try:
            await self._bot.send_photo(
                user_id,
                photo=FSInputFile(photo_path),
                caption=cap,
            )
        except TelegramForbiddenError as e:
            raise MessengerForbiddenError(str(e)) from e
        except TelegramBadRequest as e:
            raise MessengerBadRequestError(str(e)) from e

    async def send_tour_intro_with_keyboard(
        self,
        user_id: int,
        *,
        rel_image_path: str,
        caption: str,
        reply_markup: InlineKeyboardMarkup,
        chat_id: int | None = None,
    ) -> None:
        del chat_id
        try:
            await send_intro_push_to_user(
                self._bot,
                chat_id=user_id,
                rel_image_path=rel_image_path,
                caption=caption,
                reply_markup=reply_markup,
            )
        except TelegramForbiddenError as e:
            raise MessengerForbiddenError(str(e)) from e
        except TelegramBadRequest as e:
            raise MessengerBadRequestError(str(e)) from e


class MaxBroadcastAdapter:
    def __init__(self, client: MaxPlatformClient) -> None:
        self._client = client

    async def send_text_user(
        self, user_id: int, text: str, *, chat_id: int | None = None
    ) -> None:
        try:
            if chat_id is not None:
                await self._client.send_message(text, chat_id=chat_id, format_="html")
            else:
                await self._client.send_message_to_user(user_id, text, format_="html")
        except Exception as e:
            self._map_exception(e)

    async def send_photo_user(
        self,
        user_id: int,
        photo_path: Path,
        caption: str,
        *,
        chat_id: int | None = None,
    ) -> None:
        cap = caption if len(caption) <= 1024 else (caption[:1021] + "…")
        try:
            attach = await self._client.upload_file_as_attachment(
                "image", photo_path, post_upload_delay_sec=0.35
            )
            if chat_id is not None:
                await self._client.send_message(
                    cap, chat_id=chat_id, format_="html", attachments=[attach]
                )
            else:
                await self._client.send_message_to_user(
                    user_id,
                    cap,
                    format_="html",
                    attachments=[attach],
                )
        except Exception as e:
            self._map_exception(e)

    async def send_tour_intro_with_keyboard(
        self,
        user_id: int,
        *,
        rel_image_path: str,
        caption: str,
        reply_markup: InlineKeyboardMarkup,
        chat_id: int | None = None,
    ) -> None:
        from app.max_platform.telegram_markup import markup_to_max_attachments

        from app.bot.intro_media import _resolve_media_path

        cap = caption if len(caption) <= 1024 else (caption[:1021] + "…")
        try:
            attachments = markup_to_max_attachments(reply_markup)
            img = _resolve_media_path(rel_image_path)
            if img is not None:
                file_att = await self._client.upload_file_as_attachment(
                    "image", img, post_upload_delay_sec=0.35
                )
                attachments = [file_att] + (attachments or [])
            if chat_id is not None:
                await self._client.send_message(
                    cap,
                    chat_id=chat_id,
                    format_="html",
                    attachments=attachments or None,
                )
            else:
                await self._client.send_message_to_user(
                    user_id,
                    cap,
                    format_="html",
                    attachments=attachments or None,
                )
        except Exception as e:
            self._map_exception(e)

    def _map_exception(self, e: Exception) -> None:
        import httpx

        if isinstance(e, httpx.HTTPStatusError):
            code = e.response.status_code
            body = ""
            try:
                body = e.response.text[:500]
            except Exception:
                pass
            if code in (403, 401):
                raise MessengerForbiddenError(body or str(e)) from e
            if code == 400:
                raise MessengerBadRequestError(body or str(e)) from e
        log.debug("max broadcast unexpected error: %s", e)
        raise e
