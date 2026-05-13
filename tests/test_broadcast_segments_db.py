"""Сегменты рассылок: SQLite."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select

from app.db.models import (
    Round,
    RoundCode,
    RoundProgressStatus,
    RoundStatus,
    User,
    UserRoundProgress,
)
from app.services.broadcast_segments import fetch_segment_user_ids, parse_round_code_from_segment


async def _user(
    session,
    *,
    uid: int,
    tg: int,
    email_verified: bool = True,
    blocked: bool = False,
    is_admin: bool = False,
) -> User:
    now = datetime(2026, 1, 1, 12, 0, 0)
    u = User(
        id=uid,
        telegram_user_id=tg,
        email=("u@test.pmru.com" if email_verified else None),
        email_domain=("test.pmru.com" if email_verified else None),
        email_verified_at=(now if email_verified else None),
        is_admin=is_admin,
        is_blocked=blocked,
    )
    session.add(u)
    await session.flush()
    return u


async def _round(
    session,
    *,
    rid: int,
    code: RoundCode = RoundCode.R1,
) -> Round:
    r = Round(
        id=rid,
        code=code,
        name=code.value,
        starts_at=datetime(2026, 5, 1, 0, 0, 0),
        ends_at=datetime(2026, 5, 3, 23, 59, 59),
        status=RoundStatus.ACTIVE,
    )
    session.add(r)
    await session.flush()
    return r


@pytest.mark.asyncio
async def test_all_verified_sorted_by_id(db_session):
    await _user(db_session, uid=1, tg=200)
    await _user(db_session, uid=2, tg=100)
    ids = await fetch_segment_user_ids(
        db_session, segment_code="ALL_VERIFIED", round_id=None
    )
    assert ids == [1, 2]


@pytest.mark.asyncio
async def test_all_verified_blocked_excluded(db_session):
    await _user(db_session, uid=1, tg=1)
    await _user(db_session, uid=2, tg=2, blocked=True)
    ids = await fetch_segment_user_ids(
        db_session, segment_code="ALL_VERIFIED", round_id=None
    )
    assert ids == [1]


@pytest.mark.asyncio
async def test_all_verified_admin_without_email_included(db_session):
    await _user(db_session, uid=1, tg=1, email_verified=False, is_admin=True)
    await _user(db_session, uid=2, tg=2, email_verified=False, is_admin=False)
    ids = await fetch_segment_user_ids(
        db_session, segment_code="ALL_VERIFIED", round_id=None
    )
    assert ids == [1]


@pytest.mark.asyncio
async def test_not_started_no_progress(db_session):
    r = await _round(db_session, rid=1)
    await _user(db_session, uid=1, tg=10)
    await _user(db_session, uid=2, tg=20)
    ids = await fetch_segment_user_ids(
        db_session, segment_code="R1_NOT_STARTED", round_id=r.id
    )
    assert sorted(ids) == [1, 2]


@pytest.mark.asyncio
async def test_not_started_excludes_in_progress(db_session):
    r = await _round(db_session, rid=1)
    await _user(db_session, uid=1, tg=1)
    u_prog = await _user(db_session, uid=2, tg=2)
    db_session.add(
        UserRoundProgress(
            id=1,
            user_id=u_prog.id,
            round_id=r.id,
            status=RoundProgressStatus.IN_PROGRESS,
            total_score=10,
        )
    )
    await db_session.flush()
    ids = await fetch_segment_user_ids(
        db_session, segment_code="R1_NOT_STARTED", round_id=r.id
    )
    assert ids == [1]


@pytest.mark.asyncio
async def test_not_started_includes_explicit_not_started_status(db_session):
    r = await _round(db_session, rid=1)
    u = await _user(db_session, uid=1, tg=5)
    db_session.add(
        UserRoundProgress(
            id=1,
            user_id=u.id,
            round_id=r.id,
            status=RoundProgressStatus.NOT_STARTED,
            total_score=0,
        )
    )
    await db_session.flush()
    ids = await fetch_segment_user_ids(
        db_session, segment_code="R1_NOT_STARTED", round_id=r.id
    )
    assert u.id in ids


@pytest.mark.asyncio
async def test_not_finished_includes_in_progress(db_session):
    r = await _round(db_session, rid=10, code=RoundCode.R2)
    u = await _user(db_session, uid=1, tg=7)
    db_session.add(
        UserRoundProgress(
            id=1,
            user_id=u.id,
            round_id=r.id,
            status=RoundProgressStatus.IN_PROGRESS,
            total_score=3,
        )
    )
    await db_session.flush()
    ids = await fetch_segment_user_ids(
        db_session, segment_code="R2_NOT_FINISHED", round_id=r.id
    )
    assert ids == [1]


@pytest.mark.asyncio
async def test_not_finished_excludes_finished(db_session):
    r = await _round(db_session, rid=10, code=RoundCode.R2)
    u = await _user(db_session, uid=1, tg=8)
    db_session.add(
        UserRoundProgress(
            id=1,
            user_id=u.id,
            round_id=r.id,
            status=RoundProgressStatus.FINISHED,
            total_score=100,
        )
    )
    await db_session.flush()
    ids = await fetch_segment_user_ids(
        db_session, segment_code="R2_NOT_FINISHED", round_id=r.id
    )
    assert ids == []


@pytest.mark.asyncio
async def test_not_started_round_id_none_returns_empty(db_session):
    await _user(db_session, uid=1, tg=1)
    ids = await fetch_segment_user_ids(
        db_session, segment_code="R1_NOT_STARTED", round_id=None
    )
    assert ids == []


@pytest.mark.asyncio
async def test_all_rounds_finished_requires_three_finished_progress(db_session):
    from app.db.models import RoundStatus

    for rid, code in ((1, RoundCode.R1), (2, RoundCode.R2), (3, RoundCode.R3)):
        db_session.add(
            Round(
                id=rid,
                code=code,
                name=code.value,
                starts_at=datetime(2026, 5, 1, 0, 0, 0),
                ends_at=datetime(2026, 5, 3, 23, 59, 59),
                status=RoundStatus.ACTIVE,
            )
        )
    await _user(db_session, uid=1, tg=1)
    await _user(db_session, uid=2, tg=2)
    await db_session.flush()

    for uid, rid in ((1, 1), (1, 2), (1, 3)):
        db_session.add(
            UserRoundProgress(
                user_id=uid,
                round_id=rid,
                status=RoundProgressStatus.FINISHED,
                total_score=10,
            )
        )
    db_session.add(
        UserRoundProgress(
            user_id=2,
            round_id=1,
            status=RoundProgressStatus.FINISHED,
            total_score=10,
        )
    )
    await db_session.flush()

    ids = await fetch_segment_user_ids(
        db_session, segment_code="ALL_ROUNDS_FINISHED", round_id=None
    )
    assert ids == [1]


@pytest.mark.asyncio
async def test_unknown_segment_returns_empty(db_session):
    await _user(db_session, uid=1, tg=1)
    ids = await fetch_segment_user_ids(
        db_session, segment_code="WEIRD_SEGMENT", round_id=None
    )
    assert ids == []


def test_parse_round_code_variants():
    assert parse_round_code_from_segment("ALL_VERIFIED") is None
    assert parse_round_code_from_segment("ALL_ROUNDS_FINISHED") is None
    assert parse_round_code_from_segment("R3_NOT_FINISHED").value == "R3"
    assert parse_round_code_from_segment("XX_NOT_STARTED") is None
