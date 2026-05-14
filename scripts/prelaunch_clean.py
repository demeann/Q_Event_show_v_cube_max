"""Очистка БД **перед боевым запуском** (после тестов на той же базе, инстанс MAX).

По умолчанию делает то же, что ``reset_all_game_state --yes``: снимает ответы,
прогресс, рассылки и победителей. **Пользователей не трогает.**

Дополнительно (только с ``--yes``):

* ``--purge-users`` — удалить **всех** из ``users`` и строки ``email_validation_log``
  (чистый старт регистраций). Туры, вопросы и шаблоны рассылок не удаляются.

После очистки на сервере обычно: ``python -m scripts.seed_content`` и перезапуск процесса.

Пример::

    cd MAX_Q_Event && source .venv/bin/activate
    export PYTHONPATH=.
    python -m scripts.prelaunch_clean --yes --purge-users
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import delete, func, select

from app.services.game_state_reset import count_player_activity_rows, delete_all_player_activity


async def _run(*, do_delete: bool, purge_users: bool) -> int:
    from app.db.base import dispose_engine, get_session
    from app.db.models import EmailValidationLog, User

    try:
        async with get_session() as session:
            pa = await count_player_activity_rows(session)
            n_users = int(
                await session.scalar(select(func.count()).select_from(User)) or 0
            )
            n_audit = int(
                await session.scalar(select(func.count()).select_from(EmailValidationLog))
                or 0
            )

            print("Сейчас в БД (релевантно сбросу):")
            for k, v in pa.items():
                print(f"  {k}: {v}")
            print(f"  users: {n_users}")
            print(f"  email_validation_log: {n_audit}")

            if not do_delete:
                print(
                    "\nНичего не удалено. Запусти с ``--yes`` (и при необходимости "
                    "``--purge-users``).",
                    file=sys.stderr,
                )
                return 1

            await delete_all_player_activity(session)

            if purge_users:
                await session.execute(delete(EmailValidationLog))
                await session.execute(delete(User))
                print("\nУдалены все пользователи и audit email_validation_log.")

            await session.commit()
            print("\nГотово: база подготовлена к запуску.")
            if not purge_users:
                print("(Пользователи сохранены. Для полного обнуления — ``--purge-users``.)")
            return 0
    finally:
        await dispose_engine()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--yes",
        action="store_true",
        help="Подтвердить удаление (обязательно)",
    )
    p.add_argument(
        "--purge-users",
        action="store_true",
        help="После сброса активности удалить всех users и email_validation_log",
    )
    args = p.parse_args()
    if args.purge_users and not args.yes:
        print("``--purge-users`` требует ``--yes``.", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(asyncio.run(_run(do_delete=args.yes, purge_users=args.purge_users)))


if __name__ == "__main__":
    main()
