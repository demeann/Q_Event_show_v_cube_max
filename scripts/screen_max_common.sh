#!/usr/bin/env bash
# Общие переменные для screen-* скриптов MAX-бота. Не запускай напрямую.

set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export SCREEN_MAX_ROOT="${SCREEN_MAX_ROOT:-$(cd "$_SCRIPT_DIR/.." && pwd)}"
export SCREEN_MAX_SESSION="${SCREEN_MAX_SESSION:-qclub-max}"
export SCREEN_MAX_PYTHON="${SCREEN_MAX_PYTHON:-"$SCREEN_MAX_ROOT/.venv/bin/python"}"

screen_has_session() {
    # 1) Весь pipeline внутри «if …; then»: при set -euo pipefail в вызывающем скрипте
    #    один только «grep не нашёл» не должен ронять весь скрипт до return из функции
    #    (иначе возможны расхождения между ./screen_max_status.sh и ./screen_max_attach.sh).
    # 2) 2>&1: часть сборок пишет список сокетов в stderr.
    # 3) grep -F: в имени «qclub-max» дефис не ломает шаблон (в grep -E «b-m» — диапазон).
    if screen -ls 2>&1 | grep -qF ".${SCREEN_MAX_SESSION}"; then
        return 0
    fi
    return 1
}
