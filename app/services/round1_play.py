"""Игровая логика Тура 1 (миллионер): вопросы по порядку, одна попытка."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import now_utc
from app.db.models import (
    Round,
    RoundQuestion,
    UserAnswer,
    UserRoundProgress,
)
from app.db.models.progress import RoundProgressStatus


async def _get_or_create_progress(
    session: AsyncSession, user_id: int, round_id: int
) -> UserRoundProgress:
    r = await session.execute(
        select(UserRoundProgress).where(
            UserRoundProgress.user_id == user_id,
            UserRoundProgress.round_id == round_id,
        )
    )
    row = r.scalar_one_or_none()
    if row is None:
        row = UserRoundProgress(
            user_id=user_id,
            round_id=round_id,
            status=RoundProgressStatus.NOT_STARTED,
            total_score=0,
        )
        session.add(row)
        await session.flush()
    return row


async def _answered_question_ids(
    session: AsyncSession, user_id: int, round_id: int
) -> set[int]:
    r = await session.execute(
        select(UserAnswer.question_id).where(
            UserAnswer.user_id == user_id,
            UserAnswer.round_id == round_id,
        )
    )
    return set(r.scalars().all())


async def get_next_round1_question(
    session: AsyncSession, user_id: int, round_row: Round
) -> RoundQuestion | None:
    """Следующий неотвеченный вопрос по order_index или None, если все отвечены."""
    progress = await _get_or_create_progress(session, user_id, round_row.id)
    if progress.status == RoundProgressStatus.FINISHED:
        return None

    answered = await _answered_question_ids(session, user_id, round_row.id)
    r = await session.execute(
        select(RoundQuestion)
        .where(RoundQuestion.round_id == round_row.id)
        .order_by(RoundQuestion.order_index.asc())
    )
    questions = list(r.scalars().all())
    for q in questions:
        if q.id not in answered:
            return q
    return None


async def mark_round1_started_if_needed(
    session: AsyncSession, progress: UserRoundProgress
) -> None:
    if progress.status == RoundProgressStatus.NOT_STARTED:
        progress.status = RoundProgressStatus.IN_PROGRESS
        progress.started_at = now_utc().replace(tzinfo=None)


async def on_question_shown(
    session: AsyncSession, user_id: int, round_row: Round
) -> None:
    """Вызывать при показе очередного вопроса (ставит IN_PROGRESS и started_at)."""
    progress = await _get_or_create_progress(session, user_id, round_row.id)
    await mark_round1_started_if_needed(session, progress)


def _payload_options(payload: dict[str, Any]) -> list[str]:
    raw = payload.get("options")
    if not isinstance(raw, list) or not raw:
        raise ValueError("question payload missing options")
    return [str(x) for x in raw]


def correct_index(payload: dict[str, Any]) -> int:
    idx = payload.get("correct_index")
    if idx is None:
        raise ValueError("question payload missing correct_index")
    return int(idx)


async def try_answer_round1(
    session: AsyncSession,
    *,
    user_id: int,
    round_row: Round,
    question: RoundQuestion,
    selected_idx: int,
) -> tuple[bool, int, str | None]:
    """Записать ответ. Возвращает (успех_записи, очки_для_текста_юзеру, текст_ошибки).

    В прогрессе и ``UserAnswer.points_awarded`` — **1 за верный / 0 за неверный**
    (рейтинг и выгрузки = число верных ответов по туру). Второе значение для UI —
    ``question.points`` при верном ответе и 0 при неверном (подпись «ставки» в копирайте).
    """
    options = _payload_options(question.payload)
    if not (0 <= selected_idx < len(options)):
        return False, 0, "Некорректный вариант."

    corr = correct_index(question.payload)
    is_correct = selected_idx == corr
    awarded = 1 if is_correct else 0
    now_naive = now_utc().replace(tzinfo=None)

    progress = await _get_or_create_progress(session, user_id, round_row.id)
    answered = await _answered_questions_count(session, user_id, round_row.id)
    total_q = await session.scalar(
        select(func.count()).select_from(RoundQuestion).where(
            RoundQuestion.round_id == round_row.id
        )
    )
    if total_q is None or total_q == 0:
        return False, 0, "В туре нет вопросов."

    existing = await session.execute(
        select(UserAnswer.id).where(
            UserAnswer.user_id == user_id,
            UserAnswer.question_id == question.id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        return False, 0, "Ты уже отвечал на этот вопрос."

    session.add(
        UserAnswer(
            user_id=user_id,
            round_id=round_row.id,
            question_id=question.id,
            selected_option=str(selected_idx),
            is_correct=is_correct,
            points_awarded=awarded,
            answered_at=now_naive,
        )
    )

    progress.total_score += awarded
    progress.last_answer_at = now_naive
    await mark_round1_started_if_needed(session, progress)

    if answered + 1 >= int(total_q):
        progress.status = RoundProgressStatus.FINISHED
        progress.finished_at = now_naive

    return True, awarded, None


async def count_round_answers(
    session: AsyncSession, user_id: int, round_id: int
) -> int:
    """Сколько ответов пользователь уже дал в туре (для вступительного текста и т.п.)."""
    return await _answered_questions_count(session, user_id, round_id)


async def _answered_questions_count(
    session: AsyncSession, user_id: int, round_id: int
) -> int:
    c = await session.scalar(
        select(func.count()).select_from(UserAnswer).where(
            UserAnswer.user_id == user_id,
            UserAnswer.round_id == round_id,
        )
    )
    return int(c or 0)


def format_correct_answer_line(payload: dict[str, Any]) -> str:
    options = _payload_options(payload)
    ci = correct_index(payload)
    return f"\n\nПравильный ответ: <b>{options[ci]}</b>"
