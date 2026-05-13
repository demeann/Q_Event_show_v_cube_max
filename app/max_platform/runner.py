"""Запуск MAX: long poll + те же фоновые задачи, что у Telegram-бота."""

from __future__ import annotations

import logging

from app.bot.scheduler import build_scheduler
from app.core.config import get_settings
from app.db.base import dispose_engine
from app.max_platform.client import MaxPlatformClient
from app.max_platform.dispatcher import MaxUpdateDispatcher
from app.messaging.broadcast_adapter import MaxBroadcastAdapter

log = logging.getLogger(__name__)


async def run_max_polling() -> None:
    settings = get_settings()
    client = MaxPlatformClient(settings.api_access_token)
    messenger = MaxBroadcastAdapter(client)
    scheduler = build_scheduler(messenger)
    scheduler.start()
    dispatcher = MaxUpdateDispatcher(client)
    log.info("MAX messenger long polling started (GET /updates)")
    try:
        await dispatcher.run_forever()
    finally:
        scheduler.shutdown(wait=False)
        await client.aclose()
        await dispose_engine()
        log.info("MAX messenger stopped")
