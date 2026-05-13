"""Объекты, похожие на aiogram Message / CallbackQuery, но исходящий транспорт — MAX API."""

from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from aiogram.types import BufferedInputFile, FSInputFile

from app.max_platform.client import MaxPlatformClient
from app.max_platform.telegram_markup import markup_to_max_attachments


def _photo_arg_to_path(photo: Any) -> Path:
    if isinstance(photo, FSInputFile):
        return Path(photo.path)
    if isinstance(photo, Path):
        return photo
    return Path(str(photo))


class MaxUiMessage:
    def __init__(
        self,
        client: MaxPlatformClient,
        *,
        user_id: int,
        username: str | None,
        text: str | None = None,
    ) -> None:
        self._client = client
        self._uid = user_id
        self.from_user = SimpleNamespace(id=user_id, username=username)
        self.text = text
        self.chat = SimpleNamespace(id=user_id)

    async def answer(
        self,
        text: str,
        reply_markup: Any = None,
        parse_mode: str | None = "HTML",
        **kwargs: Any,
    ) -> None:
        del kwargs
        fmt = (
            "html" if parse_mode and str(parse_mode).upper() == "HTML" else "html"
        )
        att = markup_to_max_attachments(reply_markup)
        await self._client.send_message_to_user(
            self._uid,
            text,
            format_=fmt,
            attachments=att or None,
        )

    async def answer_photo(
        self,
        photo: Any,
        caption: str = "",
        reply_markup: Any = None,
        **kwargs: Any,
    ) -> None:
        del kwargs
        cleanup: Path | None = None
        if isinstance(photo, BufferedInputFile):
            suf = Path(photo.filename or "x.bin").suffix or ".bin"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suf) as tmp:
                tmp.write(photo.data)
                path = Path(tmp.name)
                cleanup = path
        else:
            path = _photo_arg_to_path(photo)
        try:
            img_att = await self._client.upload_file_as_attachment(
                "image", path, post_upload_delay_sec=0.35
            )
            att = [img_att] + markup_to_max_attachments(reply_markup)
            await self._client.send_message_to_user(
                self._uid,
                caption,
                format_="html",
                attachments=att,
            )
        finally:
            if cleanup is not None:
                cleanup.unlink(missing_ok=True)

    async def answer_document(
        self,
        document: Any,
        caption: str = "",
        **kwargs: Any,
    ) -> None:
        del kwargs
        if isinstance(document, BufferedInputFile):
            suffix = document.filename or ".bin"
            fd, name = tempfile.mkstemp(suffix=suffix)
            import os

            try:
                with os.fdopen(fd, "wb") as tmp:
                    tmp.write(document.data)
                path = Path(name)
            except Exception:
                os.close(fd)
                raise
            tmp_path = True
        elif isinstance(document, FSInputFile):
            path = Path(document.path)
            tmp_path = False
        else:
            path = Path(str(document))
            tmp_path = False
        try:
            file_att = await self._client.upload_file_as_attachment(
                "file", path, post_upload_delay_sec=0.35
            )
            cap = caption or " "
            await self._client.send_message_to_user(
                self._uid,
                cap,
                format_="html",
                attachments=[file_att],
            )
        finally:
            if tmp_path:
                path.unlink(missing_ok=True)


class MaxUiCallbackQuery:
    def __init__(
        self,
        client: MaxPlatformClient,
        *,
        user_id: int,
        username: str | None,
        callback_id: str,
        message: MaxUiMessage,
        data: str,
    ) -> None:
        self._client = client
        self._callback_id = callback_id
        self.from_user = SimpleNamespace(id=user_id, username=username)
        self.message = message
        self.data = data
        self.id = callback_id

    async def answer(
        self,
        text: str | None = None,
        show_alert: bool = False,
        **kwargs: Any,
    ) -> None:
        del kwargs
        if text is None:
            await self._client.post_answers(self._callback_id)
            return
        await self._client.post_answers(
            self._callback_id, notification=text, message=None
        )
