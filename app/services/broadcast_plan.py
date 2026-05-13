"""Планирование рассылок: слоты времени относительно окон туров в БД."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import UTC, add_days, msk_at, to_msk, to_utc
from app.db.models import (
    Broadcast,
    BroadcastRecipient,
    BroadcastStatus,
    RecipientStatus,
    Round,
    RoundCode,
)
from app.services.broadcast_segments import fetch_segment_user_ids, parse_round_code_from_segment

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class BroadcastSlot:
    template_code: str
    segment_code: str
    scheduled_at_utc_naive: datetime


def _msk_first_day_utc_naive(round_row: Round) -> datetime.date:
    return to_msk(round_row.starts_at.replace(tzinfo=UTC)).date()


def slots_for_round(round_row: Round) -> list[BroadcastSlot]:
    """Времена в UTC naive (как в колонках БД)."""
    rc = round_row.code.value
    d0 = _msk_first_day_utc_naive(round_row)
    slots: list[BroadcastSlot] = []

    slots.append(
        BroadcastSlot(f"ANNOUNCE_{rc}", "ALL_VERIFIED", round_row.starts_at)
    )

    ns = to_utc(msk_at(add_days(d0, 1), 15, 0)).replace(tzinfo=None)
    slots.append(
        BroadcastSlot(
            f"REMINDER_{rc}_NOT_STARTED",
            f"{rc}_NOT_STARTED",
            ns,
        )
    )

    nf = to_utc(msk_at(add_days(d0, 2), 11, 0)).replace(tzinfo=None)
    slots.append(
        BroadcastSlot(
            f"REMINDER_{rc}_NOT_FINISHED",
            f"{rc}_NOT_FINISHED",
            nf,
        )
    )

    # Текст RESULT_R3 благодарит за прохождение всех туров — получают только
    # пользователи с FINISHED по R1, R2 и R3. R1/R2 по-прежнему всем верифицированным.
    result_segment = (
        "ALL_ROUNDS_FINISHED"
        if round_row.code == RoundCode.R3
        else "ALL_VERIFIED"
    )
    slots.append(
        BroadcastSlot(f"RESULT_{rc}", result_segment, round_row.ends_at)
    )
    return slots


async def collect_all_slots(session: AsyncSession) -> list[BroadcastSlot]:
    r = await session.execute(select(Round).order_by(Round.starts_at.asc()))
    rows = list(r.scalars().all())
    out: list[BroadcastSlot] = []
    for row in rows:
        out.extend(slots_for_round(row))
    return out


async def _already_planned(
    session: AsyncSession,
    template_code: str,
    segment_code: str,
    scheduled_at: datetime,
) -> bool:
    q = await session.scalar(
        select(Broadcast.id).where(
            Broadcast.template_code == template_code,
            Broadcast.segment_code == segment_code,
            Broadcast.scheduled_at == scheduled_at,
        )
    )
    return q is not None


async def ensure_planned_broadcasts(session: AsyncSession, *, now_naive: datetime) -> int:
    """Создаёт отсутствующие ``Broadcast`` + ``BroadcastRecipient`` в окне backfill/horizon."""
    created = 0
    horizon_end = now_naive + timedelta(days=45)
    backfill_start = now_naive - timedelta(hours=36)

    slots = await collect_all_slots(session)
    round_by_code = {
        row.code: row
        for row in (await session.execute(select(Round))).scalars().all()
    }

    for slot in slots:
        if slot.scheduled_at_utc_naive < backfill_start or slot.scheduled_at_utc_naive > horizon_end:
            continue
        if await _already_planned(
            session,
            slot.template_code,
            slot.segment_code,
            slot.scheduled_at_utc_naive,
        ):
            continue

        rc = parse_round_code_from_segment(slot.segment_code)
        rid = round_by_code[rc].id if rc is not None else None
        user_ids = await fetch_segment_user_ids(
            session,
            segment_code=slot.segment_code,
            round_id=rid,
        )

        bc = Broadcast(
            template_code=slot.template_code,
            segment_code=slot.segment_code,
            scheduled_at=slot.scheduled_at_utc_naive,
            status=BroadcastStatus.PLANNED,
            total=len(user_ids),
            sent=0,
            failed=0,
        )
        session.add(bc)
        await session.flush()

        for uid in user_ids:
            session.add(
                BroadcastRecipient(
                    broadcast_id=bc.id,
                    user_id=uid,
                    status=RecipientStatus.QUEUED,
                )
            )
        await session.flush()
        created += 1
        log.info(
            "Planned broadcast %s seg=%s at=%s recipients=%s",
            slot.template_code,
            slot.segment_code,
            slot.scheduled_at_utc_naive,
            len(user_ids),
        )

    return created


async def plan_broadcasts_job() -> None:
    from app.core.time import now_utc
    from app.db.base import get_session

    async with get_session() as session:
        await ensure_planned_broadcasts(session, now_naive=now_utc().replace(tzinfo=None))
