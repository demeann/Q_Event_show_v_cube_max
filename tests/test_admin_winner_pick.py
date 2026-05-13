"""Ручной отбор победителей из админки: `admin_pick_winners_for_round`."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import func, select

import app.db.models  # noqa: F401
from app.db.models import (
    Round,
    RoundCode,
    RoundStatus,
    User,
    UserRoundProgress,
    Winner,
    WinnerSelection,
)
from app.db.models.progress import RoundProgressStatus
from app.services.winner_selection import admin_pick_winners_for_round


@pytest.mark.asyncio
async def test_admin_pick_round_not_found(db_session):
    r = await admin_pick_winners_for_round(
        db_session, RoundCode.R1, now_naive=datetime(2026, 7, 1)
    )
    assert r.status == "round_not_found"


@pytest.mark.asyncio
async def test_admin_pick_too_early(db_session):
    db_session.add(
        Round(
            id=1,
            code=RoundCode.R1,
            name="R1",
            starts_at=datetime(2026, 6, 1),
            ends_at=datetime(2026, 6, 10, 23, 59, 59),
            status=RoundStatus.ACTIVE,
        )
    )
    await db_session.flush()
    r = await admin_pick_winners_for_round(
        db_session, RoundCode.R1, now_naive=datetime(2026, 6, 5)
    )
    assert r.status == "too_early"
    assert r.round_row is not None


@pytest.mark.asyncio
async def test_admin_pick_ok_new(db_session):
    db_session.add(
        Round(
            id=1,
            code=RoundCode.R1,
            name="R1",
            starts_at=datetime(2026, 6, 1),
            ends_at=datetime(2026, 6, 3, 23, 59, 59),
            status=RoundStatus.ACTIVE,
        )
    )
    db_session.add(
        User(
            id=1,
            telegram_user_id=101,
            email="a@pmru.com",
            email_domain="pmru.com",
            email_verified_at=datetime(2026, 1, 1),
            is_admin=False,
            is_blocked=False,
        )
    )
    db_session.add(
        User(
            id=2,
            telegram_user_id=102,
            email="b@pmru.com",
            email_domain="pmru.com",
            email_verified_at=datetime(2026, 1, 1),
            is_admin=False,
            is_blocked=False,
        )
    )
    db_session.add(
        User(
            id=3,
            telegram_user_id=103,
            email="c@pmru.com",
            email_domain="pmru.com",
            email_verified_at=datetime(2026, 1, 1),
            is_admin=False,
            is_blocked=False,
        )
    )
    await db_session.flush()
    db_session.add(
        UserRoundProgress(
            user_id=1,
            round_id=1,
            status=RoundProgressStatus.FINISHED,
            total_score=50,
        )
    )
    db_session.add(
        UserRoundProgress(
            user_id=2,
            round_id=1,
            status=RoundProgressStatus.FINISHED,
            total_score=40,
        )
    )
    db_session.add(
        UserRoundProgress(
            user_id=3,
            round_id=1,
            status=RoundProgressStatus.FINISHED,
            total_score=30,
        )
    )
    await db_session.flush()

    r = await admin_pick_winners_for_round(
        db_session, RoundCode.R1, now_naive=datetime(2026, 6, 5)
    )
    assert r.status == "ok_new"
    assert r.selection is not None
    # Для R1 первый слот — 3-е место в рейтинге (после двух лидеров по баллу).
    assert r.selection.winners_count == 1
    n_win = await db_session.scalar(select(func.count()).select_from(Winner))
    assert n_win == 1
    w_uid = await db_session.scalar(select(Winner.user_id).limit(1))
    assert w_uid == 3


@pytest.mark.asyncio
async def test_admin_pick_ok_existing(db_session):
    db_session.add(
        Round(
            id=1,
            code=RoundCode.R1,
            name="R1",
            starts_at=datetime(2026, 6, 1),
            ends_at=datetime(2026, 6, 3),
            status=RoundStatus.ACTIVE,
        )
    )
    db_session.add(
        User(
            id=1,
            telegram_user_id=101,
            email="a@pmru.com",
            email_domain="pmru.com",
            email_verified_at=datetime(2026, 1, 1),
            is_admin=False,
            is_blocked=False,
        )
    )
    await db_session.flush()
    db_session.add(
        WinnerSelection(
            id=9,
            round_id=1,
            candidates_count=1,
            winners_count=1,
            n_step=0,
            score_threshold=0,
            executed_at=datetime(2026, 6, 4, 12, 0, 0),
            payload={"ordering_strategy": "fixed_list_ranks_v1"},
        )
    )
    await db_session.flush()
    db_session.add(Winner(winner_selection_id=9, user_id=1, position=1))
    await db_session.flush()

    r = await admin_pick_winners_for_round(
        db_session, RoundCode.R1, now_naive=datetime(2026, 6, 5)
    )
    assert r.status == "ok_existing"
    assert r.selection is not None and r.selection.id == 9


@pytest.mark.asyncio
async def test_admin_pick_no_eligible(db_session):
    db_session.add(
        Round(
            id=1,
            code=RoundCode.R1,
            name="R1",
            starts_at=datetime(2026, 6, 1),
            ends_at=datetime(2026, 6, 3),
            status=RoundStatus.ACTIVE,
        )
    )
    await db_session.flush()
    r = await admin_pick_winners_for_round(
        db_session, RoundCode.R1, now_naive=datetime(2026, 6, 5)
    )
    assert r.status == "no_eligible"
