"""Long polling обновлений MAX для отладки (см. GET /updates)."""

from __future__ import annotations

import asyncio
import json
import logging
import sys

from app.core.config import get_settings
from app.max_platform.client import MaxPlatformClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


async def _main() -> None:
    settings = get_settings()
    token = settings.api_access_token
    if not token or len(token.strip()) < 10:
        log.error("Нет MAX_ACCESS_TOKEN (или legacy BOT_TOKEN) в .env")
        sys.exit(1)

    client = MaxPlatformClient(token)
    marker: int | None = None
    try:
        me = await client.get_me()
        log.info("me: %s", json.dumps(me, ensure_ascii=False)[:500])
        while True:
            data = await client.get_updates(
                marker=marker,
                types=["message_created", "message_callback", "bot_started"],
                timeout=45,
            )
            updates = data.get("updates") or []
            marker = data.get("marker")
            for u in updates:
                log.info("update: %s", json.dumps(u, ensure_ascii=False)[:2000])
            if not updates:
                log.debug("marker=%s пустая пачка", marker)
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(_main())
