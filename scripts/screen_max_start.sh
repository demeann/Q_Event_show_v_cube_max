#!/usr/bin/env bash
# Запуск MAX-бота в отсоединённой screen-сессии (long poll).
# Использование: ./scripts/screen_max_start.sh [--force]
# Переменные: SCREEN_MAX_ROOT, SCREEN_MAX_SESSION, SCREEN_MAX_PYTHON

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/screen_max_common.sh"

if ! command -v screen >/dev/null 2>&1; then
    echo "Нужна утилита screen (обычно: yum install screen / apt install screen)." >&2
    exit 1
fi

if [[ ! -x "$SCREEN_MAX_PYTHON" ]]; then
    echo "Не найден интерпретатор: $SCREEN_MAX_PYTHON" >&2
    echo "Создай venv в корне проекта или задай SCREEN_MAX_PYTHON=/path/to/python" >&2
    exit 1
fi

if screen_has_session; then
    if [[ "${1:-}" == "--force" ]]; then
        screen -S "$SCREEN_MAX_SESSION" -X quit 2>/dev/null || true
        sleep 1
    else
        echo "Сессия screen «$SCREEN_MAX_SESSION» уже есть. Останови: ./scripts/screen_max_stop.sh" >&2
        echo "Или перезапусти: ./scripts/screen_max_start.sh --force" >&2
        exit 1
    fi
fi

cd "$SCREEN_MAX_ROOT"

# Не используем bash -lc: на хостинге login shell меняет окружение/кавычки, процесс может не стартовать.
screen -dmS "$SCREEN_MAX_SESSION" \
    env "PYTHONPATH=${SCREEN_MAX_ROOT}" \
    "$SCREEN_MAX_PYTHON" -m app.bot.main

echo "Запущено в screen «$SCREEN_MAX_SESSION». Логи в сессии: ./scripts/screen_max_attach.sh"
screen -ls | grep "$SCREEN_MAX_SESSION" || true
