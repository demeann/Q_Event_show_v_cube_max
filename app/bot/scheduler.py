"""Фоновые задачи по расписанию (APScheduler + asyncio)."""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.messaging.broadcast_adapter import BroadcastAdapter
from app.services.tour_start_push import process_due_tour_start_pushes
from app.services.winner_selection import pick_winners_for_due_rounds

log = logging.getLogger(__name__)


def build_scheduler(messenger: BroadcastAdapter) -> AsyncIOScheduler:
    sched = AsyncIOScheduler()
    sched.add_job(
        pick_winners_for_due_rounds,
        "interval",
        minutes=5,
        id="pick_winners_ended_rounds",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
    )

    async def _tour_start_pushes() -> None:
        await process_due_tour_start_pushes(messenger)

    sched.add_job(
        _tour_start_pushes,
        "interval",
        minutes=2,
        id="tour_start_pushes",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
    )
    log.info("Scheduler: winners 5m, tour_start_pushes 2m")
    return sched
