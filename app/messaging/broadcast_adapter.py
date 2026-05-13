"""Адаптеры рассылок: aiogram Bot и MAX Platform API."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import FSInputFile

from app.messaging.errors import MessengerBadRequestError, MessengerForbiddenError

if TYPE_CHECKING:
    from app.max_platform.client import MaxPlatformClient

log = logging.getLogger(__name__)


class BroadcastAdapter(Protocol):
    async def send_text_user(self, user_id: int, text: str) -> None: ...
    async def send_photo_user(
        self, user_id: int, photo_path: Path, caption: str
    ) -> None: ...


class TelegramBroadcastAdapter:
    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def send_text_user(self, user_id: int, text: str) -> None:
        try:
            await self._bot.send_message(user_id, text)
        except TelegramForbiddenError as e:
            raise MessengerForbiddenError(str(e)) from e
        except TelegramBadRequest as e:
            raise MessengerBadRequestError(str(e)) from e

    async def send_photo_user(
        self, user_id: int, photo_path: Path, caption: str
    ) -> None:
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


class MaxBroadcastAdapter:
    def __init__(self, client: MaxPlatformClient) -> None:
        self._client = client

    async def send_text_user(self, user_id: int, text: str) -> None:
        try:
            await self._client.send_message_to_user(user_id, text, format_="html")
        except Exception as e:
            self._map_exception(e)

    async def send_photo_user(
        self, user_id: int, photo_path: Path, caption: str
    ) -> None:
        cap = caption if len(caption) <= 1024 else (caption[:1021] + "…")
        try:
            attach = await self._client.upload_file_as_attachment(
                "image", photo_path, post_upload_delay_sec=0.35
            )
            await self._client.send_message_to_user(
                user_id,
                cap,
                format_="html",
                attachments=[attach],
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
