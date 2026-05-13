"""Отправка запланированных рассылок с обновлением статусов в БД."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.time import now_utc
from app.db.base import get_session
from app.db.models import (
    Broadcast,
    BroadcastRecipient,
    BroadcastStatus,
    BroadcastTemplate,
    RecipientStatus,
    User,
)
from app.messaging.broadcast_adapter import BroadcastAdapter
from app.messaging.errors import MessengerBadRequestError, MessengerForbiddenError

log = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SEND_DELAY_SEC = 0.04


async def process_due_broadcasts(
    messenger: BroadcastAdapter, session: AsyncSession | None = None
) -> None:
    """Обрабатывает одну подходящую рассылку ``PLANNED`` с ``scheduled_at`` в прошлом.

    Если передан ``session`` (например, в тестах), коммит остаётся на вызывающей стороне.
    """
    if session is None:
        async with get_session() as s:
            await _process_due_broadcasts_with_session(messenger, s)
    else:
        await _process_due_broadcasts_with_session(messenger, session)


async def _process_due_broadcasts_with_session(
    messenger: BroadcastAdapter, session: AsyncSession
) -> None:
    now_naive = now_utc().replace(tzinfo=None)
    bc_id = await session.scalar(
        select(Broadcast.id)
        .where(
            Broadcast.status == BroadcastStatus.PLANNED,
            Broadcast.scheduled_at <= now_naive,
        )
        .order_by(Broadcast.scheduled_at.asc(), Broadcast.id.asc())
        .limit(1)
    )
    if bc_id is None:
        return

    bc = await session.get(Broadcast, bc_id)
    if bc is None or bc.status != BroadcastStatus.PLANNED:
        return

    tpl = await session.scalar(
        select(BroadcastTemplate).where(BroadcastTemplate.code == bc.template_code)
    )
    if tpl is None:
        bc.status = BroadcastStatus.FAILED
        log.error("Broadcast %s: template %s missing", bc.id, bc.template_code)
        return

    bc.status = BroadcastStatus.RUNNING
    bc.started_at = now_naive
    await session.flush()

    text = tpl.text.strip()
    local_img: Path | None = None
    if tpl.image_path:
        p = _PROJECT_ROOT / str(tpl.image_path).lstrip("/")
        if p.is_file():
            local_img = p

    rec_result = await session.execute(
        select(BroadcastRecipient)
        .where(
            BroadcastRecipient.broadcast_id == bc.id,
            BroadcastRecipient.status == RecipientStatus.QUEUED,
        )
        .order_by(BroadcastRecipient.id.asc())
    )
    recipients = list(rec_result.scalars().all())

    sent_c = 0
    fail_c = 0

    for rec in recipients:
        user = await session.get(User, rec.user_id)
        if user is None:
            rec.status = RecipientStatus.SKIPPED
            rec.error = "user_missing"
            fail_c += 1
            await session.flush()
            await asyncio.sleep(_SEND_DELAY_SEC)
            continue
        settings = get_settings()
        max_chat = user.max_chat_id if settings.messenger_platform == "max" else None
        tg_id = int(user.telegram_user_id)
        try:
            if local_img is not None:
                await messenger.send_photo_user(
                    tg_id, local_img, text, chat_id=max_chat
                )
            else:
                await messenger.send_text_user(tg_id, text, chat_id=max_chat)
            rec.status = RecipientStatus.SENT
            rec.sent_at = now_utc().replace(tzinfo=None)
            sent_c += 1
        except (MessengerForbiddenError, MessengerBadRequestError) as e:
            rec.status = RecipientStatus.FAILED
            tag = "forbidden" if isinstance(e, MessengerForbiddenError) else "bad_request"
            rec.error = f"{tag}:{e}"
            fail_c += 1
        except Exception as e:
            rec.status = RecipientStatus.FAILED
            rec.error = str(e)[:500]
            fail_c += 1
            log.exception("broadcast %s user %s", bc.id, rec.user_id)

        await session.flush()
        await asyncio.sleep(_SEND_DELAY_SEC)

    bc.sent = sent_c
    bc.failed = fail_c
    bc.status = BroadcastStatus.DONE
    bc.finished_at = now_utc().replace(tzinfo=None)
    log.info(
        "Broadcast %s done: template=%s sent=%s failed=%s",
        bc.id,
        bc.template_code,
        sent_c,
        fail_c,
    )
