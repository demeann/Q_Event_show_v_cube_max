"""Сегменты получателей для рассылок (как в шаблонах ``broadcasts.yaml``)."""

from __future__ import annotations

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Round, RoundCode, User, UserRoundProgress
from app.db.models.progress import RoundProgressStatus


def eligible_user_base_stmt():
    return (
        User.is_blocked.is_(False),
        or_(
            User.email_verified_at.isnot(None),
            User.is_admin.is_(True),
        ),
    )


async def fetch_segment_user_ids(
    session: AsyncSession,
    *,
    segment_code: str,
    round_id: int | None,
) -> list[int]:
    """Возвращает ``users.id`` для сегмента. ``round_id`` обязателен для ``RX_*``."""
    base = select(User.id).where(*eligible_user_base_stmt())

    if segment_code == "ALL_VERIFIED":
        r = await session.execute(base.order_by(User.id.asc()))
        return [int(x) for x in r.scalars().all()]

    if segment_code == "ALL_ROUNDS_FINISHED":
        q = await session.execute(
            select(Round.id, Round.code).where(
                Round.code.in_((RoundCode.R1, RoundCode.R2, RoundCode.R3))
            )
        )
        by_code = {row[1]: row[0] for row in q.all()}
        if set(by_code.keys()) != {RoundCode.R1, RoundCode.R2, RoundCode.R3}:
            return []
        fin_r1 = exists(
            select(UserRoundProgress.id).where(
                UserRoundProgress.user_id == User.id,
                UserRoundProgress.round_id == by_code[RoundCode.R1],
                UserRoundProgress.status == RoundProgressStatus.FINISHED,
            )
        )
        fin_r2 = exists(
            select(UserRoundProgress.id).where(
                UserRoundProgress.user_id == User.id,
                UserRoundProgress.round_id == by_code[RoundCode.R2],
                UserRoundProgress.status == RoundProgressStatus.FINISHED,
            )
        )
        fin_r3 = exists(
            select(UserRoundProgress.id).where(
                UserRoundProgress.user_id == User.id,
                UserRoundProgress.round_id == by_code[RoundCode.R3],
                UserRoundProgress.status == RoundProgressStatus.FINISHED,
            )
        )
        r = await session.execute(
            base.where(and_(fin_r1, fin_r2, fin_r3)).order_by(User.id.asc())
        )
        return [int(x) for x in r.scalars().all()]

    if segment_code.endswith("_NOT_STARTED"):
        if round_id is None:
            return []
        not_started = or_(
            ~exists(
                select(UserRoundProgress.id).where(
                    UserRoundProgress.user_id == User.id,
                    UserRoundProgress.round_id == round_id,
                )
            ),
            exists(
                select(UserRoundProgress.id).where(
                    UserRoundProgress.user_id == User.id,
                    UserRoundProgress.round_id == round_id,
                    UserRoundProgress.status == RoundProgressStatus.NOT_STARTED,
                )
            ),
        )
        r = await session.execute(base.where(not_started).order_by(User.id.asc()))
        return [int(x) for x in r.scalars().all()]

    if segment_code.endswith("_NOT_FINISHED"):
        if round_id is None:
            return []
        not_fin = exists(
            select(UserRoundProgress.id).where(
                UserRoundProgress.user_id == User.id,
                UserRoundProgress.round_id == round_id,
                UserRoundProgress.status != RoundProgressStatus.FINISHED,
            )
        )
        r = await session.execute(base.where(not_fin).order_by(User.id.asc()))
        return [int(x) for x in r.scalars().all()]

    return []


def parse_round_code_from_segment(segment_code: str) -> RoundCode | None:
    if segment_code == "ALL_VERIFIED" or segment_code == "ALL_ROUNDS_FINISHED":
        return None
    prefix = segment_code.split("_", 1)[0]
    try:
        return RoundCode(prefix)
    except ValueError:
        return None
