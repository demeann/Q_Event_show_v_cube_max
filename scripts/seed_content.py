"""Идемпотентный сидер: туры (старт 10:00 МСК = 07:00 UTC в первый день окна), вопросы.

Тур 1 — четыре календарных дня по МСК, тур 2 — три дня, тур 3 — три дня с **дня +6**
от ``GAME_START_DATE_MSK`` (при старте 14.05 → начало R3 20.05 10:00 МСК).

Запуск из корня репозитория::

    PYTHONPATH=. python -m scripts.seed_content

Требует настроенного `.env` и применённых миграций Alembic.
"""

from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.time import add_days, msk_at, msk_day_end, to_utc
from app.db.base import dispose_engine, get_session
from app.db.models import Round, RoundCode, RoundQuestion, RoundStatus

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_CONTENT_DIR = _PROJECT_ROOT / "content"


def _load_yaml(name: str) -> dict[str, Any]:
    path = _CONTENT_DIR / name
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _msk_range_to_utc_naive(start_day: date, end_day: date) -> tuple:
    """Первый день тура (старт 10:00 МСК) -- последний день до 23:59:59 МСК; naive UTC."""
    start_utc = to_utc(msk_at(start_day, 10, 0)).replace(tzinfo=None)
    end_utc = to_utc(msk_day_end(end_day)).replace(tzinfo=None)
    return start_utc, end_utc


def _round_utc_bounds(code: RoundCode, first_day: date, last_day: date) -> tuple:
    """Границы тура в naive UTC для БД.

    R2 в последний календарный день заканчивается в **09:45 МСК** (до старта R3 в 10:00).
    """
    start_utc = to_utc(msk_at(first_day, 10, 0)).replace(tzinfo=None)
    if code == RoundCode.R2:
        end_utc = to_utc(msk_at(last_day, 9, 45)).replace(tzinfo=None)
    else:
        end_utc = to_utc(msk_day_end(last_day)).replace(tzinfo=None)
    return start_utc, end_utc


def _round_windows(game_start_msk: date) -> dict[RoundCode, tuple[str, date, date]]:
    """Имя тура + первый и последний календарный день тура (МСК).

    Тур 1: дни +0…+3. Тур 2: +4…+6 (конец в 09:45 МСК последнего дня). Тур 3: +6…+8
    (старт 10:00 МСК = 07:00 UTC). Между 09:45 и 10:00 МСК в день +6 туров нет.
    """
    return {
        RoundCode.R1: (
            "Кто хочет стать миллионером",
            game_start_msk,
            add_days(game_start_msk, 3),
        ),
        RoundCode.R2: (
            "Своя игра",
            add_days(game_start_msk, 4),
            add_days(game_start_msk, 6),
        ),
        RoundCode.R3: (
            "Где логика",
            add_days(game_start_msk, 6),
            add_days(game_start_msk, 8),
        ),
    }


async def _upsert_round(
    session,
    code: RoundCode,
    name: str,
    starts_at,
    ends_at,
    status: RoundStatus = RoundStatus.SCHEDULED,
) -> Round:
    result = await session.execute(select(Round).where(Round.code == code))
    row = result.scalar_one_or_none()
    if row is None:
        row = Round(
            code=code,
            name=name,
            starts_at=starts_at,
            ends_at=ends_at,
            status=status,
        )
        session.add(row)
        await session.flush()
        return row

    row.name = name
    row.starts_at = starts_at
    row.ends_at = ends_at
    row.status = status
    await session.flush()
    return row


async def _replace_round_questions(session, round_id: int, items: list[dict[str, Any]]) -> None:
    await session.execute(delete(RoundQuestion).where(RoundQuestion.round_id == round_id))
    for item in items:
        session.add(
            RoundQuestion(
                round_id=round_id,
                code=item["code"],
                topic_code=item.get("topic_code"),
                order_index=item["order_index"],
                points=item["points"],
                payload=item["payload"],
            )
        )


async def _seed_rounds_and_questions(session) -> None:
    settings = get_settings()
    game_start = settings.game_start_date_msk
    windows = _round_windows(game_start)

    await _load_round_file(session, RoundCode.R1, "round1.yaml", windows[RoundCode.R1])
    await _load_round_file(session, RoundCode.R2, "round2.yaml", windows[RoundCode.R2])
    await _load_round_file(session, RoundCode.R3, "round3.yaml", windows[RoundCode.R3])


async def _load_round_file(session, code: RoundCode, filename: str, window_meta) -> Round:
    name, first_day, last_day = window_meta
    starts_at, ends_at = _round_utc_bounds(code, first_day, last_day)
    rnd = await _upsert_round(session, code, name, starts_at, ends_at)

    data = _load_yaml(filename)
    if data["round_code"] != code.value:
        raise ValueError(f"{filename}: round_code mismatch {data['round_code']!r} vs {code.value}")

    items: list[dict[str, Any]] = []
    if "questions" in data:
        for q in data["questions"]:
            topic = q.get("topic_code")
            items.append(
                {
                    "code": q["code"],
                    "topic_code": topic,
                    "order_index": q["order_index"],
                    "points": q["points"],
                    "payload": q["payload"],
                }
            )
    elif "topics" in data:
        for topic in data["topics"]:
            t_code = topic["topic_code"]
            for q in topic["questions"]:
                items.append(
                    {
                        "code": q["code"],
                        "topic_code": t_code,
                        "order_index": q["order_index"],
                        "points": q["points"],
                        "payload": q["payload"],
                    }
                )
    else:
        raise ValueError(f"{filename}: expected 'questions' or 'topics'")

    items.sort(key=lambda x: x["order_index"])
    await _replace_round_questions(session, rnd.id, items)
    return rnd


async def seed_all() -> None:
    async with get_session() as session:
        await _seed_rounds_and_questions(session)


async def _async_main() -> None:
    try:
        await seed_all()
    finally:
        await dispose_engine()


def main() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
