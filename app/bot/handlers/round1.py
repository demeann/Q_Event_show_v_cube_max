"""Тур 1 «Кто хочет стать миллионером»: ответы по callback."""

from __future__ import annotations

from html import escape
from typing import Any

from aiogram import Router
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from app.bot.gates import gate_playable_user
from app.bot.intro_media import INTRO_R1_IMAGE, answer_intro_with_optional_photo
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
from app.services.tour_start_push import TOUR_PUSH_R1_TEXT

router = Router(name="round1")

_R1_INTRO = TOUR_PUSH_R1_TEXT


class R1Forward(CallbackData, prefix="r1fwd"):
    step: str = "go"


class R1Pick(CallbackData, prefix="r1"):
    qid: int
    idx: int


def _r1_forward_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Вперёд", callback_data=R1Forward().pack())]
        ]
    )


def _options_from_payload(payload: dict[str, Any]) -> list[str]:
    raw = payload.get("options")
    if not isinstance(raw, list) or not raw:
        return []
    return [str(x) for x in raw]


def _question_caption(q: RoundQuestion) -> str:
    """Текст вопроса + нумерованные варианты; на кнопках — только номера (удобно в мобильном Telegram)."""
    body = str(q.payload.get("text", ""))
    opts = _options_from_payload(q.payload)
    parts = [f"<b>Вопрос {q.order_index}.</b>", "", escape(body)]
    if opts:
        parts += ["", "<b>Варианты ответа:</b>", ""]
        parts.append("\n\n".join(f"{i}. {escape(str(o))}" for i, o in enumerate(opts, 1)))
    return "\n".join(parts)


def _r1_keyboard(q: RoundQuestion) -> InlineKeyboardMarkup:
    opts = _options_from_payload(q.payload)
    row = [
        InlineKeyboardButton(
            text=str(i + 1),
            callback_data=R1Pick(qid=q.id, idx=i).pack(),
        )
        for i in range(len(opts))
    ]
    return InlineKeyboardMarkup(inline_keyboard=[row] if row else [])


async def play_round1_entry(message: Message, session, user: User, active: Round) -> None:
    """Точка входа для /play при активном R1."""
    nq = await get_next_round1_question(session, user.id, active)
    if nq is None:
        await message.answer(
            "Ты уже прошёл все вопросы Тура 1. Отличная работа! Жди следующий тур."
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
            rel_image_path=INTRO_R1_IMAGE,
            caption=_R1_INTRO,
            reply_markup=_r1_forward_keyboard(),
        )
        return

    await on_question_shown(session, user.id, active)
    await message.answer(
        _question_caption(nq),
        reply_markup=_r1_keyboard(nq),
    )


@router.callback_query(R1Forward.filter())
async def on_r1_forward(query: CallbackQuery, callback_data: R1Forward) -> None:
    del callback_data  # единственный шаг
    if query.from_user is None or query.message is None:
        return
    msg = query.message
    async with get_session() as session:
        user, err = await gate_playable_user(session, query.from_user.id)
        if err:
            await query.answer(err, show_alert=True)
            return

        active = await get_playable_round_now(session)
        if active is None or active.code != RoundCode.R1:
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
        # Только с пуша «Вперёд» без /play — прогресса ещё нет.
        if prog is not None and prog.status != RoundProgressStatus.NOT_STARTED:
            await query.answer("Первый вопрос уже открыт выше.", show_alert=True)
            return

        nq = await get_next_round1_question(session, user.id, active)
        if nq is None:
            await query.answer("Тур уже завершён.", show_alert=True)
            return

        await on_question_shown(session, user.id, active)
        await query.answer()
        await msg.answer(
            _question_caption(nq),
            reply_markup=_r1_keyboard(nq),
        )


@router.callback_query(R1Pick.filter())
async def on_r1_pick(query: CallbackQuery, callback_data: R1Pick) -> None:
    if query.from_user is None or query.message is None:
        return
    msg = query.message
    async with get_session() as session:
        user, err = await gate_playable_user(session, query.from_user.id)
        if err:
            await query.answer(err, show_alert=True)
            return

        active = await get_playable_round_now(session)
        if active is None or active.code != RoundCode.R1:
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
        fc = pld.get("feedback_correct") if isinstance(pld.get("feedback_correct"), str) else ""
        fw = pld.get("feedback_wrong") if isinstance(pld.get("feedback_wrong"), str) else ""

        if awarded > 0:
            feedback = fc.strip() if fc.strip() else "Верно!"
        else:
            if fw.strip():
                feedback = fw.strip()
            else:
                feedback = (
                    "Увы, не в этот раз.\n\n"
                    "Баллы не снимаем — держим удар и идём дальше.\n\n"
                ) + format_correct_answer_line(pld)
        await msg.answer(feedback)

        nq = await get_next_round1_question(session, user.id, active)
        if nq is None:
            await msg.answer(
                "Ты молодец, спасибо за твои ответы!\n\n"
                "Мы объявим результаты в письме, которое пришлём на указанную почту "
                "<b>25.05</b>.\n\n"
                "А пока принимай участие в следующем туре — он стартует <b>18.05</b>, "
                "мы пришлём напоминание!📆"
            )
            return

        await on_question_shown(session, user.id, active)
        await msg.answer(
            _question_caption(nq),
            reply_markup=_r1_keyboard(nq),
        )
