"""Память FSM для MAX long poll (только онбординг ``waiting_email``)."""

from __future__ import annotations

_fsm: dict[int, str | None] = {}


def max_fsm_raw(uid: int) -> str | None:
    return _fsm.get(uid)


def max_fsm_clear(uid: int) -> None:
    _fsm.pop(uid, None)


def max_fsm_set(uid: int, state: str) -> None:
    _fsm[uid] = state
