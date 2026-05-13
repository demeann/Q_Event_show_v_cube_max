"""Сброс прогресса админом для тестов."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import func, select

from app.db.models import (
    Round,
    RoundCode,
    RoundProgressStatus,
    RoundQuestion,
    RoundStatus,
    User,
    UserAnswer,
    UserRoundProgress,
    UserTopicProgress,
    Winner,
    WinnerSelection,
)
from app.db.models.progress import TopicStatus
from app.services.admin_progress_reset import reset_all_game_progress_for_user


@pytest.mark.asyncio
async def test_reset_all_game_progress_for_user_clears_related_rows(db_session):
    db_session.add(
        Round(
            id=1,
            code=RoundCode.R1,
            name="R1",
            starts_at=datetime(2026, 5, 1),
            ends_at=datetime(2026, 5, 10),
            status=RoundStatus.ACTIVE,
        )
    )
    db_session.add(User(id=10, telegram_user_id=999001, is_blocked=False))
    db_session.add(
        RoundQuestion(
            id=100,
            round_id=1,
            code="R1Q1",
            order_index=1,
            topic_code=None,
            points=100,
            payload={"text": "?", "options": ["a", "b"], "correct_index": 0},
        )
    )
    await db_session.flush()
    db_session.add(
        UserRoundProgress(
            user_id=10,
            round_id=1,
            status=RoundProgressStatus.FINISHED,
            total_score=100,
        )
    )
    db_session.add(
        UserTopicProgress(
            user_id=10,
            round_id=1,
            topic_code="T1",
            status=TopicStatus.CLOSED,
            score=50,
        )
    )
    db_session.add(
        UserAnswer(
            user_id=10,
            round_id=1,
            question_id=100,
            selected_option="0",
            is_correct=True,
            points_awarded=100,
            answered_at=datetime(2026, 5, 2, 12, 0, 0),
        )
    )
    db_session.add(
        WinnerSelection(
            round_id=1,
            candidates_count=1,
            winners_count=1,
            n_step=0,
            ordering_strategy="fixed_list_ranks_v1",
            score_threshold=0,
            executed_at=datetime(2026, 5, 11, 12, 0, 0),
            payload={},
        )
    )
    await db_session.flush()
    wsel_id = await db_session.scalar(
        select(WinnerSelection.id).where(WinnerSelection.round_id == 1)
    )
    db_session.add(Winner(winner_selection_id=wsel_id, user_id=10, position=1))
    await db_session.flush()

    stats = await reset_all_game_progress_for_user(db_session, 10)
    await db_session.commit()

    assert stats["answers"] >= 1
    assert stats["round_progress"] >= 1
    assert stats["topic_progress"] >= 1
    assert stats["winners"] >= 1

    n_ans = int(
        await db_session.scalar(
            select(func.count()).select_from(UserAnswer).where(UserAnswer.user_id == 10)
        )
        or 0
    )
    assert n_ans == 0
    n_rp = int(
        await db_session.scalar(
            select(func.count())
            .select_from(UserRoundProgress)
            .where(UserRoundProgress.user_id == 10)
        )
        or 0
    )
    assert n_rp == 0
