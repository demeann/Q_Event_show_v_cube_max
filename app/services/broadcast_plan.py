"""Планирование массовых рассылок (legacy).

Раньше здесь создавались записи ``Broadcast`` по слотам ANNOUNCE / REMINDER / RESULT.
Сейчас используются только три стартовых пуша туров — см. ``app.services.tour_start_push``.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


async def ensure_planned_broadcasts(session, *, now_naive) -> int:  # noqa: ANN001, ARG001
    """Оставлено для совместимости; новых рассылок не планирует."""
    return 0


async def plan_broadcasts_job() -> None:
    """Пустая задача: планировщик старых рассылок отключён."""
    return


async def collect_all_slots(session) -> list:  # noqa: ANN001, ARG001
    return []
