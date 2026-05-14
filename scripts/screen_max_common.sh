#!/usr/bin/env bash
# Общие переменные для screen-* скриптов MAX-бота. Не запускай напрямую.

set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export SCREEN_MAX_ROOT="${SCREEN_MAX_ROOT:-$(cd "$_SCRIPT_DIR/.." && pwd)}"
export SCREEN_MAX_SESSION="${SCREEN_MAX_SESSION:-qclub-max}"
export SCREEN_MAX_PYTHON="${SCREEN_MAX_PYTHON:-"$SCREEN_MAX_ROOT/.venv/bin/python"}"

screen_has_session() {
    # В выводе: "12345.qclub-max (Detached)" — ищем суффикс .SESSION
    screen -ls 2>/dev/null | grep -qE "[[:digit:]]+\.${SCREEN_MAX_SESSION}([[:space:]]|\$)"
}
