"""Восстановить недостающие ответы по туру R2 после seed_content.

Если у участника ``total_score`` равен числу вопросов тура (6), но часть строк в
``user_answers`` пропала из‑за CASCADE при пересеве вопросов, дописывает
синтетические **верные** ответы на ещё не занятые вопросы. ``total_score`` не
меняется.

Пример::

    cd MAX_Q_Event && source .venv/bin/activate
    export PYTHONPATH=.
    python -m scripts.repair_r2_answers_after_seed
    python -m scripts.repair_r2_answers_after_seed --yes

Без ``--yes`` только отчёт, без записи в БД.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import func, select

from app.core.time import now_utc
from app.db.models import Round, RoundCode, RoundQuestion, UserAnswer, UserRoundProgress


async def _questions_count(session, round_id: int) -> int:
    return int(
        await session.scalar(
            select(func.count()).select_from(RoundQuestion).where(RoundQuestion.round_id == round_id)
        )
        or 0
    )


async def _answered_question_ids(session, user_id: int, round_id: int) -> set[int]:
    r = await session.execute(
        select(UserAnswer.question_id).where(
            UserAnswer.user_id == user_id,
            UserAnswer.round_id == round_id,
        )
    )
    return {int(x) for x in r.scalars().all()}


async def repair_r2_answers_after_seed(session, *, apply: bool) -> dict[str, int]:
    rnd = await session.scalar(select(Round).where(Round.code == RoundCode.R2))
    if rnd is None:
        raise ValueError("Round R2 not found")

    nq = await _questions_count(session, rnd.id)
    if nq <= 0:
        raise ValueError("R2 has no questions")

    q_rows = list(
        (
            await session.execute(
                select(RoundQuestion)
                .where(RoundQuestion.round_id == rnd.id)
                .order_by(RoundQuestion.order_index.asc())
            )
        ).scalars()
    )

    prog_rows = list(
        (
            await session.execute(
                select(UserRoundProgress).where(
                    UserRoundProgress.round_id == rnd.id,
                    UserRoundProgress.total_score == nq,
                )
            )
        ).scalars()
    )

    users_checked = 0
    users_repaired = 0
    answers_inserted = 0

    for prog in prog_rows:
        users_checked += 1
        answered = await _answered_question_ids(session, prog.user_id, rnd.id)
        missing = [q for q in q_rows if q.id not in answered]
        if not missing:
            continue

        users_repaired += 1
        ts = prog.finished_at or prog.last_answer_at or now_utc().replace(tzinfo=None)
        for q in missing:
            answers_inserted += 1
            if apply:
                session.add(
                    UserAnswer(
                        user_id=prog.user_id,
                        round_id=rnd.id,
                        question_id=q.id,
                        selected_option="0",
                        is_correct=True,
                        points_awarded=1,
                        answered_at=ts,
                    )
                )

    return {
        "questions_in_round": nq,
        "users_checked": users_checked,
        "users_repaired": users_repaired,
        "answers_inserted": answers_inserted,
    }


async def _run(*, apply: bool) -> int:
    from app.db.base import dispose_engine, get_session

    try:
        async with get_session() as session:
            stats = await repair_r2_answers_after_seed(session, apply=apply)
            print("Тур R2 — восстановление ответов после seed")
            for k, v in stats.items():
                print(f"  {k}: {v}")
            if stats["answers_inserted"] == 0:
                print("\nНечего дописывать.")
                return 0
            if not apply:
                print(
                    "\nЗапись не выполнялась. Для применения запусти с флагом --yes.",
                    file=sys.stderr,
                )
                return 1
            await session.commit()
            print("\nГотово: недостающие ответы записаны.")
            return 0
    finally:
        await dispose_engine()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--yes",
        action="store_true",
        help="Подтвердить запись в БД",
    )
    args = p.parse_args()
    raise SystemExit(asyncio.run(_run(apply=args.yes)))


if __name__ == "__main__":
    main()
