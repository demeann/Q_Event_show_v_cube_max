"""Модели выбора победителей и итогового списка победителей тура.

`WinnerSelection` хранит параметры запуска алгоритма Иосифа Флавия (T, W, n, порядок)
и полный аудит шагов в `payload`. Уникальность по `round_id` гарантирует, что
для одного тура существует ровно один результат селекции.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntPkMixin, TimestampMixin


class WinnerSelection(IntPkMixin, TimestampMixin, Base):
    __tablename__ = "winner_selections"

    round_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("rounds.id", ondelete="CASCADE"), nullable=False
    )

    candidates_count: Mapped[int] = mapped_column(Integer, nullable=False)  # T
    winners_count: Mapped[int] = mapped_column(Integer, nullable=False)     # W
    n_step: Mapped[int] = mapped_column(Integer, nullable=False)            # n

    ordering_strategy: Mapped[str] = mapped_column(
        String(32), nullable=False, default="user_id_asc", server_default="user_id_asc"
    )
    score_threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)

    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        UniqueConstraint("round_id", name="uq_winner_selections_round"),
    )


class Winner(IntPkMixin, TimestampMixin, Base):
    __tablename__ = "winners"

    winner_selection_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("winner_selections.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "winner_selection_id", "user_id", name="uq_winners_selection_user"
        ),
        UniqueConstraint(
            "winner_selection_id", "position", name="uq_winners_selection_position"
        ),
    )
