#!/usr/bin/env bash
# Остановка screen-сессии MAX-бота.

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/screen_max_common.sh"

if screen_has_session; then
    screen -S "$SCREEN_MAX_SESSION" -X quit
    echo "Сессия «$SCREEN_MAX_SESSION» остановлена."
else
    echo "Сессия «$SCREEN_MAX_SESSION» не найдена."
fi
