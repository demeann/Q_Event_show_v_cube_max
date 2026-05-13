"""Модель вопроса тура.

`payload` — JSON со структурой:

    {
      "text": "Какие две новинки появились в Q CLUB весной 2025?",
      "options": ["Бассейн ...", "Карта лояльности ...", "...", "..."],
      "correct_index": 1,
      "image_path": "assets/round3/q1.jpg",   // только для Тура 3
      "feedback": "Кстати, ..."               // подсказка после ответа
    }
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, BigInteger, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntPkMixin, TimestampMixin


class RoundQuestion(IntPkMixin, TimestampMixin, Base):
    __tablename__ = "round_questions"

    round_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("rounds.id", ondelete="CASCADE"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    topic_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    round = relationship("Round", lazy="joined")

    __table_args__ = (
        UniqueConstraint("round_id", "code", name="uq_round_questions_round_code"),
        Index("ix_round_questions_round_order", "round_id", "order_index"),
        Index("ix_round_questions_round_topic", "round_id", "topic_code"),
    )
