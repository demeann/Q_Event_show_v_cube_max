"""Тур 2 «Твоя игра»: выбор темы и ответы по callback."""

from __future__ import annotations

from html import escape
from typing import Any

from aiogram import Router
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from app.bot.gates import gate_playable_user
from app.bot.intro_media import INTRO_R2_IMAGE, answer_intro_with_optional_photo
from app.db.base import get_session
from app.db.models import Round, RoundCode, RoundQuestion, User, UserRoundProgress
from app.services.round2_play import (
    all_r2_topics_finished_for_user,
    ensure_r2_round_started_on_show,
    first_unanswered_in_topic,
    get_resume_question_r2,
    open_topic_for_user,
    ordered_topic_codes,
    round2_needs_go_button,
    topics_available_to_open,
    try_answer_round2,
)
from app.services.round_schedule import get_playable_round_now
from app.services.tour_start_push import TOUR_PUSH_R2_TEXT

router = Router(name="round2")

_R2_INTRO = TOUR_PUSH_R2_TEXT

_R2_FINISHED_FOLLOWUP = (
    "Ты молодец!🎉\n\n"
    "Это была последняя тема тура, спасибо за твои ответы!\n\n"
    "Мы объявим результаты в письме, которое пришлём <b>25.05</b> на указанную почту, "
    "а пока принимай участие в финальном туре, который стартует <b>20.05</b>.📆"
)


async def _send_round2_completed(msg: Message) -> None:
    await msg.answer(_R2_FINISHED_FOLLOWUP)

R2_TOPIC_TITLES: dict[str, str] = {
    "T1": "Преимущества Q CLUB",
    "T2": "Задания и активности",
    "T3": "Карта лояльности и сервис",
}


class R2Topic(CallbackData, prefix="r2t"):
    t: str


class R2Go(CallbackData, prefix="r2go"):
    step: str = "go"


class R2Pick(CallbackData, prefix="r2"):
    qid: int
    idx: int


def _btn_caption(text: str, max_len: int = 64) -> str:
    t = text.strip()
    if len(t) <= max_len:
        return t
    return t[: max_len - 1] + "…"


def _options_from_payload(payload: dict[str, Any]) -> list[str]:
    raw = payload.get("options")
    if not isinstance(raw, list) or not raw:
        return []
    return [str(x) for x in raw]


def _r2_question_caption(q: RoundQuestion) -> str:
    tc = q.topic_code or ""
    title = R2_TOPIC_TITLES.get(tc, tc)
    body = str(q.payload.get("text", ""))
    opts = _options_from_payload(q.payload)
    parts = [f"<b>{escape(title)}</b>", "", escape(body)]
    if opts:
        parts += ["", "<b>Варианты ответа:</b>", ""]
        parts.append("\n\n".join(f"{i}. {escape(str(o))}" for i, o in enumerate(opts, 1)))
    return "\n".join(parts)


def _r2_answer_keyboard(q: RoundQuestion) -> InlineKeyboardMarkup:
    opts = _options_from_payload(q.payload)
    row = [
        InlineKeyboardButton(
            text=str(i + 1),
            callback_data=R2Pick(qid=q.id, idx=i).pack(),
        )
        for i in range(len(opts))
    ]
    return InlineKeyboardMarkup(inline_keyboard=[row] if row else [])


def _topic_pick_keyboard(topic_codes: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=_btn_caption(R2_TOPIC_TITLES.get(c, c)),
                callback_data=R2Topic(t=c).pack(),
            )
        ]
        for c in topic_codes
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _r2_go_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Поехали", callback_data=R2Go().pack())]
        ]
    )


async def play_round2_entry(message: Message, session, user: User, active: Round) -> None:
    topics_order = await ordered_topic_codes(session, active.id)
    if await all_r2_topics_finished_for_user(session, user.id, active.id, topics_order):
        await _send_round2_completed(message)
        return

    resume = await get_resume_question_r2(session, user.id, active)
    if resume:
        await ensure_r2_round_started_on_show(session, user.id, active)
        await message.answer(
            _r2_question_caption(resume),
            reply_markup=_r2_answer_keyboard(resume),
        )
        return

    avail = await topics_available_to_open(session, user.id, active.id, topics_order)
    if not avail:
        await message.answer(
            "Не удалось продолжить тур автоматически. Напиши /play ещё раз "
            "или обратись к организаторам Q CLUB."
        )
        return

    if await round2_needs_go_button(session, user.id, active.id):
        await answer_intro_with_optional_photo(
            message,
            rel_image_path=INTRO_R2_IMAGE,
            caption=_R2_INTRO,
            reply_markup=_r2_go_keyboard(),
        )
        return

    await ensure_r2_round_started_on_show(session, user.id, active)
    await message.answer(
        "<b>Выбери тему:</b>",
        reply_markup=_topic_pick_keyboard(avail),
    )


async def _continue_round2_ui(
    msg: Message,
    session,
    user: User,
    active: Round,
    *,
    question: RoundQuestion,
    awarded: int,
) -> None:
    pld = question.payload if isinstance(question.payload, dict) else {}
    fc_raw = pld.get("feedback_correct")
    fw_raw = pld.get("feedback_wrong")
    fc = fc_raw.strip() if isinstance(fc_raw, str) else ""
    fw = fw_raw.strip() if isinstance(fw_raw, str) else ""

    if awarded > 0:
        feedback = fc if fc else f"Верно! +{awarded} баллов."
    else:
        feedback = (
            fw
            if fw
            else (
                "Увы, не в этот раз.\n\n"
                "Баллы не снимаем. Тема для тебя закрыта — выбери другую, если ещё есть."
            )
        )
    await msg.answer(feedback)

    topics_order = await ordered_topic_codes(session, active.id)
    if await all_r2_topics_finished_for_user(session, user.id, active.id, topics_order):
        await _send_round2_completed(msg)
        return

    resume = await get_resume_question_r2(session, user.id, active)
    if resume:
        await msg.answer(
            _r2_question_caption(resume),
            reply_markup=_r2_answer_keyboard(resume),
        )
        return

    avail = await topics_available_to_open(session, user.id, active.id, topics_order)
    if avail:
        await msg.answer(
            "Выбери следующую тему:",
            reply_markup=_topic_pick_keyboard(avail),
        )
    else:
        await msg.answer("Нажми /play, чтобы продолжить.")


@router.callback_query(R2Go.filter())
async def on_r2_go(query: CallbackQuery, callback_data: R2Go) -> None:
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
        if active is None or active.code != RoundCode.R2:
            await query.answer("Сейчас нельзя продолжить тур.", show_alert=True)
            return

        if not await round2_needs_go_button(session, user.id, active.id):
            await query.answer("Выбор темы уже открыт выше.", show_alert=True)
            return

        topics_order = await ordered_topic_codes(session, active.id)
        avail = await topics_available_to_open(session, user.id, active.id, topics_order)
        if not avail:
            await query.answer("Нет доступных тем. Нажми /play.", show_alert=True)
            return

        await ensure_r2_round_started_on_show(session, user.id, active)
        await query.answer()
        await msg.answer(
            "<b>Выбери тему:</b>",
            reply_markup=_topic_pick_keyboard(avail),
        )


@router.callback_query(R2Topic.filter())
async def on_r2_topic_chosen(query: CallbackQuery, callback_data: R2Topic) -> None:
    if query.from_user is None or query.message is None:
        return
    msg = query.message
    async with get_session() as session:
        user, err = await gate_playable_user(session, query.from_user.id)
        if err:
            await query.answer(err, show_alert=True)
            return

        active = await get_playable_round_now(session)
        if active is None or active.code != RoundCode.R2:
            await query.answer("Сейчас нельзя выбрать тему.", show_alert=True)
            return

        topics_order = await ordered_topic_codes(session, active.id)
        if callback_data.t not in topics_order:
            await query.answer("Тема недоступна.", show_alert=True)
            return

        tp_row, oerr = await open_topic_for_user(
            session, user.id, active.id, callback_data.t
        )
        if tp_row is None:
            await query.answer(oerr or "Нельзя открыть тему.", show_alert=True)
            return

        nq = await first_unanswered_in_topic(
            session, user.id, active.id, callback_data.t
        )
        if nq is None:
            await query.answer("По этой теме больше нет вопросов.", show_alert=True)
            return

        await ensure_r2_round_started_on_show(session, user.id, active)
        await query.answer()
        await msg.answer(
            _r2_question_caption(nq),
            reply_markup=_r2_answer_keyboard(nq),
        )


@router.callback_query(R2Pick.filter())
async def on_r2_pick(query: CallbackQuery, callback_data: R2Pick) -> None:
    if query.from_user is None or query.message is None:
        return
    msg = query.message
    async with get_session() as session:
        user, err = await gate_playable_user(session, query.from_user.id)
        if err:
            await query.answer(err, show_alert=True)
            return

        active = await get_playable_round_now(session)
        if active is None or active.code != RoundCode.R2:
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

        ok, awarded, err_msg = await try_answer_round2(
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
        await _continue_round2_ui(
            msg, session, user, active, question=q_row, awarded=awarded
        )
