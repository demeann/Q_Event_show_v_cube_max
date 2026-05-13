"""Отбор победителей: фиксированные места в рейтинге (балл, затем время последнего ответа)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import now_utc
from app.db.models import Round, RoundCode, RoundStatus, Winner, WinnerSelection
from app.services.winner_ranking import (
    WINNER_LIST_RANKS_BY_ROUND,
    fetch_ranked_participants,
    pick_winners_by_fixed_list_ranks,
    selection_note_ru,
)

log = logging.getLogger(__name__)


async def ensure_winner_selection(
    session: AsyncSession,
    round_row: Round,
    *,
    only_after_end: bool = True,
    now_naive: datetime | None = None,
) -> WinnerSelection | None:
    """Идемпотентно создаёт `WinnerSelection` + строки `Winner` для тура."""
    if only_after_end:
        effective = (
            now_naive if now_naive is not None else now_utc().replace(tzinfo=None)
        )
        if round_row.ends_at >= effective:
            return None

    existing_id = await session.scalar(
        select(WinnerSelection.id).where(WinnerSelection.round_id == round_row.id)
    )
    if existing_id is not None:
        return await session.get(WinnerSelection, existing_id)

    ranked = await fetch_ranked_participants(session, round_row)
    if not ranked:
        log.warning("No eligible scores for round_id=%s; skip winner selection", round_row.id)
        return None

    ordered_ids = [p.user_id for p in ranked]
    ranks = WINNER_LIST_RANKS_BY_ROUND.get(round_row.code)
    if not ranks:
        log.error("No WINNER_LIST_RANKS for round code=%s", round_row.code)
        return None

    winners, filled_ranks, missing_ranks = pick_winners_by_fixed_list_ranks(ordered_ids, ranks)
    note = selection_note_ru(filled_ranks, missing_ranks)

    scores_by_uid = {p.user_id: p.total_score for p in ranked}
    min_score = min((scores_by_uid[uid] for uid in winners), default=0)

    now_val = now_utc().replace(tzinfo=None)
    selection_meta: dict[str, Any] = {
        "algorithm": "fixed_list_ranks_score_then_last_answer_time",
        "winner_list_ranks": list(ranks),
        "ranks_filled": filled_ranks,
        "ranks_not_selected": missing_ranks,
        "export_note_ru": note,
        "ordered_user_ids_head": ordered_ids[:50],
        "ordered_user_ids_tail": ordered_ids[-50:] if len(ordered_ids) > 50 else [],
        "ordered_count": len(ordered_ids),
        "winner_user_ids": winners,
    }
    payload: dict[str, Any] = {
        **selection_meta,
        "W_target": len(ranks),
        "W_actual": len(winners),
    }

    sel = WinnerSelection(
        round_id=round_row.id,
        candidates_count=len(ordered_ids),
        winners_count=len(winners),
        n_step=0,
        ordering_strategy="fixed_list_ranks_v1",
        score_threshold=int(min_score),
        executed_at=now_val,
        payload=payload,
    )
    session.add(sel)
    await session.flush()

    for position, uid in enumerate(winners, start=1):
        session.add(
            Winner(
                winner_selection_id=sel.id,
                user_id=uid,
                position=position,
            )
        )

    await session.flush()
    round_row.status = RoundStatus.FINISHED
    log.info(
        "Winner selection for round %s (%s): eligible=%s W=%s missing_ranks=%s",
        round_row.id,
        round_row.code,
        len(ordered_ids),
        len(winners),
        missing_ranks,
    )
    return sel


AdminWinnerPickStatus = Literal[
    "ok_new",
    "ok_existing",
    "round_not_found",
    "too_early",
    "no_eligible",
]


@dataclass(frozen=True)
class AdminWinnerPickResult:
    status: AdminWinnerPickStatus
    round_row: Round | None = None
    selection: WinnerSelection | None = None


async def admin_pick_winners_for_round(
    session: AsyncSession,
    code: RoundCode,
    *,
    now_naive: datetime | None = None,
) -> AdminWinnerPickResult:
    """Ручной запуск отбора победителей (админка): только если ``ends_at`` уже в прошлом.

    Если отбор уже есть — возвращает ``ok_existing`` без повторного расчёта.
    """
    if now_naive is None:
        now_naive = now_utc().replace(tzinfo=None)

    rnd = await session.scalar(select(Round).where(Round.code == code))
    if rnd is None:
        return AdminWinnerPickResult(status="round_not_found")

    if rnd.ends_at >= now_naive:
        return AdminWinnerPickResult(status="too_early", round_row=rnd)

    existing = await session.scalar(
        select(WinnerSelection).where(WinnerSelection.round_id == rnd.id)
    )
    if existing is not None:
        return AdminWinnerPickResult(
            status="ok_existing", round_row=rnd, selection=existing
        )

    sel = await ensure_winner_selection(
        session, rnd, only_after_end=True, now_naive=now_naive
    )
    if sel is None:
        return AdminWinnerPickResult(status="no_eligible", round_row=rnd)
    return AdminWinnerPickResult(status="ok_new", round_row=rnd, selection=sel)


async def pick_winners_for_due_rounds() -> None:
    """Запуск из планировщика: туры с ``ends_at`` в прошлом без ``winner_selections``."""
    from app.db.base import get_session

    now_naive = now_utc().replace(tzinfo=None)
    subq = (
        select(WinnerSelection.id)
        .where(WinnerSelection.round_id == Round.id)
        .exists()
    )
    stmt = (
        select(Round.id)
        .where(Round.ends_at < now_naive, ~subq)
        .order_by(Round.ends_at.asc())
    )

    async with get_session() as session:
        round_ids = list((await session.scalars(stmt)).all())

    for rid in round_ids:
        try:
            async with get_session() as session:
                rnd = await session.get(Round, rid)
                if rnd is None:
                    continue
                await ensure_winner_selection(session, rnd, only_after_end=True)
        except Exception:
            log.exception("Winner selection failed for round_id=%s", rid)
