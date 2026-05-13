# Перенос с Telegram (aiogram) на MAX

## Карта соответствий

| Telegram / aiogram | MAX Platform API |
|--------------------|------------------|
| `BOT_TOKEN` | `Authorization: <access_token>` |
| `getUpdates` / webhook | `GET /updates` (long poll) или webhook из `POST /subscriptions` |
| ЛС: `chat_id` | исходящие в ЛС: `POST /messages?chat_id=` (берём из `Update.chat_id`); `user_id` в query — для адресации по пользователю (см. доки) |
| `sendMessage` + `reply_markup` | `POST /messages` + `attachments[].type=inline_keyboard` |
| `callback_query` | событие `message_callback`; в кнопке `type: callback`, строка `payload` |
| HTML | поле `format: "html"` в теле сообщения |
| `answerCallbackQuery` | уточнить в доках MAX для подтверждения нажатия (при необходимости — пустой `POST` или отдельный метод) |
| Загрузка фото/файлов | вложения в `POST /messages` (см. раздел вложений в API) |
| `protect_content` | нет прямого аналога; уточнить актуальные ограничения MAX |

## Что не трогать при переносе

- `app/services/*` (кроме `broadcast_dispatch.py` — туда передаётся клиент отправки)
- `app/db/*` (до отдельного решения о переименовании колонок)
- `content/*.yaml`, `scripts/seed_content.py`
- Правила игры, сегменты рассылок, ранжирование победителей

## Что переписать

1. **`app/bot/main.py`** — убрать aiogram `Bot`/`Dispatcher`; запуск long poll или aiohttp webhook.
2. **Все `app/bot/handlers/*.py`** — заменить:
   - `Message` / `CallbackQuery` на тонкие типы-обёртки с `from_user.id`, `.text`, `.answer()`, `.answer_photo()` → вызовы `MaxPlatformClient`.
   - `@router.message(CommandStart())` — разбор текста `/start` и `bot_started` (см. объект `Update`).
   - `FSMContext` — свое хранилище состояний (память/Redis) по ключу `max_user_id`.
   - `CallbackData.pack()/unpack()` — оставить ту же строковую схему в `payload` кнопок `callback`.
3. **`app/bot/middlewares/access.py`** — фильтрация событий до логики доступа.
4. **`app/services/broadcast_dispatch.py`** — интерфейс «отправить сообщение пользователю» без aiogram.
5. **`app/bot/intro_media.py`** — отправка локального файла через API вложений MAX.
6. **Тексты onboarding** — для MAX подсказка по приглашению: `https://max.ru/<ник>?start=<token>` (см. onboarding_core).

## Рекомендуемый порядок работ

1. Реализовать `MaxPlatformClient.send_message_user(user_id, text, format, buttons)`.
2. Один вертикальный срез: `/start` + ввод email + `/play` + тур 1 (без фото или с фото).
3. Тур 2 и 3 + админка + рассылки.
4. Webhook на проде, отключить long poll.

## Репозиторий

Локально проект лежит в `MAX_Q_Event` (в этом workspace — под `2bd_bot_2/MAX_Q_Event`). Перенеси каталог на Mac в нужное место и подключи remote:

```bash
cd MAX_Q_Event
git init
git add .
git commit -m "Initial MAX mirror scaffold"
git remote add origin <url>
git push -u origin main
```
