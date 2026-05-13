"""Админка: /admin с меню на кнопках + совместимость со slash-командами."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton
from aiogram.types import InlineKeyboardMarkup as IBMarkup
from aiogram.types import Message
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.base import get_session
from app.db.models import Broadcast, Round, RoundCode, User, UserRoundProgress, WinnerSelection
from app.services.admin_export import export_round_csv, export_round_xlsx
from app.services.admin_progress_reset import reset_all_game_progress_for_user
from app.services.user_service import get_user_by_telegram_id
from app.services.winner_selection import admin_pick_winners_for_round

router = Router(name="admin")
log = logging.getLogger(__name__)

_CB_PREFIX = "adm"


def _is_admin(uid: int) -> bool:
    return get_settings().is_admin(uid)


def _parse_round(arg: str | None) -> RoundCode | None:
    if not arg:
        return None
    key = arg.strip().upper()
    try:
        return RoundCode(key)
    except ValueError:
        return None


def admin_main_menu_kb() -> IBMarkup:
    """Главное меню после /admin."""
    return IBMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Статистика", callback_data=f"{_CB_PREFIX}:stats"),
                InlineKeyboardButton(text="Справка", callback_data=f"{_CB_PREFIX}:help"),
            ],
            [
                InlineKeyboardButton(text="CSV · R1", callback_data=f"{_CB_PREFIX}:csv:R1"),
                InlineKeyboardButton(text="CSV · R2", callback_data=f"{_CB_PREFIX}:csv:R2"),
                InlineKeyboardButton(text="CSV · R3", callback_data=f"{_CB_PREFIX}:csv:R3"),
            ],
            [
                InlineKeyboardButton(text="Excel · R1", callback_data=f"{_CB_PREFIX}:xlsx:R1"),
                InlineKeyboardButton(text="Excel · R2", callback_data=f"{_CB_PREFIX}:xlsx:R2"),
                InlineKeyboardButton(text="Excel · R3", callback_data=f"{_CB_PREFIX}:xlsx:R3"),
            ],
            [
                InlineKeyboardButton(
                    text="Победители · R1", callback_data=f"{_CB_PREFIX}:win:R1"
                ),
                InlineKeyboardButton(
                    text="Победители · R2", callback_data=f"{_CB_PREFIX}:win:R2"
                ),
                InlineKeyboardButton(
                    text="Победители · R3", callback_data=f"{_CB_PREFIX}:win:R3"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Сбросить мой прогресс (тест)",
                    callback_data=f"{_CB_PREFIX}:reset_prompt",
                ),
            ],
        ]
    )


def _reset_confirm_kb() -> IBMarkup:
    return IBMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Да, обнулить",
                    callback_data=f"{_CB_PREFIX}:reset_exec",
                ),
                InlineKeyboardButton(
                    text="Отмена",
                    callback_data=f"{_CB_PREFIX}:reset_cancel",
                ),
            ],
        ]
    )


async def _answer_stats(message: Message) -> None:
    async with get_session() as session:
        n_users = int(await session.scalar(select(func.count()).select_from(User)) or 0)
        n_verified = int(
            await session.scalar(
                select(func.count())
                .select_from(User)
                .where(User.email_verified_at.isnot(None))
            )
            or 0
        )
        n_bc = int(
            await session.scalar(select(func.count()).select_from(Broadcast)) or 0
        )

        r = await session.execute(
            select(Round.id, Round.code, Round.starts_at, Round.ends_at).order_by(
                Round.starts_at.asc()
            )
        )
        round_rows = r.all()

        lines = [
            "<b>Сводка</b>",
            f"Пользователей: <b>{n_users}</b>, с email: <b>{n_verified}</b>",
            f"Рассылок (запусков): <b>{n_bc}</b>",
            "",
            "<b>Туры</b>",
        ]
        for rid, code, sa, ea in round_rows:
            n_prog = int(
                await session.scalar(
                    select(func.count())
                    .select_from(UserRoundProgress)
                    .where(UserRoundProgress.round_id == rid)
                )
                or 0
            )
            w_id = await session.scalar(
                select(WinnerSelection.id).where(WinnerSelection.round_id == rid)
            )
            w_ok = "да" if w_id else "нет"
            lines.append(
                f"{code.value}: прогресс <b>{n_prog}</b>, победители выбраны: <b>{w_ok}</b> "
                f"({sa} … {ea})"
            )

    await message.answer("\n".join(lines), parse_mode="HTML")


async def _answer_help(message: Message) -> None:
    text = (
        "<b>Админка</b>\n"
        "Главное меню: <code>/admin</code>\n\n"
        "Кнопки: статистика, справка, выгрузки CSV/Excel, отбор победителей по турам "
        "(доступен только после <code>ends_at</code> тура в БД).\n\n"
        "<b>Сброс прогресса (тест):</b> кнопка в меню или <code>/admin_reset</code> — "
        "удаляет ответы, баллы и темы по <b>твоему</b> аккаунту (email не трогаем). "
        "Победители из выгрузок: строки <code>winners</code> для тебя тоже сбрасываются.\n\n"
        "Также вручную: <code>/admin_stats</code>, "
        "<code>/export_csv R1</code>, <code>/export_xlsx R1</code>."
    )
    await message.answer(text, parse_mode="HTML")


async def _run_admin_winner_pick(message: Message, code: RoundCode) -> None:
    async with get_session() as session:
        res = await admin_pick_winners_for_round(session, code)

    if res.status == "round_not_found":
        await message.answer(f"Тур <b>{code.value}</b> не найден в базе.", parse_mode="HTML")
        return
    if res.status == "too_early":
        ends = res.round_row.ends_at if res.round_row else "—"
        await message.answer(
            f"Тур <b>{code.value}</b> ещё не закончен. "
            f"Окончание по расписанию (UTC): <code>{ends}</code>.\n"
            "Выбрать победителей можно только после этого момента.",
            parse_mode="HTML",
        )
        return
    if res.status == "ok_existing":
        sel = res.selection
        if sel is None:
            return
        await message.answer(
            f"Победители для <b>{code.value}</b> уже выбраны ранее "
            f"(<b>{sel.winners_count}</b> чел., запись №<code>{sel.id}</code>).",
            parse_mode="HTML",
        )
        return
    if res.status == "no_eligible":
        await message.answer(
            f"Не удалось отобрать победителей для <b>{code.value}</b>: "
            "нет участников с прогрессом в туре (или список пуст после фильтров).",
            parse_mode="HTML",
        )
        return
    if res.status == "ok_new":
        sel = res.selection
        if sel is None:
            return
        await message.answer(
            f"Готово: для <b>{code.value}</b> выбрано <b>{sel.winners_count}</b> победителей "
            f"(запись №<code>{sel.id}</code>).",
            parse_mode="HTML",
        )


async def _send_csv_export(message: Message, code: RoundCode) -> None:
    async with get_session() as session:
        try:
            raw = await export_round_csv(session, code)
        except ValueError as e:
            await message.answer(str(e))
            return

    fname = f"qclub_{code.value}_scores.csv"
    await message.answer_document(
        BufferedInputFile(raw, filename=fname),
        caption=f"Выгрузка {code.value} (CSV)",
    )


async def _prompt_reset_progress(message: Message) -> None:
    await message.answer(
        "<b>Сброс игрового прогресса</b>\n\n"
        "Будут удалены для <b>твоего</b> аккаунта: все ответы, баллы по турам, "
        "темы Тура 2 и записи победителя (если ты попадал в <code>winners</code>). "
        "Почта и профиль остаются.\n\n"
        "Подтверди действие:",
        parse_mode="HTML",
        reply_markup=_reset_confirm_kb(),
    )


async def _execute_reset_progress(message: Message, telegram_user_id: int) -> None:
    async with get_session() as session:
        user = await get_user_by_telegram_id(session, telegram_user_id)
        if user is None:
            await message.answer(
                "Не найден пользователь в базе. Отправь <code>/start</code> один раз.",
                parse_mode="HTML",
            )
            return
        stats = await reset_all_game_progress_for_user(session, user.id)

    lines = [
        "<b>Прогресс обнулён.</b> Можно снова нажать <code>/play</code>.\n",
        f"Удалено ответов: <b>{stats['answers']}</b>",
        f"строк прогресса по турам: <b>{stats['round_progress']}</b>",
        f"по темам (тур 2): <b>{stats['topic_progress']}</b>",
        f"записей победителя: <b>{stats['winners']}</b>",
    ]
    await message.answer("\n".join(lines), parse_mode="HTML")


async def _send_xlsx_export(message: Message, code: RoundCode) -> None:
    async with get_session() as session:
        try:
            raw = await export_round_xlsx(session, code)
        except ValueError as e:
            await message.answer(str(e))
            return

    fname = f"qclub_{code.value}_scores.xlsx"
    await message.answer_document(
        BufferedInputFile(raw, filename=fname),
        caption=f"Выгрузка {code.value} (Excel)",
    )


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if message.from_user is None:
        return
    if not _is_admin(message.from_user.id):
        await message.answer("Команда только для администраторов.")
        return

    await message.answer(
        "<b>Панель администратора</b>\nВыбери действие:",
        parse_mode="HTML",
        reply_markup=admin_main_menu_kb(),
    )


@router.callback_query(F.data.startswith(f"{_CB_PREFIX}:"))
async def on_admin_menu_callback(query: CallbackQuery) -> None:
    if query.from_user is None or not _is_admin(query.from_user.id):
        await query.answer("Недоступно.", show_alert=True)
        return

    data = query.data or ""
    parts = data.split(":", 2)
    action = parts[1] if len(parts) > 1 else ""

    if query.message is None:
        await query.answer()
        log.warning("admin callback without message: %s", data)
        return

    await query.answer()

    if action == "stats":
        await _answer_stats(query.message)
        return
    if action == "help":
        await _answer_help(query.message)
        return
    if action == "csv" and len(parts) > 2:
        code = _parse_round(parts[2])
        if code is not None:
            await _send_csv_export(query.message, code)
        return
    if action == "xlsx" and len(parts) > 2:
        code = _parse_round(parts[2])
        if code is not None:
            await _send_xlsx_export(query.message, code)
        return
    if action == "win" and len(parts) > 2:
        code = _parse_round(parts[2])
        if code is not None:
            await _run_admin_winner_pick(query.message, code)
        return
    if action == "reset_prompt":
        await _prompt_reset_progress(query.message)
        return
    if action == "reset_exec" and query.from_user is not None:
        await _execute_reset_progress(query.message, query.from_user.id)
        return
    if action == "reset_cancel":
        await query.message.answer("Сброс отменён.")
        return


@router.message(Command("admin_reset"))
async def cmd_admin_reset(message: Message) -> None:
    if message.from_user is None:
        return
    if not _is_admin(message.from_user.id):
        await message.answer("Команда только для администраторов.")
        return
    await _prompt_reset_progress(message)


@router.message(Command("admin_stats"))
async def cmd_admin_stats(message: Message) -> None:
    if message.from_user is None:
        return
    if not _is_admin(message.from_user.id):
        await message.answer("Команда только для администраторов.")
        return

    await _answer_stats(message)


@router.message(Command("export_csv"))
async def cmd_export_csv(message: Message, command: CommandObject) -> None:
    if message.from_user is None:
        return
    if not _is_admin(message.from_user.id):
        await message.answer("Команда только для администраторов.")
        return

    code = _parse_round(command.args)
    if code is None:
        await message.answer(
            "Укажи тур: <code>/export_csv R1</code> или открой <code>/admin</code>.",
            parse_mode="HTML",
        )
        return

    await _send_csv_export(message, code)


@router.message(Command("export_xlsx"))
async def cmd_export_xlsx(message: Message, command: CommandObject) -> None:
    if message.from_user is None:
        return
    if not _is_admin(message.from_user.id):
        await message.answer("Команда только для администраторов.")
        return

    code = _parse_round(command.args)
    if code is None:
        await message.answer(
            "Укажи тур: <code>/export_xlsx R1</code> или открой <code>/admin</code>.",
            parse_mode="HTML",
        )
        return

    await _send_xlsx_export(message, code)


@router.message(Command("admin_help"))
async def cmd_admin_help(message: Message) -> None:
    if message.from_user is None:
        return
    if not _is_admin(message.from_user.id):
        await message.answer("Команда только для администраторов.")
        return

    await _answer_help(message)
