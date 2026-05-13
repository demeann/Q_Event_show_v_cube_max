"""Тур 2 «Своя игра»: темы по 2 вопроса, ошибка по теме закрывает тему, баллы не снимаются."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import now_utc
from app.db.models import (
    Round,
    RoundQuestion,
    UserAnswer,
    UserRoundProgress,
    UserTopicProgress,
)
from app.db.models.progress import RoundProgressStatus, TopicStatus


def _options_from_payload(payload: dict[str, Any]) -> list[str]:
    raw = payload.get("options")
    if not isinstance(raw, list) or not raw:
        raise ValueError("question payload missing options")
    return [str(x) for x in raw]


def _correct_index(payload: dict[str, Any]) -> int:
    idx = payload.get("correct_index")
    if idx is None:
        raise ValueError("question payload missing correct_index")
    return int(idx)


async def _get_or_create_round_progress(
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


async def mark_round2_started_if_needed(
    session: AsyncSession, progress: UserRoundProgress
) -> None:
    if progress.status == RoundProgressStatus.NOT_STARTED:
        progress.status = RoundProgressStatus.IN_PROGRESS
        progress.started_at = now_utc().replace(tzinfo=None)


async def ordered_topic_codes(session: AsyncSession, round_id: int) -> list[str]:
    r = await session.execute(
        select(RoundQuestion)
        .where(
            RoundQuestion.round_id == round_id,
            RoundQuestion.topic_code.isnot(None),
        )
        .order_by(RoundQuestion.order_index.asc())
    )
    out: list[str] = []
    seen: set[str] = set()
    for q in r.scalars():
        tc = q.topic_code
        if tc and tc not in seen:
            seen.add(tc)
            out.append(tc)
    return out


async def get_topic_progress_row(
    session: AsyncSession, user_id: int, round_id: int, topic_code: str
) -> UserTopicProgress | None:
    r = await session.execute(
        select(UserTopicProgress).where(
            UserTopicProgress.user_id == user_id,
            UserTopicProgress.round_id == round_id,
            UserTopicProgress.topic_code == topic_code,
        )
    )
    return r.scalar_one_or_none()


async def open_topic_for_user(
    session: AsyncSession, user_id: int, round_id: int, topic_code: str
) -> tuple[UserTopicProgress | None, str]:
    existing = await get_topic_progress_row(session, user_id, round_id, topic_code)
    if existing is not None:
        if existing.status == TopicStatus.CLOSED:
            return None, "Эта тема уже закрыта для тебя."
        return existing, ""  # already OPEN, resume
    row = UserTopicProgress(
        user_id=user_id,
        round_id=round_id,
        topic_code=topic_code,
        status=TopicStatus.OPEN,
        score=0,
    )
    session.add(row)
    await session.flush()
    return row, ""


async def questions_in_topic_ordered(
    session: AsyncSession, round_id: int, topic_code: str
) -> list[RoundQuestion]:
    r = await session.execute(
        select(RoundQuestion)
        .where(
            RoundQuestion.round_id == round_id,
            RoundQuestion.topic_code == topic_code,
        )
        .order_by(RoundQuestion.order_index.asc())
    )
    return list(r.scalars().all())


async def _answer_for_question(
    session: AsyncSession, user_id: int, question_id: int
) -> UserAnswer | None:
    r = await session.execute(
        select(UserAnswer).where(
            UserAnswer.user_id == user_id,
            UserAnswer.question_id == question_id,
        )
    )
    return r.scalar_one_or_none()


async def first_unanswered_in_topic(
    session: AsyncSession,
    user_id: int,
    round_id: int,
    topic_code: str,
) -> RoundQuestion | None:
    for q in await questions_in_topic_ordered(session, round_id, topic_code):
        if await _answer_for_question(session, user_id, q.id) is None:
            return q
    return None


async def get_resume_question_r2(
    session: AsyncSession,
    user_id: int,
    round_row: Round,
) -> RoundQuestion | None:
    """Если есть незакрытая тема с неотвеченным вопросом — вернуть его."""
    topics = await ordered_topic_codes(session, round_row.id)
    for tcode in topics:
        tp = await get_topic_progress_row(session, user_id, round_row.id, tcode)
        if tp is None or tp.status != TopicStatus.OPEN:
            continue
        qs = await questions_in_topic_ordered(session, round_row.id, tcode)
        for q in qs:
            ans = await _answer_for_question(session, user_id, q.id)
            if ans is None:
                return q
    return None


async def all_r2_topics_finished_for_user(
    session: AsyncSession, user_id: int, round_id: int, topic_codes: list[str]
) -> bool:
    for t in topic_codes:
        tp = await get_topic_progress_row(session, user_id, round_id, t)
        if tp is None or tp.status != TopicStatus.CLOSED:
            return False
    return True


async def topics_available_to_open(
    session: AsyncSession, user_id: int, round_id: int, topic_codes: list[str]
) -> list[str]:
    return [t for t in topic_codes if await get_topic_progress_row(session, user_id, round_id, t) is None]


async def try_answer_round2(
    session: AsyncSession,
    *,
    user_id: int,
    round_row: Round,
    question: RoundQuestion,
    selected_idx: int,
) -> tuple[bool, int, str | None]:
    """Записать ответ в теме. Закрывает тему при ошибке или после 2-го вопроса.

    Возвращает (ok, points_for_user_message, err): в счёт тура в БД идёт **1** за верный
    ответ; второе число — ``question.points`` при верном ответе (для фразы «+N баллов» в UI).
    """
    if question.topic_code is None:
        return False, 0, "Внутренняя ошибка темы."

    options = _options_from_payload(question.payload)
    if not (0 <= selected_idx < len(options)):
        return False, 0, "Некорректный вариант."

    tp = await get_topic_progress_row(session, user_id, round_row.id, question.topic_code)
    if tp is None:
        return False, 0, "Сначала выбери тему в меню тура."
    if tp.status != TopicStatus.OPEN:
        return False, 0, "Эта тема уже закрыта."

    qs_ordered = await questions_in_topic_ordered(session, round_row.id, question.topic_code)
    if question.id not in {q.id for q in qs_ordered}:
        return False, 0, "Вопрос не из этой темы."

    try:
        q_index = next(i for i, q in enumerate(qs_ordered) if q.id == question.id)
    except StopIteration:
        return False, 0, "Вопрос устарел."

    for j in range(q_index):
        prev = qs_ordered[j]
        prev_ans = await _answer_for_question(session, user_id, prev.id)
        if prev_ans is None:
            return False, 0, "Сначала ответь на предыдущий вопрос темы."
        if not prev_ans.is_correct:
            return False, 0, "Тема уже закрыта из‑за прошлого ответа."

    existing = await _answer_for_question(session, user_id, question.id)
    if existing is not None:
        return False, 0, "Ты уже отвечал на этот вопрос."

    corr = _correct_index(question.payload)
    is_correct = selected_idx == corr
    score_increment = 1 if is_correct else 0
    display_points = question.points if is_correct else 0
    now_naive = now_utc().replace(tzinfo=None)

    rp = await _get_or_create_round_progress(session, user_id, round_row.id)
    await mark_round2_started_if_needed(session, rp)

    session.add(
        UserAnswer(
            user_id=user_id,
            round_id=round_row.id,
            question_id=question.id,
            selected_option=str(selected_idx),
            is_correct=is_correct,
            points_awarded=score_increment,
            answered_at=now_naive,
        )
    )

    rp.total_score += score_increment
    rp.last_answer_at = now_naive
    tp.score += score_increment

    is_last_in_topic = q_index == len(qs_ordered) - 1
    if (not is_correct) or is_last_in_topic:
        tp.status = TopicStatus.CLOSED

    topics = await ordered_topic_codes(session, round_row.id)
    if await all_r2_topics_finished_for_user(session, user_id, round_row.id, topics):
        rp.status = RoundProgressStatus.FINISHED
        rp.finished_at = now_naive

    # Второе значение — «вес» вопроса для текста пользователю; в БД считаем только верные ответы.
    return True, display_points, None


async def ensure_r2_round_started_on_show(
    session: AsyncSession, user_id: int, round_row: Round
) -> None:
    rp = await _get_or_create_round_progress(session, user_id, round_row.id)
    await mark_round2_started_if_needed(session, rp)


async def round2_needs_go_button(
    session: AsyncSession, user_id: int, round_id: int
) -> bool:
    """True, если тур ещё не начат — показываем вступление и кнопку «Поехали»."""
    rp = await _get_or_create_round_progress(session, user_id, round_id)
    return rp.status == RoundProgressStatus.NOT_STARTED
