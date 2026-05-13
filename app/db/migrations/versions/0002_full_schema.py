"""full schema: questions, progress, answers, winners, broadcasts, audit

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-03

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _ts_columns():
    return [
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    ]


_TABLE_KW = dict(
    mysql_charset="utf8mb4",
    mysql_collate="utf8mb4_unicode_ci",
    mysql_engine="InnoDB",
)


def upgrade() -> None:
    # ---------- round_questions ----------
    op.create_table(
        "round_questions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("round_id", sa.BigInteger(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("topic_code", sa.String(length=32), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        *_ts_columns(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_round_questions")),
        sa.ForeignKeyConstraint(
            ["round_id"], ["rounds.id"], name="fk_round_questions_round_id_rounds", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("round_id", "code", name="uq_round_questions_round_code"),
        **_TABLE_KW,
    )
    op.create_index(
        "ix_round_questions_round_order", "round_questions", ["round_id", "order_index"], unique=False
    )
    op.create_index(
        "ix_round_questions_round_topic", "round_questions", ["round_id", "topic_code"], unique=False
    )

    # ---------- user_round_progress ----------
    op.create_table(
        "user_round_progress",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("round_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default="NOT_STARTED", nullable=False
        ),
        sa.Column("total_score", sa.Integer(), server_default="0", nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("last_answer_at", sa.DateTime(), nullable=True),
        *_ts_columns(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_round_progress")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_round_progress_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["round_id"],
            ["rounds.id"],
            name="fk_user_round_progress_round_id_rounds",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("user_id", "round_id", name="uq_user_round_progress_user_round"),
        **_TABLE_KW,
    )
    op.create_index(
        "ix_user_round_progress_round_status",
        "user_round_progress",
        ["round_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_user_round_progress_round_score",
        "user_round_progress",
        ["round_id", "total_score"],
        unique=False,
    )

    # ---------- user_topic_progress ----------
    op.create_table(
        "user_topic_progress",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("round_id", sa.BigInteger(), nullable=False),
        sa.Column("topic_code", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=8), server_default="OPEN", nullable=False),
        sa.Column("score", sa.Integer(), server_default="0", nullable=False),
        *_ts_columns(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_topic_progress")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_topic_progress_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["round_id"],
            ["rounds.id"],
            name="fk_user_topic_progress_round_id_rounds",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "user_id", "round_id", "topic_code",
            name="uq_user_topic_progress_user_round_topic",
        ),
        **_TABLE_KW,
    )
    op.create_index(
        "ix_user_topic_progress_round_topic",
        "user_topic_progress",
        ["round_id", "topic_code"],
        unique=False,
    )

    # ---------- user_answers ----------
    op.create_table(
        "user_answers",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("round_id", sa.BigInteger(), nullable=False),
        sa.Column("question_id", sa.BigInteger(), nullable=False),
        sa.Column("selected_option", sa.String(length=8), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("points_awarded", sa.Integer(), server_default="0", nullable=False),
        sa.Column("answered_at", sa.DateTime(), nullable=False),
        *_ts_columns(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_answers")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_answers_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["round_id"], ["rounds.id"], name="fk_user_answers_round_id_rounds", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["round_questions.id"],
            name="fk_user_answers_question_id_round_questions",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("user_id", "question_id", name="uq_user_answers_user_question"),
        **_TABLE_KW,
    )
    op.create_index("ix_user_answers_round", "user_answers", ["round_id"], unique=False)
    op.create_index("ix_user_answers_answered_at", "user_answers", ["answered_at"], unique=False)

    # ---------- winner_selections ----------
    op.create_table(
        "winner_selections",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("round_id", sa.BigInteger(), nullable=False),
        sa.Column("candidates_count", sa.Integer(), nullable=False),
        sa.Column("winners_count", sa.Integer(), nullable=False),
        sa.Column("n_step", sa.Integer(), nullable=False),
        sa.Column(
            "ordering_strategy",
            sa.String(length=32),
            server_default="user_id_asc",
            nullable=False,
        ),
        sa.Column("score_threshold", sa.Integer(), nullable=False),
        sa.Column("executed_at", sa.DateTime(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        *_ts_columns(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_winner_selections")),
        sa.ForeignKeyConstraint(
            ["round_id"],
            ["rounds.id"],
            name="fk_winner_selections_round_id_rounds",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("round_id", name="uq_winner_selections_round"),
        **_TABLE_KW,
    )

    # ---------- winners ----------
    op.create_table(
        "winners",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("winner_selection_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        *_ts_columns(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_winners")),
        sa.ForeignKeyConstraint(
            ["winner_selection_id"],
            ["winner_selections.id"],
            name="fk_winners_winner_selection_id_winner_selections",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_winners_user_id_users", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("winner_selection_id", "user_id", name="uq_winners_selection_user"),
        sa.UniqueConstraint(
            "winner_selection_id", "position", name="uq_winners_selection_position"
        ),
        **_TABLE_KW,
    )

    # ---------- broadcast_templates ----------
    op.create_table(
        "broadcast_templates",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("image_path", sa.String(length=255), nullable=True),
        *_ts_columns(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_broadcast_templates")),
        sa.UniqueConstraint("code", name="uq_broadcast_templates_code"),
        **_TABLE_KW,
    )

    # ---------- broadcasts ----------
    op.create_table(
        "broadcasts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("template_code", sa.String(length=64), nullable=False),
        sa.Column("segment_code", sa.String(length=64), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column(
            "status", sa.String(length=16), server_default="PLANNED", nullable=False
        ),
        sa.Column("total", sa.Integer(), server_default="0", nullable=False),
        sa.Column("sent", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed", sa.Integer(), server_default="0", nullable=False),
        *_ts_columns(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_broadcasts")),
        **_TABLE_KW,
    )
    op.create_index("ix_broadcasts_status", "broadcasts", ["status"], unique=False)
    op.create_index(
        "ix_broadcasts_scheduled_at", "broadcasts", ["scheduled_at"], unique=False
    )

    # ---------- broadcast_recipients ----------
    op.create_table(
        "broadcast_recipients",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("broadcast_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default="QUEUED", nullable=False
        ),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("error", sa.String(length=512), nullable=True),
        *_ts_columns(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_broadcast_recipients")),
        sa.ForeignKeyConstraint(
            ["broadcast_id"],
            ["broadcasts.id"],
            name="fk_broadcast_recipients_broadcast_id_broadcasts",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_broadcast_recipients_user_id_users",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "broadcast_id", "user_id", name="uq_broadcast_recipients_broadcast_user"
        ),
        **_TABLE_KW,
    )
    op.create_index(
        "ix_broadcast_recipients_broadcast_status",
        "broadcast_recipients",
        ["broadcast_id", "status"],
        unique=False,
    )

    # ---------- email_validation_log ----------
    op.create_table(
        "email_validation_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("is_valid", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=False),
        *_ts_columns(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_validation_log")),
        **_TABLE_KW,
    )
    op.create_index(
        "ix_email_validation_log_telegram_user_id",
        "email_validation_log",
        ["telegram_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_email_validation_log_tg_created",
        "email_validation_log",
        ["telegram_user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_email_validation_log_tg_created", table_name="email_validation_log")
    op.drop_index("ix_email_validation_log_telegram_user_id", table_name="email_validation_log")
    op.drop_table("email_validation_log")

    op.drop_index(
        "ix_broadcast_recipients_broadcast_status", table_name="broadcast_recipients"
    )
    op.drop_table("broadcast_recipients")

    op.drop_index("ix_broadcasts_scheduled_at", table_name="broadcasts")
    op.drop_index("ix_broadcasts_status", table_name="broadcasts")
    op.drop_table("broadcasts")

    op.drop_table("broadcast_templates")

    op.drop_table("winners")
    op.drop_table("winner_selections")

    op.drop_index("ix_user_answers_answered_at", table_name="user_answers")
    op.drop_index("ix_user_answers_round", table_name="user_answers")
    op.drop_table("user_answers")

    op.drop_index("ix_user_topic_progress_round_topic", table_name="user_topic_progress")
    op.drop_table("user_topic_progress")

    op.drop_index("ix_user_round_progress_round_score", table_name="user_round_progress")
    op.drop_index("ix_user_round_progress_round_status", table_name="user_round_progress")
    op.drop_table("user_round_progress")

    op.drop_index("ix_round_questions_round_topic", table_name="round_questions")
    op.drop_index("ix_round_questions_round_order", table_name="round_questions")
    op.drop_table("round_questions")
