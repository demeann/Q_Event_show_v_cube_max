#!/usr/bin/env bash
# Подключиться к screen с ботом (выход без убийства: Ctrl+A, затем D).

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/screen_max_common.sh"

if ! screen -r "$SCREEN_MAX_SESSION"; then
    echo "Не удалось подключиться к «$SCREEN_MAX_SESSION». Текущий список screen:" >&2
    screen -ls >&2 || true
    echo "Если сессии нет — запуск: ./scripts/screen_max_start.sh" >&2
    exit 1
fi
