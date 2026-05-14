#!/usr/bin/env bash
# Подключиться к screen с ботом (выход без убийства: Ctrl+A, затем D).

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/screen_max_common.sh"

if ! screen_has_session; then
    echo "Сессия «$SCREEN_MAX_SESSION» не запущена. Старт: ./scripts/screen_max_start.sh" >&2
    exit 1
fi

exec screen -r "$SCREEN_MAX_SESSION"
