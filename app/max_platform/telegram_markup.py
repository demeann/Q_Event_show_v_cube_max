"""Конвертация aiogram InlineKeyboardMarkup → вложения MAX."""

from __future__ import annotations

from typing import Any

from aiogram.types import InlineKeyboardMarkup


def markup_to_max_attachments(markup: InlineKeyboardMarkup | None) -> list[dict[str, Any]]:
    if markup is None or not markup.inline_keyboard:
        return []
    rows_out: list[list[dict[str, Any]]] = []
    for row in markup.inline_keyboard:
        max_row: list[dict[str, Any]] = []
        for btn in row:
            if btn.url:
                max_row.append(
                    {"type": "link", "text": btn.text, "url": btn.url},
                )
            elif btn.callback_data:
                max_row.append(
                    {
                        "type": "callback",
                        "text": btn.text,
                        "payload": btn.callback_data,
                    },
                )
        if max_row:
            rows_out.append(max_row)
    if not rows_out:
        return []
    return [{"type": "inline_keyboard", "payload": {"buttons": rows_out}}]
