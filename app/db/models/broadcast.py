"""Модели для механизма массовых рассылок Telegram.

Поток:
1. По расписанию (APScheduler) создаётся `Broadcast` со статусом PLANNED
   и заполняются `BroadcastRecipient` для всех получателей сегмента.
2. Воркер переводит broadcast в RUNNING, отправляет сообщения с rate-limit,
   обновляет статус каждого получателя.
3. По завершении broadcast переводится в DONE, считаются метрики `total/sent/failed`.

`UNIQUE(broadcast_id, user_id)` гарантирует идемпотентность повторного запуска.
"""

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
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntPkMixin, TimestampMixin


class BroadcastTemplateType(str, enum.Enum):
    ANNOUNCE = "ANNOUNCE"
    REMINDER = "REMINDER"
    RESULT = "RESULT"
    CUSTOM = "CUSTOM"


class BroadcastStatus(str, enum.Enum):
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"


class RecipientStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    SENT = "SENT"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class BroadcastTemplate(IntPkMixin, TimestampMixin, Base):
    """Шаблон сообщения. Подгружается из `content/broadcasts.yaml` при сидинге."""

    __tablename__ = "broadcast_templates"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    type: Mapped[BroadcastTemplateType] = mapped_column(
        Enum(BroadcastTemplateType, native_enum=False, length=16),
        nullable=False,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Broadcast(IntPkMixin, TimestampMixin, Base):
    """Конкретный запуск рассылки."""

    __tablename__ = "broadcasts"

    template_code: Mapped[str] = mapped_column(String(64), nullable=False)
    segment_code: Mapped[str] = mapped_column(String(64), nullable=False)

    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    status: Mapped[BroadcastStatus] = mapped_column(
        Enum(BroadcastStatus, native_enum=False, length=16),
        nullable=False,
        default=BroadcastStatus.PLANNED,
        server_default=BroadcastStatus.PLANNED.value,
    )

    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    sent: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    __table_args__ = (
        Index("ix_broadcasts_status", "status"),
        Index("ix_broadcasts_scheduled_at", "scheduled_at"),
    )


class BroadcastRecipient(IntPkMixin, TimestampMixin, Base):
    """Один получатель в одной рассылке."""

    __tablename__ = "broadcast_recipients"

    broadcast_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("broadcasts.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    status: Mapped[RecipientStatus] = mapped_column(
        Enum(RecipientStatus, native_enum=False, length=16),
        nullable=False,
        default=RecipientStatus.QUEUED,
        server_default=RecipientStatus.QUEUED.value,
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    error: Mapped[str | None] = mapped_column(String(512), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "broadcast_id", "user_id", name="uq_broadcast_recipients_broadcast_user"
        ),
        Index("ix_broadcast_recipients_broadcast_status", "broadcast_id", "status"),
    )
