"""Абстракции отправки сообщений (Telegram / MAX)."""

from __future__ import annotations

from app.messaging.broadcast_adapter import MaxBroadcastAdapter, TelegramBroadcastAdapter
from app.messaging.errors import MessengerBadRequestError, MessengerForbiddenError

__all__ = [
    "MessengerBadRequestError",
    "MessengerForbiddenError",
    "TelegramBroadcastAdapter",
    "MaxBroadcastAdapter",
]
