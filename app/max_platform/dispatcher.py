"""Long poll MAX: маршрутизация update → те же обработчики, что и в Telegram."""

from __future__ import annotations

import logging
from typing import Any

from aiogram.filters.command import CommandObject

from app.bot.handlers.admin import (
    cmd_admin,
    cmd_admin_help,
    cmd_admin_reset,
    cmd_admin_stats,
    cmd_export_csv,
    cmd_export_xlsx,
    on_admin_menu_callback,
)
from app.bot.handlers.main_menu import placeheld_tours
from app.bot.handlers.play import cmd_play
from app.bot.handlers.round1 import (
    R1Forward,
    R1Pick,
    on_r1_forward,
    on_r1_pick,
)
from app.bot.handlers.round2 import (
    R2Go,
    R2Pick,
    R2Topic,
    on_r2_go,
    on_r2_pick,
    on_r2_topic_chosen,
)
from app.bot.handlers.round3 import (
    R3Go,
    R3Pick,
    on_r3_go,
    on_r3_pick,
)
from app.bot.logic.onboarding_core import (
    handle_need_text_only_email,
    handle_start,
    handle_waiting_email_text,
    is_waiting_email_state,
)
from app.bot.states import OnboardingStates
from app.core.config import get_settings
from app.db.base import get_session
from app.max_platform.access_gate import max_access_gate
from app.max_platform.client import MaxPlatformClient
from app.max_platform.fsm_memory import max_fsm_clear, max_fsm_raw, max_fsm_set
from app.max_platform.parse_update import (
    chat_id_from_update,
    max_user_id_from_sender,
    message_sender_is_bot,
    parse_bot_started,
    parse_message_callback,
    parse_message_created,
)
from app.max_platform.shim import MaxUiCallbackQuery, MaxUiMessage
from app.messaging.broadcast_adapter import MaxBroadcastAdapter
from app.max_platform.update_batch import ordered_updates
from app.services.tour_start_push import deliver_pending_tour_pushes_for_user

log = logging.getLogger(__name__)


def _cmd_and_args(text: str | None) -> tuple[str | None, str]:
    if not text or not text.startswith("/"):
        return None, ""
    parts = text.split(maxsplit=1)
    cmd = parts[0].split("@", 1)[0].lower()
    rest = parts[1].strip() if len(parts) > 1 else ""
    return cmd, rest


class MaxUpdateDispatcher:
    def __init__(self, client: MaxPlatformClient) -> None:
        self._c = client

    async def run_forever(self) -> None:
        marker: int | None = None
        types = ["message_created", "message_callback", "bot_started"]
        while True:
            data = await self._c.get_updates(
                marker=marker,
                types=types,
                timeout=45,
            )
            updates = ordered_updates(data.get("updates") or [])
            marker = data.get("marker")
            for u in updates:
                try:
                    await self._dispatch(u)
                except Exception:
                    log.exception("MAX dispatch failed for update snippet=%r", str(u)[:500])

    async def _dispatch(self, u: dict[str, Any]) -> None:
        ut = u.get("update_type")
        if ut == "bot_started":
            parsed = parse_bot_started(u)
            if parsed is None:
                return
            uid, uname, payload, max_chat_id = parsed
            await self._do_start(uid, uname, payload, platform_chat_id=max_chat_id)
            return
        if ut == "message_created":
            if message_sender_is_bot(u):
                return
            parsed = parse_message_created(u)
            if parsed is None:
                return
            uid, uname, text = parsed
            await self._handle_incoming_message(
                uid, uname, text, platform_chat_id=chat_id_from_update(u)
            )
            return
        if ut == "message_callback":
            await self._handle_callback_raw(u)
            return

    async def _do_start(
        self,
        uid: int,
        uname: str | None,
        start_payload: str,
        *,
        platform_chat_id: int | None,
    ) -> None:
        settings = get_settings()
        msg = MaxUiMessage(
            self._c, user_id=uid, username=uname, text=None, chat_id=platform_chat_id
        )

        async def reply_html(t: str) -> None:
            await msg.answer(t, parse_mode="HTML")

        async def state_clear() -> None:
            max_fsm_clear(uid)

        async def state_set_waiting_email() -> None:
            max_fsm_set(uid, OnboardingStates.waiting_email.state)

        async with get_session() as session:
            await handle_start(
                session,
                settings,
                user_id=uid,
                username=uname,
                start_payload=start_payload,
                reply_html=reply_html,
                state_clear=state_clear,
                state_set_waiting_email=state_set_waiting_email,
                platform_chat_id=platform_chat_id,
            )

    async def _handle_incoming_message(
        self,
        uid: int,
        uname: str | None,
        text: str | None,
        *,
        platform_chat_id: int | None,
    ) -> None:
        settings = get_settings()
        msg = MaxUiMessage(
            self._c,
            user_id=uid,
            username=uname,
            text=text,
            chat_id=platform_chat_id,
        )
        fsm_state = max_fsm_raw(uid)

        async def reply_html(t: str) -> None:
            await msg.answer(t, parse_mode="HTML")

        if not await max_access_gate(
            uid,
            text,
            fsm_state,
            reply_html=reply_html,
        ):
            return

        if is_waiting_email_state(fsm_state):
            if text is not None:
                async with get_session() as session:
                    async def _clear() -> None:
                        max_fsm_clear(uid)

                    async def _after_verified() -> None:
                        msgr = MaxBroadcastAdapter(self._c)
                        await deliver_pending_tour_pushes_for_user(
                            msgr, platform_user_id=uid
                        )

                    await handle_waiting_email_text(
                        session,
                        settings,
                        user_id=uid,
                        username=uname,
                        raw_email_text=text,
                        reply_html=reply_html,
                        state_clear=_clear,
                        after_email_verified=_after_verified,
                        platform_chat_id=platform_chat_id,
                    )
            else:
                await handle_need_text_only_email(reply_html)
            return

        cmd, rest = _cmd_and_args(text)
        if cmd == "/start":
            await self._do_start(uid, uname, rest, platform_chat_id=platform_chat_id)
            return
        if cmd == "/play":
            await cmd_play(msg)
            return
        if cmd == "/admin":
            await cmd_admin(msg)
            return
        if cmd == "/admin_reset":
            await cmd_admin_reset(msg)
            return
        if cmd == "/admin_stats":
            await cmd_admin_stats(msg)
            return
        if cmd == "/admin_help":
            await cmd_admin_help(msg)
            return
        if cmd == "/export_csv":
            co = CommandObject(prefix="/", command="export_csv", args=rest or None)
            await cmd_export_csv(msg, co)
            return
        if cmd == "/export_xlsx":
            co = CommandObject(prefix="/", command="export_xlsx", args=rest or None)
            await cmd_export_xlsx(msg, co)
            return
        if text is not None:
            await placeheld_tours(msg)

    async def _handle_callback_raw(self, u: dict[str, Any]) -> None:
        parsed = parse_message_callback(u)
        if parsed is None:
            return
        cid, payload, cb, update = parsed
        user = cb.get("user") or {}
        if not user and isinstance(update.get("user"), dict):
            user = update["user"]
        uid = max_user_id_from_sender(user)
        if uid is None:
            return
        uname = user.get("username")
        if uname is not None:
            uname = str(uname)
        fsm_state = max_fsm_raw(uid)
        max_chat_id = chat_id_from_update(u)
        base_msg = MaxUiMessage(
            self._c, user_id=uid, username=uname, chat_id=max_chat_id
        )
        cbq = MaxUiCallbackQuery(
            self._c,
            user_id=uid,
            username=uname,
            callback_id=cid,
            message=base_msg,
            data=payload,
        )

        async def reply_html(t: str) -> None:
            await base_msg.answer(t, parse_mode="HTML")

        async def reply_alert(t: str) -> None:
            await cbq.answer(t, show_alert=True)

        if not await max_access_gate(
            uid,
            None,
            fsm_state,
            reply_html=reply_html,
            reply_callback_alert=reply_alert,
        ):
            return

        if payload.startswith("adm:"):
            await on_admin_menu_callback(cbq)
            return
        if payload.startswith("r1fwd:"):
            await on_r1_forward(cbq, R1Forward.unpack(payload))
            return
        if payload.startswith("r1:"):
            await on_r1_pick(cbq, R1Pick.unpack(payload))
            return
        if payload.startswith("r2t:"):
            await on_r2_topic_chosen(cbq, R2Topic.unpack(payload))
            return
        if payload.startswith("r2go:"):
            await on_r2_go(cbq, R2Go.unpack(payload))
            return
        if payload.startswith("r2:"):
            await on_r2_pick(cbq, R2Pick.unpack(payload))
            return
        if payload.startswith("r3go:"):
            await on_r3_go(cbq, R3Go.unpack(payload))
            return
        if payload.startswith("r3:"):
            await on_r3_pick(cbq, R3Pick.unpack(payload))
            return
        await cbq.answer("Неизвестная кнопка. Попробуй /play.", show_alert=True)
