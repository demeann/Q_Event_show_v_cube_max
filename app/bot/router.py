"""Сборка Router для Dispatcher."""

from __future__ import annotations

from aiogram import Router

from app.bot.handlers import admin, main_menu, onboarding, play, round1, round2, round3


def get_root_router() -> Router:
    root = Router()
    root.include_router(admin.router)
    root.include_router(onboarding.router)
    root.include_router(play.router)
    root.include_router(round1.router)
    root.include_router(round2.router)
    root.include_router(round3.router)
    root.include_router(main_menu.router)
    return root
