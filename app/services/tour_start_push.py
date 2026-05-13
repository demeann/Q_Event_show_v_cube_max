"""Три стартовых пуша: в окне тура (и сразу после верификации email). Telegram и MAX."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import now_utc
from app.db.base import get_session
from app.db.models import Round, RoundCode, User, UserRoundProgress
from app.messaging.broadcast_adapter import BroadcastAdapter
from app.messaging.errors import MessengerBadRequestError, MessengerForbiddenError
from app.services.broadcast_segments import eligible_user_base_stmt

log = logging.getLogger(__name__)

_SEND_GAP_SEC = 0.05

_ALL_ROUNDS = (RoundCode.R1, RoundCode.R2, RoundCode.R3)

# Совпадают с интро в /play (R3 — tg-spoiler для Telegram; MAX рендерит как HTML).
TOUR_PUSH_R1_TEXT = (
    "Мы начинаем! Добро пожаловать в первый тур!⚡\n\n"
    "Тут всё серьёзно: четыре варианта, один верный, ноль подсказок от зала.\n\n"
    "Ну, почти ноль. Поехали?👀"
)
TOUR_PUSH_R2_TEXT = (
    "Привет! Уверены, ты очень ждал этот день, потому что вот он - следующий тур "
    "нашего Конкурса в Кубе! Внимание, начинаем второй тур! 🎉\n\n"
    "Выбери тему, ответь правильно — идёшь дальше. Ошибёшься — тема закрывается, "
    "но баллы не отнимаются. Мы ж не звери, мы Q CLUB. Начинаем? 👀"
)
TOUR_PUSH_R3_TEXT = (
    "Привет! Скучал? А вот и мы! Встречай финальный тур нашего Конкурса в Кубе!\n\n"
    "Смотри на картинки, включай ассоциации и выбирай ответ.\n\n"
    "<i>Подсказка: <tg-spoiler>Q CLUB рядом, но не всё так очевидно. Баллы не отнимаются — "
    "мы добрые до конца.</i></tg-spoiler>"
)

INTRO_R1_IMAGE = "assets/round1/intro.jpg"
INTRO_R2_IMAGE = "assets/round2/intro.jpg"
INTRO_R3_IMAGE = "assets/round3/intro.jpg"

CB_R1_GO = "r1fwd:go"
CB_R2_GO = "r2go:go"
CB_R3_GO = "r3go:go"


def _kb_r1() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Вперёд", callback_data=CB_R1_GO)]
        ]
    )


def _kb_r2() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Начинаем", callback_data=CB_R2_GO)]
        ]
    )


def _kb_r3() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Поехали", callback_data=CB_R3_GO)]
        ]
    )


def _push_meta(code: RoundCode) -> tuple[str, str, InlineKeyboardMarkup]:
    if code == RoundCode.R1:
        return TOUR_PUSH_R1_TEXT, INTRO_R1_IMAGE, _kb_r1()
    if code == RoundCode.R2:
        return TOUR_PUSH_R2_TEXT, INTRO_R2_IMAGE, _kb_r2()
    return TOUR_PUSH_R3_TEXT, INTRO_R3_IMAGE, _kb_r3()


def _sent_column(code: RoundCode):
    return {
        RoundCode.R1: User.tour_push_r1_sent_at,
        RoundCode.R2: User.tour_push_r2_sent_at,
        RoundCode.R3: User.tour_push_r3_sent_at,
    }[code]


def _within_tour_push_window(round_row: Round, now_naive: datetime) -> bool:
    """Стартовый пуш только в окне тура; после ends_at не догоняем."""
    return round_row.starts_at <= now_naive <= round_row.ends_at


async def _send_one_push(
    messenger: BroadcastAdapter,
    *,
    platform_user_id: int,
    code: RoundCode,
) -> bool:
    """``True`` если не нужно ретраить (успех или чат недоступен)."""
    caption, image, markup = _push_meta(code)
    try:
        await messenger.send_tour_intro_with_keyboard(
            platform_user_id,
            rel_image_path=image,
            caption=caption,
            reply_markup=markup,
        )
        return True
    except MessengerForbiddenError:
        log.info("tour_push skip forbidden user_id=%s round=%s", platform_user_id, code.value)
        return True
    except MessengerBadRequestError as e:
        log.warning("tour_push bad_request user_id=%s round=%s %s", platform_user_id, code.value, e)
        return False
    except Exception:
        log.exception("tour_push failed user_id=%s round=%s", platform_user_id, code.value)
        return False


async def try_send_tour_push_for_user(
    session: AsyncSession,
    messenger: BroadcastAdapter,
    *,
    user_id: int,
    round_row: Round,
) -> None:
    """Отправить пуш тура, если пора и ещё не отправляли."""
    user = await session.get(User, user_id)
    if user is None or user.is_blocked:
        return
    if user.email_verified_at is None and not user.is_admin:
        return
    now_naive = now_utc().replace(tzinfo=None)
    if not _within_tour_push_window(round_row, now_naive):
        return
    col = _sent_column(round_row.code)
    if getattr(user, col.key) is not None:
        return
    already_in_round = await session.scalar(
        select(
            exists().where(
                UserRoundProgress.user_id == user_id,
                UserRoundProgress.round_id == round_row.id,
            )
        )
    )
    if already_in_round:
        return
    ok = await _send_one_push(
        messenger,
        platform_user_id=int(user.telegram_user_id),
        code=round_row.code,
    )
    if ok:
        setattr(user, col.key, now_naive)
        await session.flush()


async def deliver_pending_tour_pushes_for_user(
    messenger: BroadcastAdapter, *, platform_user_id: int
) -> None:
    """После верификации: туры в активном окне, по которым пуш ещё не слали."""
    async with get_session() as session:
        r = await session.execute(
            select(Round)
            .where(Round.code.in_(_ALL_ROUNDS))
            .order_by(Round.starts_at.asc())
        )
        rounds = list(r.scalars().all())
        user = await session.scalar(
            select(User).where(User.telegram_user_id == platform_user_id)
        )
        if user is None:
            return
        for rnd in rounds:
            await try_send_tour_push_for_user(
                session, messenger, user_id=user.id, round_row=rnd
            )


async def process_due_tour_start_pushes(messenger: BroadcastAdapter) -> None:
    """Фон: пуши по турам в окне [starts_at, ends_at], один раз на пользователя."""
    async with get_session() as session:
        now_naive = now_utc().replace(tzinfo=None)
        r = await session.execute(
            select(Round)
            .where(Round.code.in_(_ALL_ROUNDS))
            .order_by(Round.starts_at.asc())
        )
        rounds = [x for x in r.scalars().all() if _within_tour_push_window(x, now_naive)]
        for rnd in rounds:
            col = _sent_column(rnd.code)
            has_round_progress = exists().where(
                UserRoundProgress.user_id == User.id,
                UserRoundProgress.round_id == rnd.id,
            )
            q = await session.execute(
                select(User)
                .where(
                    *eligible_user_base_stmt(),
                    col.is_(None),
                    ~has_round_progress,
                )
                .order_by(User.id.asc())
            )
            users = list(q.scalars().all())
            for user in users:
                ok = await _send_one_push(
                    messenger,
                    platform_user_id=int(user.telegram_user_id),
                    code=rnd.code,
                )
                if ok:
                    setattr(user, col.key, now_naive)
                    await session.flush()
                await asyncio.sleep(_SEND_GAP_SEC)
