#!/usr/bin/env bash
# Показать, запущена ли screen-сессия MAX-бота.

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/screen_max_common.sh"

echo "ROOT=$SCREEN_MAX_ROOT"
echo "SESSION=$SCREEN_MAX_SESSION"
echo "PYTHON=$SCREEN_MAX_PYTHON"
echo

if screen_has_session; then
    echo "Статус: запущена"
    screen -ls | grep "$SCREEN_MAX_SESSION" || true
else
    echo "Статус: не запущена"
fi
