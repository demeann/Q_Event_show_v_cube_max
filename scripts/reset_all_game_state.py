"""Полный сброс **игровой** активности для **всех** пользователей.

Удаляет ответы, прогресс по турам и темам, запланированные/завершённые рассылки
и результаты отбора победителей.

**Не трогает:** `users` (регистрация, почта), `rounds`, `round_questions`,
`broadcast_templates`, логи валидации email.

Пример::

    cd MAX_Q_Event && source .venv/bin/activate
    export PYTHONPATH=.
    python -m scripts.reset_all_game_state --yes

Без флага ``--yes`` скрипт только выведет текущие счётчики и выйдет с кодом 1.

Перед боевым запуском с нулевой аудиторией см. ``scripts.prelaunch_clean``.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.services.game_state_reset import count_player_activity_rows, delete_all_player_activity


async def _run(*, do_delete: bool) -> int:
    from app.db.base import dispose_engine, get_session

    try:
        async with get_session() as session:
            before = await count_player_activity_rows(session)

            print("Текущее количество строк:")
            for k, v in before.items():
                print(f"  {k}: {v}")
            total = sum(before.values())
            print(f"  — всего: {total}")

            if not do_delete:
                print(
                    "\nУдаление не выполнялось. Для реального сброса запусти с флагом --yes.",
                    file=sys.stderr,
                )
                return 1

            if total == 0:
                print("\nУже пусто, удалать нечего.")
                return 0

            await delete_all_player_activity(session)
            await session.commit()

            print("\nГотово: игровые данные всех пользователей очищены.")
            return 0
    finally:
        await dispose_engine()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--yes",
        action="store_true",
        help="Подтвердить массовое удаление (обязательно)",
    )
    args = p.parse_args()
    raise SystemExit(asyncio.run(_run(do_delete=args.yes)))


if __name__ == "__main__":
    main()
