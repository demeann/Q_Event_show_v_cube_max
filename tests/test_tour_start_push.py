"""Пуши старта тура: не дублировать через /play; не слать после ends_at."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.db.models import Round, User, UserRoundProgress
from app.db.models.progress import RoundProgressStatus
from app.db.models.round import RoundCode, RoundStatus
from app.services.tour_start_push import try_send_tour_push_for_user


@pytest.mark.asyncio
async def test_try_send_skips_when_user_has_round_progress(db_session, monkeypatch):
    async def boom(*_a, **_kw):
        raise AssertionError("send_tour_intro_with_keyboard must not be called")

    msgr = AsyncMock()
    msgr.send_tour_intro_with_keyboard = boom

    u = User(
        telegram_user_id=424242,
        email_verified_at=datetime(2026, 1, 1, 12, 0, 0),
    )
    db_session.add(u)
    rnd = Round(
        code=RoundCode.R1,
        name="Тур 1",
        starts_at=datetime(2026, 1, 1, 0, 0, 0),
        ends_at=datetime(2030, 1, 1, 0, 0, 0),
        status=RoundStatus.ACTIVE,
    )
    db_session.add(rnd)
    await db_session.flush()

    db_session.add(
        UserRoundProgress(
            user_id=u.id,
            round_id=rnd.id,
            status=RoundProgressStatus.NOT_STARTED,
            total_score=0,
        )
    )
    await db_session.flush()

    await try_send_tour_push_for_user(db_session, msgr, user_id=u.id, round_row=rnd)
    assert u.tour_push_r1_sent_at is None


@pytest.mark.asyncio
async def test_try_send_when_no_progress(db_session):
    calls: list[int] = []

    async def fake_send(*_a, **_kw):
        calls.append(1)

    msgr = AsyncMock()
    msgr.send_tour_intro_with_keyboard = fake_send

    u = User(
        telegram_user_id=424243,
        email_verified_at=datetime(2026, 1, 1, 12, 0, 0),
    )
    db_session.add(u)
    rnd = Round(
        code=RoundCode.R1,
        name="Тур 1",
        starts_at=datetime(2026, 1, 1, 0, 0, 0),
        ends_at=datetime(2030, 1, 1, 0, 0, 0),
        status=RoundStatus.ACTIVE,
    )
    db_session.add(rnd)
    await db_session.flush()

    await try_send_tour_push_for_user(db_session, msgr, user_id=u.id, round_row=rnd)
    assert len(calls) == 1
    assert u.tour_push_r1_sent_at is not None


@pytest.mark.asyncio
async def test_try_send_skips_when_round_window_ended(db_session, monkeypatch):
    async def boom(*_a, **_kw):
        raise AssertionError("send_tour_intro_with_keyboard must not be called")

    msgr = AsyncMock()
    msgr.send_tour_intro_with_keyboard = boom
    monkeypatch.setattr(
        "app.services.tour_start_push.now_utc",
        lambda: datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
    )

    u = User(
        telegram_user_id=424244,
        email_verified_at=datetime(2026, 1, 1, 12, 0, 0),
    )
    db_session.add(u)
    rnd = Round(
        code=RoundCode.R1,
        name="Тур 1",
        starts_at=datetime(2026, 1, 1, 0, 0, 0),
        ends_at=datetime(2026, 1, 10, 0, 0, 0),
        status=RoundStatus.ACTIVE,
    )
    db_session.add(rnd)
    await db_session.flush()

    await try_send_tour_push_for_user(db_session, msgr, user_id=u.id, round_row=rnd)
    assert u.tour_push_r1_sent_at is None
