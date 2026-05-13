"""Фоновые задачи по расписанию (APScheduler + asyncio)."""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.messaging.broadcast_adapter import BroadcastAdapter
from app.services.broadcast_dispatch import process_due_broadcasts
from app.services.broadcast_plan import plan_broadcasts_job
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
    sched.add_job(
        plan_broadcasts_job,
        "interval",
        hours=1,
        id="plan_broadcasts",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )

    async def _run_broadcasts() -> None:
        await process_due_broadcasts(messenger)

    sched.add_job(
        _run_broadcasts,
        "interval",
        minutes=1,
        id="dispatch_broadcasts",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
    )
    log.info(
        "Scheduler: winners 5m, plan_broadcasts 1h, dispatch_broadcasts 1m"
    )
    return sched
