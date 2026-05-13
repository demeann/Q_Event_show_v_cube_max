"""Модель ответа пользователя на вопрос.

UNIQUE(user_id, question_id) гарантирует правило «одна попытка на вопрос».
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntPkMixin, TimestampMixin


class UserAnswer(IntPkMixin, TimestampMixin, Base):
    __tablename__ = "user_answers"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    round_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("rounds.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("round_questions.id", ondelete="CASCADE"), nullable=False
    )

    selected_option: Mapped[str] = mapped_column(String(8), nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    points_awarded: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "question_id", name="uq_user_answers_user_question"),
        Index("ix_user_answers_round", "round_id"),
        Index("ix_user_answers_answered_at", "answered_at"),
    )
