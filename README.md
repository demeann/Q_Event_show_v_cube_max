# Q CLUB — бот для мессенджера MAX

Зеркало игровой логики репозитория Telegram-бота (`Q_Event_show_v_cube`), с **доставкой сообщений через [Platform API MAX](https://dev.max.ru/docs-api)** (`platform-api.max.ru`).

## Статус переноса (поэтапно)

| Этап | Содержание | Статус |
|------|------------|--------|
| A | Копия домена: `app/services`, `app/db`, `content`, миграции, тесты | готово |
| B | HTTP-клиент MAX, long polling, модели Update | **частично** (см. `app/max_platform/`) |
| C | Замена aiogram: общий контекст сообщений, FSM, callback-кнопки | в работе |
| D | Webhook HTTPS, подписка `POST /subscriptions` | после C |
| E | Рассылки (`broadcast_dispatch`) на `MaxPlatformClient` | после C |

Игровой код (туры, баллы, сидер, админ-выгрузки) **общий по смыслу** с TG-веткой; транспорт **должен** вызывать MAX API вместо `aiogram.Bot`.

## Важно про БД

Рекомендуется **отдельная база** для MAX, чтобы не смешивать пользователей с Telegram.

В схеме пока сохранены имена колонок `telegram_user_id` / `tg_username` — в инстансе MAX в них пишутся **ID и имя пользователя MAX** (это осознанное упрощение без миграции `→ max_user_id`). В выгрузках CSV заголовок останется `telegram_user_id`; трактуйте как «ID пользователя в мессенджере».

## Окружение

- Python 3.11–3.13 (см. `pyproject.toml`)
- MySQL 8+, те же миграции Alembic, что и у TG-проекта
- Токен бота: личный кабинет MAX → Чат-боты → Интеграция → токен

Скопируй `.env.example` в `.env` и задай `MAX_ACCESS_TOKEN` (и параметры БД).

## Быстрый тест API (long polling)

```bash
cd MAX_Q_Event
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # заполни MAX_ACCESS_TOKEN
PYTHONPATH=. python -m app.max_platform.poll_updates
```

Команда делает long poll и печатает сырые `update_type` (разработка событий перед подключением обработчиков).

## Дальше

Подробный чеклист переноса хендлеров и отличий MAX от Telegram — в **`docs/MAX_PORTING.md`**.

Официальная документация: [dev.max.ru](https://dev.max.ru/docs-api) (формат HTML, `inline_keyboard`, события `message_created`, `message_callback`, webhook).

## Лицензия / продукт

Внутренний проект Q CLUB; структура и контент игры совпадают с веткой Telegram.
