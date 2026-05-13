"""Аудит ключевых действий: лог попыток валидации email."""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntPkMixin, TimestampMixin


class EmailValidationLog(IntPkMixin, TimestampMixin, Base):
    """Лог попыток ввода email с результатом проверки.

    Хранится с точки зрения телеграм-аккаунта (а не User), чтобы фиксировать
    и попытки до создания записи в `users`. PII (сам email) хранится только
    с целью аудита и может быть очищен по retention-политике.
    """

    __tablename__ = "email_validation_log"

    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        Index("ix_email_validation_log_tg_created", "telegram_user_id", "created_at"),
    )
