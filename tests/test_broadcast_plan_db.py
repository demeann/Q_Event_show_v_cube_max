"""Планирование рассылок: дедуп и получатели (SQLite)."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import func, select

from app.db.models import Broadcast, BroadcastRecipient, User


@pytest.mark.asyncio
async def test_ensure_planned_idempotent(monkeypatch, db_session):
    from app.services import broadcast_plan as bp

    t = datetime(2026, 6, 1, 15, 0, 0)
    slots = [bp.BroadcastSlot("ANNOUNCE_R1", "ALL_VERIFIED", t)]

    async def fake_collect(sess):
        return slots

    monkeypatch.setattr("app.services.broadcast_plan.collect_all_slots", fake_collect)

    db_session.add(
        User(
            id=1,
            telegram_user_id=101,
            email="a@pmru.com",
            email_domain="pmru.com",
            email_verified_at=datetime(2026, 1, 1, 0, 0, 0),
            is_admin=False,
            is_blocked=False,
        )
    )
    await db_session.flush()

    now = datetime(2026, 6, 1, 16, 0, 0)
    n1 = await bp.ensure_planned_broadcasts(db_session, now_naive=now)
    n2 = await bp.ensure_planned_broadcasts(db_session, now_naive=now)
    assert n1 == 1
    assert n2 == 0

    bc_count = await db_session.scalar(select(func.count()).select_from(Broadcast))
    assert bc_count == 1
    rc = await db_session.scalar(select(func.count()).select_from(BroadcastRecipient))
    assert rc == 1


@pytest.mark.asyncio
async def test_ensure_planned_skips_outside_backfill_window(monkeypatch, db_session):
    from app.services import broadcast_plan as bp

    old = datetime(2019, 1, 1, 12, 0, 0)
    slots = [bp.BroadcastSlot("ANNOUNCE_R1", "ALL_VERIFIED", old)]

    async def fake_collect(sess):
        return slots

    monkeypatch.setattr("app.services.broadcast_plan.collect_all_slots", fake_collect)

    db_session.add(
        User(
            id=1,
            telegram_user_id=101,
            email="a@pmru.com",
            email_domain="pmru.com",
            email_verified_at=datetime(2026, 1, 1, 0, 0, 0),
            is_admin=False,
            is_blocked=False,
        )
    )
    await db_session.flush()

    n = await bp.ensure_planned_broadcasts(
        db_session, now_naive=datetime(2026, 6, 1, 16, 0, 0)
    )
    assert n == 0


@pytest.mark.asyncio
async def test_ensure_planned_two_users_two_recipients(monkeypatch, db_session):
    from app.services import broadcast_plan as bp

    t = datetime(2026, 7, 1, 10, 0, 0)
    slots = [bp.BroadcastSlot("RESULT_R1", "ALL_VERIFIED", t)]

    async def fake_collect(sess):
        return slots

    monkeypatch.setattr("app.services.broadcast_plan.collect_all_slots", fake_collect)

    for uid, tg in ((1, 11), (2, 22)):
        db_session.add(
            User(
                id=uid,
                telegram_user_id=tg,
                email=f"u{uid}@pmru.com",
                email_domain="pmru.com",
                email_verified_at=datetime(2026, 1, 1, 0, 0, 0),
                is_admin=False,
                is_blocked=False,
            )
        )
    await db_session.flush()

    await bp.ensure_planned_broadcasts(db_session, now_naive=datetime(2026, 7, 1, 12, 0, 0))
    rc = await db_session.scalar(select(func.count()).select_from(BroadcastRecipient))
    assert rc == 2


@pytest.mark.asyncio
async def test_ensure_planned_segment_not_started(monkeypatch, db_session):
    from app.services import broadcast_plan as bp

    from app.db.models import Round, RoundCode, RoundStatus

    db_session.add(
        Round(
            id=5,
            code=RoundCode.R1,
            name="R1",
            starts_at=datetime(2026, 8, 1, 0, 0, 0),
            ends_at=datetime(2026, 8, 3, 23, 59, 59),
            status=RoundStatus.ACTIVE,
        )
    )
    db_session.add(
        User(
            id=1,
            telegram_user_id=1,
            email="a@pmru.com",
            email_domain="pmru.com",
            email_verified_at=datetime(2026, 1, 1, 0, 0, 0),
            is_admin=False,
            is_blocked=False,
        )
    )
    await db_session.flush()

    t = datetime(2026, 8, 2, 12, 0, 0)
    slots = [bp.BroadcastSlot("REMINDER_R1_NOT_STARTED", "R1_NOT_STARTED", t)]

    async def fake_collect(sess):
        return slots

    monkeypatch.setattr("app.services.broadcast_plan.collect_all_slots", fake_collect)

    await bp.ensure_planned_broadcasts(db_session, now_naive=datetime(2026, 8, 2, 20, 0, 0))
    rc = await db_session.scalar(select(func.count()).select_from(BroadcastRecipient))
    assert rc == 1
