"""Единая настройка логирования.

Идемпотентна: повторный вызов не дублирует обработчики.

Куда пишем:
- stdout (всегда);
- ротируемый файл `<log_dir>/bot.log` (5 МБ, до 5 архивов), если задана `log_dir`.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def configure_logging(level: str = "INFO", log_dir: Path | str | None = None) -> None:
    """Сконфигурировать root-logger.

    Args:
        level: один из DEBUG/INFO/WARNING/ERROR/CRITICAL.
        log_dir: директория для файлового лога. Если None — только stdout.
    """
    global _configured
    if _configured:
        return

    root = logging.getLogger()
    root.setLevel(level.upper())

    for handler in list(root.handlers):
        root.removeHandler(handler)

    formatter = logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    if log_dir is not None:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_path / "bot.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    # Прижимаем шумные библиотеки.
    logging.getLogger("aiogram").setLevel(logging.INFO)
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    _configured = True


def reset_logging_for_tests() -> None:
    """Тестовый хелпер: сбросить флаг, чтобы можно было переинициализировать."""
    global _configured
    _configured = False
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
