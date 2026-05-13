"""HTTP-клиент Platform API MAX (https://platform-api.max.ru)."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import httpx

DEFAULT_BASE = "https://platform-api.max.ru"

log = logging.getLogger(__name__)


class MaxPlatformClient:
    """Минимальный клиент: отправка сообщений и long polling."""

    def __init__(
        self,
        access_token: str,
        *,
        base_url: str = DEFAULT_BASE,
        timeout: float = 60.0,
    ) -> None:
        self._token = access_token.strip()
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base,
                headers={
                    "Authorization": self._token,
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(self._timeout),
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get_me(self) -> dict[str, Any]:
        c = await self._get_client()
        r = await c.get("/me")
        r.raise_for_status()
        return r.json()

    async def get_updates(
        self,
        *,
        limit: int = 100,
        timeout: int = 30,
        marker: int | None = None,
        types: list[str] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit, "timeout": timeout}
        if marker is not None:
            params["marker"] = marker
        if types:
            # httpx сериализует list как повторяющиеся ключи или через запятую — проверьте бэкенд MAX.
            params["types"] = ",".join(types)
        c = await self._get_client()
        r = await c.get("/updates", params=params)
        r.raise_for_status()
        return r.json()

    async def send_message(
        self,
        text: str,
        *,
        user_id: int | None = None,
        chat_id: int | None = None,
        format_: str = "html",
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """POST /messages — ровно один из ``user_id`` или ``chat_id`` (см. доки MAX)."""
        if (user_id is None) == (chat_id is None):
            raise ValueError("need exactly one of user_id, chat_id")
        c = await self._get_client()
        body: dict[str, Any] = {"text": text, "format": format_}
        if attachments:
            body["attachments"] = attachments
        params = (
            {"user_id": user_id} if user_id is not None else {"chat_id": chat_id}
        )
        r = await c.post("/messages", params=params, json=body)
        try:
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            detail = ""
            try:
                detail = e.response.text[:800]
            except Exception:
                pass
            log.warning(
                "MAX POST /messages failed status=%s params=%s detail=%s",
                e.response.status_code,
                params,
                detail or str(e),
            )
            raise
        return r.json()

    async def send_message_to_user(
        self,
        user_id: int,
        text: str,
        *,
        format_: str = "html",
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """POST /messages?user_id=…"""
        return await self.send_message(
            text,
            user_id=user_id,
            format_=format_,
            attachments=attachments,
        )

    async def post_answers(
        self,
        callback_id: str,
        *,
        notification: str | None = None,
        message: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """POST /answers?callback_id=…"""
        c = await self._get_client()
        body: dict[str, Any] = {}
        if notification is not None:
            body["notification"] = notification
        if message is not None:
            body["message"] = message
        r = await c.post("/answers", params={"callback_id": callback_id}, json=body)
        r.raise_for_status()
        return r.json()

    async def upload_file_as_attachment(
        self,
        upload_type: str,
        file_path: Path,
        *,
        post_upload_delay_sec: float = 0.0,
    ) -> dict[str, Any]:
        """Загрузка по схеме POST /uploads → POST upload_url; вложение для ``/messages``."""
        c = await self._get_client()
        r1 = await c.post("/uploads", params={"type": upload_type})
        r1.raise_for_status()
        meta = r1.json()
        url = meta["url"]
        async with httpx.AsyncClient(timeout=httpx.Timeout(self._timeout)) as up:
            with open(file_path, "rb") as fh:
                r2 = await up.post(
                    url,
                    headers={"Authorization": self._token},
                    files={"data": (file_path.name, fh)},
                )
            r2.raise_for_status()
            uploaded = r2.json()
        if post_upload_delay_sec:
            await asyncio.sleep(post_upload_delay_sec)
        return {"type": upload_type, "payload": uploaded}

    @staticmethod
    def inline_keyboard_single_row(
        buttons: list[tuple[str, str]],
    ) -> list[dict[str, Any]]:
        """Кнопки callback: (text, payload) в один ряд."""
        row = [
            {"type": "callback", "text": t, "payload": pl}
            for t, pl in buttons
        ]
        return [{"type": "inline_keyboard", "payload": {"buttons": [row]}}]
