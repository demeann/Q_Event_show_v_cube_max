"""Стабильный порядок обработки событий в одной пачке GET /updates (MAX)."""

from __future__ import annotations

from typing import Any

# В одном ответе MAX часто отдаёт message_created (/start) и bot_started с payload из ссылки.
# Если обработать /start раньше bot_started — invite_gate ещё пустой → ложное «только по ссылке».
UPDATE_TYPE_ORDER = {"bot_started": 0, "message_callback": 1, "message_created": 2}


def ordered_updates(raw: list[Any]) -> list[dict[str, Any]]:
    updates = [u for u in raw if isinstance(u, dict)]
    updates.sort(
        key=lambda u: UPDATE_TYPE_ORDER.get(str(u.get("update_type") or ""), 99)
    )
    return updates
