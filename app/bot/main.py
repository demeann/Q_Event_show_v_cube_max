"""Запуск бота: long polling (разработка) или webhook (продакшен)."""

from __future__ import annotations

import asyncio
import logging
import sys

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError
from aiogram.types import BotCommand
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from app.bot.middlewares.access import AccessMiddleware
from app.bot.router import get_root_router
from app.bot.scheduler import build_scheduler
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.base import dispose_engine
from app.max_platform.runner import run_max_polling
from app.messaging.broadcast_adapter import TelegramBroadcastAdapter

log = logging.getLogger(__name__)

# По умолчанию в aiogram 60 с — на «медленных» каналах до api.telegram.org этого мало.
_BOT_HTTP_TIMEOUT_SEC = 120.0


def _webhook_path_normalized(settings: Settings) -> str:
    p = settings.webhook_path.strip()
    return p if p.startswith("/") else f"/{p}"


def _webhook_full_url(settings: Settings) -> str:
    base = settings.webhook_base_url.rstrip("/")
    return f"{base}{_webhook_path_normalized(settings)}"


def _build_bot_and_dispatcher(settings: Settings) -> tuple[Bot, Dispatcher]:
    session = AiohttpSession(timeout=_BOT_HTTP_TIMEOUT_SEC)
    bot = Bot(
        token=settings.bot_token,
        session=session,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            protect_content=True,
        ),
    )
    dp = Dispatcher()
    dp.update.outer_middleware(AccessMiddleware())
    dp.include_router(get_root_router())
    return bot, dp


async def _set_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Регистрация и профиль"),
            BotCommand(command="play", description="Активный тур (1–3)"),
        ]
    )


async def _run_polling() -> None:
    settings = get_settings()
    bot, dp = _build_bot_and_dispatcher(settings)
    messenger = TelegramBroadcastAdapter(bot)
    scheduler = build_scheduler(messenger)
    scheduler.start()

    await _set_bot_commands(bot)

    try:
        await bot.delete_webhook(drop_pending_updates=False)
    except TelegramNetworkError as e:
        log.warning("delete_webhook before polling: %s", e)

    log.info(
        "Bot polling started (parse_mode=HTML, http_timeout=%ss)",
        _BOT_HTTP_TIMEOUT_SEC,
    )
    try:
        await dp.start_polling(bot)
    except TelegramNetworkError as e:
        log.error(
            "Не удаётся достучаться до MAX API (%s). "
            "Проверь интернет, может включен VPN?",
            e,
        )
        raise SystemExit(1) from None
    finally:
        scheduler.shutdown(wait=False)
        await dispose_engine()
        log.info("Bot stopped")


def _create_webhook_app(settings: Settings) -> web.Application:
    bot, dp = _build_bot_and_dispatcher(settings)
    messenger = TelegramBroadcastAdapter(bot)
    scheduler = build_scheduler(messenger)
    path = _webhook_path_normalized(settings)
    wh_url = _webhook_full_url(settings)
    secret = settings.webhook_secret.strip() or None

    app = web.Application()
    app["settings"] = settings
    app["bot"] = bot
    app["dispatcher"] = dp
    app["scheduler"] = scheduler

    async def _dispose_engine(_app: web.Application) -> None:
        await dispose_engine()

    app.on_shutdown.append(_dispose_engine)

    setup_application(app, dp, bot=bot)

    async def _on_startup(_app: web.Application) -> None:
        b: Bot = _app["bot"]
        sched = _app["scheduler"]
        await _set_bot_commands(b)
        await b.set_webhook(
            url=wh_url,
            secret_token=secret,
            drop_pending_updates=True,
        )
        sched.start()
        log.info(
            "Webhook listening %s:%s route POST %s | registered URL %s",
            settings.webhook_listen_host,
            settings.webhook_listen_port,
            path,
            wh_url,
        )

    async def _stop_scheduler_and_webhook(_app: web.Application) -> None:
        b: Bot = _app["bot"]
        sched = _app["scheduler"]
        sched.shutdown(wait=False)
        try:
            await b.delete_webhook(drop_pending_updates=False)
        except TelegramNetworkError as e:
            log.warning("delete_webhook: %s", e)
        log.info("Webhook: scheduler stopped, webhook deleted")

    app.on_startup.append(_on_startup)
    app.on_shutdown.append(_stop_scheduler_and_webhook)

    handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        handle_in_background=True,
        secret_token=secret,
    )
    handler.register(app, path=path)
    return app


async def _run_max_messenger() -> None:
    await run_max_polling()


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_dir)

    if settings.messenger_platform == "max":
        if settings.run_mode != "polling":
            log.error(
                "MESSENGER_PLATFORM=max: сейчас поддержан только RUN_MODE=polling "
                "(webhook MAX — в следующих шагах)."
            )
            sys.exit(1)
        asyncio.run(_run_max_messenger())
        return

    if settings.run_mode == "webhook":
        if not settings.webhook_base_url.startswith("https://"):
            log.error(
                "RUN_MODE=webhook: укажите WEBHOOK_BASE_URL с https:// (так требует Telegram)."
            )
            sys.exit(1)
        app = _create_webhook_app(settings)
        web.run_app(
            app,
            host=settings.webhook_listen_host,
            port=settings.webhook_listen_port,
            print=None,
        )
        return

    asyncio.run(_run_polling())


if __name__ == "__main__":
    main()
