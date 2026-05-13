"""Ранжирование участников тура для отбора победителей и выгрузок.

Порядок (сверху вниз):
1. Баллы по убыванию.
2. При равных баллах — раньше время последнего ответа в туре (меньше ``answered_at``).
3. При равенстве — ``user_id`` по возрастанию (детерминизм).

Победители — участники с **фиксированными порядковыми номерами** (1-based) в этом списке
после сортировки (конфиг по коду тура).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Round, RoundCode, RoundQuestion, User, UserAnswer, UserRoundProgress

# Порядковые номера победителей в отсортированном списке (1 = первый сверху).
WINNER_LIST_RANKS_BY_ROUND: dict[RoundCode, list[int]] = {
    RoundCode.R1: [3, 97, 189, 277, 378, 455, 546, 632, 720],
    RoundCode.R2: [53, 161, 239, 348, 402, 468, 502, 658, 704],
    RoundCode.R3: [69, 114, 215, 300, 356, 472, 538, 616, 735],
}

_LAST_ANS_NULL_SORT = datetime(3000, 1, 1, 0, 0, 0)


@dataclass(frozen=True)
class RankedParticipant:
    user_id: int
    total_score: int
    last_answer_at: datetime | None
    perfect_all: bool


def sort_participant_rows(
    rows: list[RankedParticipant],
) -> list[RankedParticipant]:
    """Стабильная сортировка под правила конкурса."""
    return sorted(
        rows,
        key=lambda r: (
            -r.total_score,
            r.last_answer_at if r.last_answer_at is not None else _LAST_ANS_NULL_SORT,
            r.user_id,
        ),
    )


def pick_winners_by_fixed_list_ranks(
    ordered_user_ids: list[int],
    ranks: list[int],
) -> tuple[list[int], list[int], list[int]]:
    """По номерам мест в списке (1-based). Возвращает (user_ids по порядку слотов, занятые номера, пропущенные номера)."""
    winners: list[int] = []
    filled: list[int] = []
    missing: list[int] = []
    n = len(ordered_user_ids)
    for rank in ranks:
        if rank < 1 or rank > n:
            missing.append(rank)
            continue
        winners.append(ordered_user_ids[rank - 1])
        filled.append(rank)
    return winners, filled, missing


def selection_note_ru(filled_ranks: list[int], missing_ranks: list[int]) -> str | None:
    """Текст предупреждения для выгрузки, если не все номера «достались» из списка."""
    if not missing_ranks:
        return None
    fr = ", ".join(str(x) for x in filled_ranks)
    mr = ", ".join(str(x) for x in missing_ranks)
    return (
        f"Выбраны победители только под номерами в рейтинге: {fr}. "
        f"Под номерами {mr} победители не выбраны (в рейтинге недостаточно участников)."
    )


async def _questions_count(session: AsyncSession, round_id: int) -> int:
    return int(
        await session.scalar(
            select(func.count()).select_from(RoundQuestion).where(RoundQuestion.round_id == round_id)
        )
        or 0
    )


async def _perfect_user_ids(session: AsyncSession, round_id: int, n_questions: int) -> set[int]:
    """Все вопросы тура отвечены и все ответы верные."""
    if n_questions <= 0:
        return set()
    stmt = (
        select(UserAnswer.user_id)
        .where(UserAnswer.round_id == round_id)
        .group_by(UserAnswer.user_id)
        .having(
            func.count(UserAnswer.id) == n_questions,
            func.min(UserAnswer.is_correct) == True,  # noqa: E712
        )
    )
    r = await session.execute(stmt)
    return {int(x) for x in r.scalars().all()}


def _base_eligible_stmt(round_id: int) -> Select[Any]:
    return (
        select(User.id, UserRoundProgress.total_score)
        .join(
            UserRoundProgress,
            (UserRoundProgress.user_id == User.id) & (UserRoundProgress.round_id == round_id),
        )
        .where(
            User.is_blocked.is_(False),
            or_(User.email_verified_at.isnot(None), User.is_admin.is_(True)),
        )
    )


async def fetch_ranked_participants(session: AsyncSession, round_row: Round) -> list[RankedParticipant]:
    """Участники тура с фильтром eligibility, отсортированные для конкурса."""
    nq = await _questions_count(session, round_row.id)
    perfect = await _perfect_user_ids(session, round_row.id, nq)

    base = await session.execute(_base_eligible_stmt(round_row.id))
    raw: list[tuple[int, int]] = [(int(uid), int(tscore or 0)) for uid, tscore in base.all()]
    if not raw:
        return []

    uids = [t[0] for t in raw]
    tstmt = (
        select(UserAnswer.user_id, func.max(UserAnswer.answered_at))
        .where(UserAnswer.round_id == round_row.id, UserAnswer.user_id.in_(uids))
        .group_by(UserAnswer.user_id)
    )
    tr = await session.execute(tstmt)
    last_by: dict[int, datetime | None] = {int(u): la for u, la in tr.all()}

    rows: list[RankedParticipant] = []
    for uid, score in raw:
        rows.append(
            RankedParticipant(
                user_id=uid,
                total_score=score,
                last_answer_at=last_by.get(uid),
                perfect_all=uid in perfect,
            )
        )
    return sort_participant_rows(rows)


async def ordered_user_ids_for_round(session: AsyncSession, round_row: Round) -> list[int]:
    ranked = await fetch_ranked_participants(session, round_row)
    return [p.user_id for p in ranked]
