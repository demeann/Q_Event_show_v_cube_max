"""Флаги отправки стартовых пушей туров (ровно 3 на пользователя).

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-15

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    t = sa.DateTime(timezone=False)
    op.add_column("users", sa.Column("tour_push_r1_sent_at", t, nullable=True))
    op.add_column("users", sa.Column("tour_push_r2_sent_at", t, nullable=True))
    op.add_column("users", sa.Column("tour_push_r3_sent_at", t, nullable=True))


def downgrade() -> None:
    op.drop_column("users", "tour_push_r3_sent_at")
    op.drop_column("users", "tour_push_r2_sent_at")
    op.drop_column("users", "tour_push_r1_sent_at")
