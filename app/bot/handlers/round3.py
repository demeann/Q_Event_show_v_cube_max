"""Тур 3 «Где логика»: картинка + два варианта ответа (callback)."""

from __future__ import annotations

import logging
from html import escape
from pathlib import Path
from typing import Any

from aiogram import Router
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from app.bot.gates import gate_playable_user
from app.bot.intro_media import INTRO_R3_IMAGE, answer_intro_with_optional_photo
from app.db.base import get_session
from app.db.models import Round, RoundCode, RoundQuestion, User, UserRoundProgress
from app.db.models.progress import RoundProgressStatus
from app.services.round1_play import (
    count_round_answers,
    format_correct_answer_line,
    get_next_round1_question,
    on_question_shown,
    try_answer_round1,
)
from app.services.round_schedule import get_playable_round_now
from app.services.tour_start_push import TOUR_PUSH_R3_TEXT

log = logging.getLogger(__name__)

router = Router(name="round3")

_R3_INTRO = TOUR_PUSH_R3_TEXT


class R3Go(CallbackData, prefix="r3go"):
    step: str = "go"


class R3Pick(CallbackData, prefix="r3"):
    qid: int
    idx: int


_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _options_from_payload(payload: dict[str, Any]) -> list[str]:
    raw = payload.get("options")
    if not isinstance(raw, list) or not raw:
        return []
    return [str(x) for x in raw]


def _question_caption(q: RoundQuestion) -> str:
    """Подпись к фото: номер + нумерованные варианты; на кнопках — только номера."""
    opts = _options_from_payload(q.payload)
    parts = [f"<b>Вопрос №{q.order_index}</b>"]
    if opts:
        parts += ["", "<b>Варианты ответа:</b>", ""]
        parts.append("\n\n".join(f"{i}. {escape(str(o))}" for i, o in enumerate(opts, 1)))
    return "\n".join(parts)


def _resolve_image_file(payload: dict[str, Any]) -> Path | None:
    raw = payload.get("image_path")
    if not raw:
        return None
    p = _PROJECT_ROOT / str(raw).lstrip("/")
    if p.is_file():
        return p
    log.warning("Round3 image missing: %s (expected at %s)", raw, p)
    return None


def _r3_keyboard(q: RoundQuestion) -> InlineKeyboardMarkup:
    opts = _options_from_payload(q.payload)
    row = [
        InlineKeyboardButton(
            text=str(i + 1),
            callback_data=R3Pick(qid=q.id, idx=i).pack(),
        )
        for i in range(len(opts))
    ]
    return InlineKeyboardMarkup(inline_keyboard=[row] if row else [])


def _r3_go_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Поехали", callback_data=R3Go().pack())]
        ]
    )


async def _send_r3_question(message: Message, q: RoundQuestion) -> None:
    caption = _question_caption(q)
    kb = _r3_keyboard(q)
    img = _resolve_image_file(q.payload)
    if img is not None:
        await message.answer_photo(photo=FSInputFile(img), caption=caption, reply_markup=kb)
    else:
        await message.answer(
            f"{caption}\n\n"
            "<i>(Файла картинки нет — положите его в репозиторий по пути из "
            "<code>content/round3.yaml</code> → <code>assets/round3/</code>.)</i>",
            reply_markup=kb,
        )


async def play_round3_entry(message: Message, session, user: User, active: Round) -> None:
    """Точка входа для /play при активном R3."""
    nq = await get_next_round1_question(session, user.id, active)
    if nq is None:
        await message.answer(
            "Ты уже прошёл все вопросы Тура 3. Отличная работа! Жди итогов шоу."
        )
        return

    n_ans = await count_round_answers(session, user.id, active.id)
    pr = await session.execute(
        select(UserRoundProgress).where(
            UserRoundProgress.user_id == user.id,
            UserRoundProgress.round_id == active.id,
        )
    )
    prog = pr.scalar_one_or_none()
    if (
        n_ans == 0
        and prog is not None
        and prog.status == RoundProgressStatus.NOT_STARTED
    ):
        await answer_intro_with_optional_photo(
            message,
            rel_image_path=INTRO_R3_IMAGE,
            caption=_R3_INTRO,
            reply_markup=_r3_go_keyboard(),
        )
        return

    await on_question_shown(session, user.id, active)
    await _send_r3_question(message, nq)


@router.callback_query(R3Go.filter())
async def on_r3_go(query: CallbackQuery, callback_data: R3Go) -> None:
    del callback_data
    if query.from_user is None or query.message is None:
        return
    msg = query.message
    async with get_session() as session:
        user, err = await gate_playable_user(session, query.from_user.id)
        if err:
            await query.answer(err, show_alert=True)
            return

        active = await get_playable_round_now(session)
        if active is None or active.code != RoundCode.R3:
            await query.answer("Сейчас нельзя продолжить тур.", show_alert=True)
            return

        if await count_round_answers(session, user.id, active.id) > 0:
            await query.answer("Уже отвечаешь на вопросы.", show_alert=True)
            return

        pr = await session.execute(
            select(UserRoundProgress).where(
                UserRoundProgress.user_id == user.id,
                UserRoundProgress.round_id == active.id,
            )
        )
        prog = pr.scalar_one_or_none()
        if prog is not None and prog.status != RoundProgressStatus.NOT_STARTED:
            await query.answer("Первый вопрос уже открыт выше.", show_alert=True)
            return

        nq = await get_next_round1_question(session, user.id, active)
        if nq is None:
            await query.answer("Тур уже завершён.", show_alert=True)
            return

        await on_question_shown(session, user.id, active)
        await query.answer()
        await _send_r3_question(msg, nq)


@router.callback_query(R3Pick.filter())
async def on_r3_pick(query: CallbackQuery, callback_data: R3Pick) -> None:
    if query.from_user is None or query.message is None:
        return
    msg = query.message
    async with get_session() as session:
        user, err = await gate_playable_user(session, query.from_user.id)
        if err:
            await query.answer(err, show_alert=True)
            return

        active = await get_playable_round_now(session)
        if active is None or active.code != RoundCode.R3:
            await query.answer("Сейчас нельзя ответить в этом туре.", show_alert=True)
            return

        q_row = await session.get(RoundQuestion, callback_data.qid)
        if (
            q_row is None
            or q_row.round_id != active.id
            or not _options_from_payload(q_row.payload)
        ):
            await query.answer("Вопрос устарел. Нажми /play снова.", show_alert=True)
            return

        ok, awarded, err_msg = await try_answer_round1(
            session,
            user_id=user.id,
            round_row=active,
            question=q_row,
            selected_idx=callback_data.idx,
        )
        if not ok:
            await query.answer(err_msg or "Ошибка", show_alert=True)
            return

        await query.answer()

        pld = q_row.payload if isinstance(q_row.payload, dict) else {}
        fc_raw = pld.get("feedback_correct")
        fb_legacy = pld.get("feedback")
        fc = fc_raw.strip() if isinstance(fc_raw, str) else ""
        fw_raw = pld.get("feedback_wrong")
        fw = fw_raw.strip() if isinstance(fw_raw, str) else ""

        if awarded > 0:
            if fc:
                feedback = fc
            else:
                lines = ["Верно!"]
                if isinstance(fb_legacy, str) and fb_legacy.strip():
                    lines.append(fb_legacy.strip())
                feedback = "\n\n".join(lines)
        else:
            if fw:
                feedback = fw
            else:
                feedback = (
                    "Увы, не в этот раз.\n\n"
                    "Баллы не снимаем — держим удар и идём дальше.\n\n"
                ) + format_correct_answer_line(pld)
        await msg.answer(feedback)

        nq = await get_next_round1_question(session, user.id, active)
        if nq is None:
            await msg.answer(
                "Ты молодец! Это был последний тур нашего Конкурса в Кубе!\n\n"
                "Спасибо за ответы, участие и вовлечение.\n\n"
                "Итоги пришлём письмом <b>25.05</b> на указанную почту — следи за ящиком!"
            )
            return

        await on_question_shown(session, user.id, active)
        await _send_r3_question(msg, nq)
