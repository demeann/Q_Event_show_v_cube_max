"""FSM-состояния пользовательских сценариев."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    """Ожидание корпоративного email."""

    waiting_email = State()
