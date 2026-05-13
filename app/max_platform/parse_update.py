"""Разбор полей из сырых Update MAX (long poll / webhook)."""

from __future__ import annotations

from typing import Any


def max_user_id_from_sender(sender: dict[str, Any]) -> int | None:
    if not sender:
        return None
    uid = sender.get("user_id")
    if uid is None:
        return None
    try:
        return int(uid)
    except (TypeError, ValueError):
        return None


def parse_message_created(update: dict[str, Any]) -> tuple[int, str | None, str | None] | None:
    """Возвращает ``(user_id, username, text)`` или ``None``."""
    msg = update.get("message")
    if not isinstance(msg, dict):
        return None
    sender = msg.get("sender") or update.get("user") or {}
    uid = max_user_id_from_sender(sender)
    if uid is None:
        return None
    uname = sender.get("username")
    if uname is not None:
        uname = str(uname)
    body = msg.get("body")
    text: str | None = None
    if isinstance(body, dict):
        raw = body.get("text")
        if raw is not None:
            text = str(raw)
    return uid, uname, text


def message_sender_is_bot(update: dict[str, Any]) -> bool:
    """Собственные сообщения бота в ``message_created`` — не обрабатывать (иначе шум/петли)."""
    msg = update.get("message")
    if not isinstance(msg, dict):
        return False
    sender = msg.get("sender") or {}
    return bool(sender.get("is_bot"))


def chat_id_from_update(update: dict[str, Any]) -> int | None:
    """``chat_id`` из события (нужен для ``POST /messages`` в ЛС MAX)."""
    raw = update.get("chat_id")
    if raw is not None:
        try:
            return int(raw)
        except (TypeError, ValueError):
            pass
    msg = update.get("message")
    if isinstance(msg, dict):
        rec = msg.get("recipient")
        if isinstance(rec, dict) and rec.get("chat_id") is not None:
            try:
                return int(rec["chat_id"])
            except (TypeError, ValueError):
                pass
        # редкий fallback: только id диалога
        for key in ("chat_id", "id"):
            raw = msg.get(key)
            if raw is not None:
                try:
                    return int(raw)
                except (TypeError, ValueError):
                    pass
    return None


def parse_bot_started(
    update: dict[str, Any],
) -> tuple[int, str | None, str, int | None] | None:
    """Старт диалога: ``(user_id, username, start_payload, chat_id)``."""
    user = update.get("user") or update.get("sender") or {}
    uid = max_user_id_from_sender(user)
    if uid is None:
        return None
    uname = user.get("username")
    if uname is not None:
        uname = str(uname)
    payload = (
        update.get("payload")
        or update.get("start_payload")
        or update.get("start")
        or ""
    )
    if not isinstance(payload, str):
        payload = str(payload)
    return uid, uname, payload.strip(), chat_id_from_update(update)


def parse_message_callback(
    update: dict[str, Any],
) -> tuple[str, str, dict[str, Any], dict[str, Any]] | None:
    """``(callback_id, button_payload, callback_obj, raw_update)``."""
    cb = update.get("callback")
    if not isinstance(cb, dict):
        return None
    cid = cb.get("callback_id") or cb.get("id")
    if not cid:
        return None
    cid_s = str(cid)
    payload = cb.get("payload")
    if payload is None:
        payload = cb.get("data") or ""
    if not isinstance(payload, str):
        payload = str(payload)
    return cid_s, payload, cb, update
