"""Модель тура (раунда) игры."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntPkMixin, TimestampMixin


class RoundCode(str, enum.Enum):
    """Код тура. Привязан к фиксированному порядку проведения."""

    R1 = "R1"  # «Кто хочет стать миллионером»
    R2 = "R2"  # «Своя игра»
    R3 = "R3"  # «Где логика»


class RoundStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    ACTIVE = "ACTIVE"
    FINISHED = "FINISHED"


class Round(IntPkMixin, TimestampMixin, Base):
    """Тур игры.

    Окно `[starts_at, ends_at]` хранится в UTC (как и все datetime),
    а в коде приложения конвертируется в МСК через `app.core.time`.
    """

    __tablename__ = "rounds"

    code: Mapped[RoundCode] = mapped_column(
        Enum(RoundCode, native_enum=False, length=4),
        unique=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)

    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)

    status: Mapped[RoundStatus] = mapped_column(
        Enum(RoundStatus, native_enum=False, length=16),
        nullable=False,
        default=RoundStatus.SCHEDULED,
        server_default=RoundStatus.SCHEDULED.value,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Round {self.code.value} {self.status.value} {self.starts_at}..{self.ends_at}>"
