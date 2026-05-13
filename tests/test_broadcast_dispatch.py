"""Отправка рассылок: мок Bot."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.exceptions import TelegramForbiddenError

from app.db.models import (
    Broadcast,
    BroadcastRecipient,
    BroadcastStatus,
    BroadcastTemplate,
    BroadcastTemplateType,
    RecipientStatus,
    User,
)
from app.messaging.broadcast_adapter import TelegramBroadcastAdapter
from app.services.broadcast_dispatch import process_due_broadcasts


@pytest.fixture(autouse=True)
def _no_broadcast_sleep(monkeypatch):
    monkeypatch.setattr(
        "app.services.broadcast_dispatch.asyncio.sleep",
        AsyncMock(),
    )


@pytest.mark.asyncio
async def test_dispatch_sends_text_messages(db_session):
    db_session.add(
        BroadcastTemplate(
            id=1,
            code="ANNOUNCE_R1",
            type=BroadcastTemplateType.ANNOUNCE,
            text="  Привет, тур!  ",
            image_path=None,
        )
    )
    db_session.add(
        User(
            id=1,
            telegram_user_id=555001,
            email="x@pmru.com",
            email_domain="pmru.com",
            email_verified_at=datetime(2026, 1, 1, 0, 0, 0),
            is_blocked=False,
            is_admin=False,
        )
    )
    db_session.add(
        Broadcast(
            id=1,
            template_code="ANNOUNCE_R1",
            segment_code="ALL_VERIFIED",
            scheduled_at=datetime(2000, 1, 1, 0, 0, 0),
            status=BroadcastStatus.PLANNED,
            total=1,
            sent=0,
            failed=0,
        )
    )
    db_session.add(
        BroadcastRecipient(
            id=1,
            broadcast_id=1,
            user_id=1,
            status=RecipientStatus.QUEUED,
        )
    )
    await db_session.flush()

    bot = AsyncMock()
    await process_due_broadcasts(TelegramBroadcastAdapter(bot), db_session)

    bot.send_message.assert_awaited_once()
    assert bot.send_message.await_args.args[0] == 555001
    assert bot.send_message.await_args.args[1] == "Привет, тур!"
    bc = await db_session.get(Broadcast, 1)
    assert bc.status == BroadcastStatus.DONE
    assert bc.sent == 1
    assert bc.failed == 0


@pytest.mark.asyncio
async def test_dispatch_template_missing_marks_failed(db_session):
    db_session.add(
        User(
            id=1,
            telegram_user_id=1,
            email="x@pmru.com",
            email_domain="pmru.com",
            email_verified_at=datetime(2026, 1, 1, 0, 0, 0),
            is_blocked=False,
            is_admin=False,
        )
    )
    db_session.add(
        Broadcast(
            id=1,
            template_code="MISSING",
            segment_code="ALL_VERIFIED",
            scheduled_at=datetime(2000, 1, 1, 0, 0, 0),
            status=BroadcastStatus.PLANNED,
            total=1,
            sent=0,
            failed=0,
        )
    )
    db_session.add(
        BroadcastRecipient(
            id=1,
            broadcast_id=1,
            user_id=1,
            status=RecipientStatus.QUEUED,
        )
    )
    await db_session.flush()

    bot = AsyncMock()
    await process_due_broadcasts(TelegramBroadcastAdapter(bot), db_session)

    bot.send_message.assert_not_called()
    bc = await db_session.get(Broadcast, 1)
    assert bc.status == BroadcastStatus.FAILED


@pytest.mark.asyncio
async def test_dispatch_forbidden_counts_failed(db_session):
    db_session.add(
        BroadcastTemplate(
            id=1,
            code="X",
            type=BroadcastTemplateType.CUSTOM,
            text="hey",
            image_path=None,
        )
    )
    db_session.add(
        User(
            id=1,
            telegram_user_id=777,
            email="x@pmru.com",
            email_domain="pmru.com",
            email_verified_at=datetime(2026, 1, 1, 0, 0, 0),
            is_blocked=False,
            is_admin=False,
        )
    )
    db_session.add(
        Broadcast(
            id=1,
            template_code="X",
            segment_code="ALL_VERIFIED",
            scheduled_at=datetime(2000, 1, 1, 0, 0, 0),
            status=BroadcastStatus.PLANNED,
            total=1,
            sent=0,
            failed=0,
        )
    )
    db_session.add(
        BroadcastRecipient(
            id=1,
            broadcast_id=1,
            user_id=1,
            status=RecipientStatus.QUEUED,
        )
    )
    await db_session.flush()

    bot = AsyncMock()
    bot.send_message.side_effect = TelegramForbiddenError(
        method=MagicMock(), message="forbidden"
    )
    await process_due_broadcasts(TelegramBroadcastAdapter(bot), db_session)

    bc = await db_session.get(Broadcast, 1)
    assert bc.status == BroadcastStatus.DONE
    assert bc.sent == 0
    assert bc.failed == 1
    rec = await db_session.get(BroadcastRecipient, 1)
    assert rec.status == RecipientStatus.FAILED


@pytest.mark.asyncio
async def test_dispatch_empty_recipients_still_done(db_session):
    db_session.add(
        BroadcastTemplate(
            id=1,
            code="X",
            type=BroadcastTemplateType.CUSTOM,
            text="t",
            image_path=None,
        )
    )
    db_session.add(
        Broadcast(
            id=1,
            template_code="X",
            segment_code="ALL_VERIFIED",
            scheduled_at=datetime(2000, 1, 1, 0, 0, 0),
            status=BroadcastStatus.PLANNED,
            total=0,
            sent=0,
            failed=0,
        )
    )
    await db_session.flush()

    bot = AsyncMock()
    await process_due_broadcasts(TelegramBroadcastAdapter(bot), db_session)

    bot.send_message.assert_not_called()
    bc = await db_session.get(Broadcast, 1)
    assert bc.status == BroadcastStatus.DONE
