"""Модель пользователя бота."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntPkMixin, TimestampMixin


class User(IntPkMixin, TimestampMixin, Base):
    """Участник игры.

    Email подтверждается простой проверкой формата + домена из whitelist
    (см. `ALLOWED_EMAIL_DOMAINS`). OTP в MVP не используется.
    """

    __tablename__ = "users"

    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    tg_username: Mapped[str | None] = mapped_column(String(64), nullable=True)

    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    email_domain: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True, index=True
    )

    invite_gate_passed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    is_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<User id={self.id} tg={self.telegram_user_id} "
            f"verified={'yes' if self.email_verified_at else 'no'}>"
        )
