"""Модели прогресса участника по турам и темам Тура 2."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntPkMixin, TimestampMixin


class RoundProgressStatus(str, enum.Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    FINISHED = "FINISHED"


class TopicStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class UserRoundProgress(IntPkMixin, TimestampMixin, Base):
    """Прогресс пользователя по конкретному туру (одна строка на пару user × round)."""

    __tablename__ = "user_round_progress"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    round_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("rounds.id", ondelete="CASCADE"), nullable=False
    )

    status: Mapped[RoundProgressStatus] = mapped_column(
        Enum(RoundProgressStatus, native_enum=False, length=16),
        nullable=False,
        default=RoundProgressStatus.NOT_STARTED,
        server_default=RoundProgressStatus.NOT_STARTED.value,
    )
    total_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    last_answer_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "round_id", name="uq_user_round_progress_user_round"),
        Index("ix_user_round_progress_round_status", "round_id", "status"),
        Index("ix_user_round_progress_round_score", "round_id", "total_score"),
    )


class UserTopicProgress(IntPkMixin, TimestampMixin, Base):
    """Прогресс пользователя по теме внутри тура (актуально для Тура 2)."""

    __tablename__ = "user_topic_progress"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    round_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("rounds.id", ondelete="CASCADE"), nullable=False
    )
    topic_code: Mapped[str] = mapped_column(String(32), nullable=False)

    status: Mapped[TopicStatus] = mapped_column(
        Enum(TopicStatus, native_enum=False, length=8),
        nullable=False,
        default=TopicStatus.OPEN,
        server_default=TopicStatus.OPEN.value,
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    __table_args__ = (
        UniqueConstraint(
            "user_id", "round_id", "topic_code", name="uq_user_topic_progress_user_round_topic"
        ),
        Index("ix_user_topic_progress_round_topic", "round_id", "topic_code"),
    )
