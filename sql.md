# SQL-шпаргалки (MySQL, Q CLUB)

Подставь имя базы или выполни после `USE твоя_база;`.  
Время в колонках — **UTC без таймзоны** (как в ORM). Коды туров: `R1`, `R2`, `R3`.  
Статусы прогресса тура: `NOT_STARTED`, `IN_PROGRESS`, `FINISHED`.

---

## Сервер: шелл и SSH (без лишних «broken pipe»)

Сессия часто рвётся по таймауту на NAT/роутере. Держи соединение «живым» с клиента:

```bash
ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=4 root@IP_ИЛИ_HOSTNAME
```

- **`ServerAliveInterval=30`** — раз в 30 с клиент шлёт пустой пакет; сервер не считает сессию мёртвой.
- **`ServerAliveCountMax=4`** — сколько подряд отсутствия ответа до разрыва (при необходимости увеличь).

Чтобы не печатать опции каждый раз, на **своём** Mac добавь в `~/.ssh/config`:

```
Host qclub-vps
    HostName IP_ИЛИ_HOSTNAME
    User root
    ServerAliveInterval 30
    ServerAliveCountMax 4
```

Дальше: `ssh qclub-vps`.

**Частые команды в каталоге проекта** (пути подставь под свой деплой):

```bash
cd ~/q_event_show_v_cube/Q_Event_show_v_cube
source .venv/bin/activate
sudo systemctl restart qclub-bot.service
sudo systemctl status qclub-bot.service --no-pager
PYTHONPATH=. python -m scripts.seed_content
```

MySQL с сервера (учётка как в `.env` приложения):

```bash
mysql -u qclub_bot -p -h 127.0.0.1 ИМЯ_БАЗЫ
# в консоли mysql: USE ИМЯ_БАЗЫ;
```

---

## MAX: колонка `users.max_chat_id` (если пропущена миграция 0005)

Ошибка: `Unknown column 'users.max_chat_id' in 'field list'`. Предпочтительно: из каталога проекта `PYTHONPATH=. alembic upgrade head`. Или один раз вручную:

```sql
USE u3412349_default;
ALTER TABLE users ADD COLUMN max_chat_id BIGINT NULL
  COMMENT 'MAX: chat_id диалога для POST /messages'
  AFTER telegram_user_id;
```

После ручного `ALTER` приведи `alembic_version` в соответствие с репозиторием (иначе следующий `upgrade` может упасть). Надёжнее всегда применять миграции из репозитория.

---

## База и туры

```sql
-- Текущее время MySQL (сверка с приложением)
SELECT NOW() AS db_now_utc_session, UTC_TIMESTAMP() AS db_utc;

-- Окна туров
SELECT id, code, name, status, starts_at, ends_at
FROM rounds
ORDER BY starts_at;
```

---

## Пользователи: базовый срез

```sql
-- Все пользователи: регистрация, верификация, блок
SELECT
  id,
  telegram_user_id,
  tg_username,
  email,
  email_domain,
  email_verified_at,
  is_admin,
  is_blocked,
  created_at,
  updated_at
FROM users
ORDER BY id;

-- Только с подтверждённым email (как типичный участник)
SELECT id, telegram_user_id, email, email_verified_at
FROM users
WHERE email_verified_at IS NOT NULL AND is_blocked = 0
ORDER BY id;

-- Заблокированные
SELECT id, telegram_user_id, email, is_blocked
FROM users
WHERE is_blocked = 1;
```

---

## Прогресс по турам (длинный формат)

```sql
SELECT
  u.id AS user_id,
  u.telegram_user_id,
  u.email,
  r.code AS round_code,
  urp.status AS progress_status,
  urp.total_score,
  urp.started_at,
  urp.finished_at,
  urp.last_answer_at
FROM user_round_progress urp
JOIN users u ON u.id = urp.user_id
JOIN rounds r ON r.id = urp.round_id
ORDER BY u.id, r.starts_at;
```

---

## Завершили тур / не начинали (по выбранному коду тура)

```sql
-- Замени 'R1' на R2 / R3
SELECT
  u.id,
  u.telegram_user_id,
  u.email,
  urp.status,
  urp.total_score,
  urp.finished_at
FROM users u
LEFT JOIN rounds r ON r.code = 'R2'
LEFT JOIN user_round_progress urp
  ON urp.user_id = u.id AND urp.round_id = r.id
WHERE u.is_blocked = 0
  AND (u.email_verified_at IS NOT NULL OR u.is_admin = 1)
ORDER BY u.id;
```

```sql
-- Кто завершил тур R1
SELECT u.id, u.telegram_user_id, u.email, urp.total_score, urp.finished_at
FROM user_round_progress urp
JOIN users u ON u.id = urp.user_id
JOIN rounds r ON r.id = urp.round_id AND r.code = 'R1'
WHERE urp.status = 'FINISHED'
ORDER BY urp.total_score DESC, u.id;
```

```sql
-- Кто eligible, но нет строки прогресса по R1 (ещё не трогали тур)
SELECT u.id, u.telegram_user_id, u.email
FROM users u
LEFT JOIN rounds r ON r.code = 'R1'
LEFT JOIN user_round_progress urp ON urp.user_id = u.id AND urp.round_id = r.id
WHERE u.is_blocked = 0
  AND (u.email_verified_at IS NOT NULL OR u.is_admin = 1)
  AND urp.id IS NULL
ORDER BY u.id;
```

---

## Баллы и таблица лидеров по туру

```sql
SELECT
  u.id,
  u.telegram_user_id,
  u.email,
  urp.total_score,
  urp.status
FROM user_round_progress urp
JOIN users u ON u.id = urp.user_id
JOIN rounds r ON r.id = urp.round_id AND r.code = 'R1'
WHERE u.is_blocked = 0
ORDER BY urp.total_score DESC, u.id;
```

---

## Ответы: успех / ошибки по пользователю и туру

```sql
-- Сводка по ответам (кол-во верных / неверных) за тур
SELECT
  u.id AS user_id,
  u.telegram_user_id,
  r.code AS round_code,
  SUM(ua.is_correct = 1) AS correct_cnt,
  SUM(ua.is_correct = 0) AS wrong_cnt,
  COUNT(*) AS answers_total,
  SUM(ua.points_awarded) AS points_from_answers
FROM user_answers ua
JOIN users u ON u.id = ua.user_id
JOIN rounds r ON r.id = ua.round_id
GROUP BY u.id, u.telegram_user_id, r.code
ORDER BY r.code, u.id;
```

```sql
-- Детально: каждый ответ пользователя UserId=1 в туре R2
SELECT
  ua.id,
  rq.code AS question_code,
  rq.order_index,
  ua.selected_option,
  ua.is_correct,
  ua.points_awarded,
  ua.answered_at
FROM user_answers ua
JOIN rounds r ON r.id = ua.round_id AND r.code = 'R2'
JOIN round_questions rq ON rq.id = ua.question_id
WHERE ua.user_id = 1
ORDER BY rq.order_index;
```

---

## Активность в базе (последние ответы и «кто недавно играл»)

```sql
-- Последние 80 ответов по всем турам (кто, какой тур, вопрос, верно или нет, когда)
SELECT
  ua.answered_at,
  u.telegram_user_id,
  u.email,
  r.code AS round_code,
  rq.code AS question_code,
  ua.is_correct,
  ua.points_awarded
FROM user_answers ua
JOIN users u ON u.id = ua.user_id
JOIN rounds r ON r.id = ua.round_id
JOIN round_questions rq ON rq.id = ua.question_id
ORDER BY ua.answered_at DESC
LIMIT 80;
```

```sql
-- Кто обновлял прогресс недавно (по last_answer_at в турах)
SELECT
  urp.last_answer_at,
  u.telegram_user_id,
  r.code,
  urp.status,
  urp.total_score
FROM user_round_progress urp
JOIN users u ON u.id = urp.user_id
JOIN rounds r ON r.id = urp.round_id
WHERE urp.last_answer_at IS NOT NULL
ORDER BY urp.last_answer_at DESC
LIMIT 50;
```

```sql
-- Сводка за сегодня по UTC: сколько ответов (подставь UTC-дату)
SELECT
  DATE(ua.answered_at) AS day_utc,
  COUNT(*) AS answers_cnt,
  SUM(ua.is_correct = 1) AS correct_cnt
FROM user_answers ua
WHERE ua.answered_at >= UTC_DATE()
GROUP BY DATE(ua.answered_at);
```

---

## Вопросы: сколько всего / сколько отвечено (по туру)

```sql
-- Число вопросов в туре и число ответов у пользователя (замени user_id)
SELECT
  r.code,
  (SELECT COUNT(*) FROM round_questions rq WHERE rq.round_id = r.id) AS questions_in_round,
  COUNT(DISTINCT ua.question_id) AS user_answered
FROM rounds r
LEFT JOIN user_answers ua ON ua.round_id = r.id AND ua.user_id = 1
WHERE r.code = 'R1'
GROUP BY r.id, r.code;
```

---

## Тур 2: темы (`user_topic_progress`)

```sql
SELECT
  u.id AS user_id,
  r.code AS round_code,
  utp.topic_code,
  utp.status,
  utp.score
FROM user_topic_progress utp
JOIN users u ON u.id = utp.user_id
JOIN rounds r ON r.id = utp.round_id
ORDER BY u.id, r.code, utp.topic_code;
```

---

## Победители

```sql
-- Есть ли отбор по турам
SELECT r.code, ws.id AS selection_id, ws.winners_count, ws.executed_at
FROM winner_selections ws
JOIN rounds r ON r.id = ws.round_id
ORDER BY r.starts_at;

-- Список победителей тура R1
SELECT
  w.position,
  u.telegram_user_id,
  u.email
FROM winners w
JOIN winner_selections ws ON ws.id = w.winner_selection_id
JOIN rounds r ON r.id = ws.round_id AND r.code = 'R1'
JOIN users u ON u.id = w.user_id
ORDER BY w.position;
```

---

## Рассылки

```sql
-- Запуски рассылок
SELECT id, template_code, segment_code, scheduled_at, status, total, sent, failed, started_at, finished_at
FROM broadcasts
ORDER BY scheduled_at DESC
LIMIT 50;

-- Получатели одной рассылки (замени broadcast_id)
SELECT
  user_id,
  status,
  sent_at,
  error
FROM broadcast_recipients
WHERE broadcast_id = 1
ORDER BY user_id;
```

---

## Текущий «активный» тур по времени (как в приложении)

Совпадение окна: `starts_at <= NOW_UTC` и `ends_at >= NOW_UTC`. В MySQL подставь то же «сейчас», что считает бот (UTC naive), или для ручной проверки:

```sql
SELECT id, code, name, starts_at, ends_at
FROM rounds
WHERE starts_at <= UTC_TIMESTAMP()
  AND ends_at >= UTC_TIMESTAMP()
ORDER BY starts_at
LIMIT 1;
```

(Если сессия MySQL не в UTC, для строгого совпадения с приложением лучше подставить конкретное время, которое пишет бот.)

---

## Полный сброс игровых данных для **всех** пользователей (осторожно)

Стирает ответы, прогресс по турам/темам, очереди и историю **рассылок** (`broadcasts` / `broadcast_recipients`), **отборы победителей** (`winner_selections` и связанные `winners`).

**Не удаляет:** строки `users`, туры `rounds`, вопросы `round_questions`, шаблоны `broadcast_templates`, логи `email_validation_log`.

**Предпочтительно с сервера** (одна транзакция, счётчики до/после, без `--yes` только просмотр):

```bash
cd ~/q_event_show_v_cube/Q_Event_show_v_cube && source .venv/bin/activate
export PYTHONPATH=.
python -m scripts.reset_all_game_state          # только статистика таблиц
python -m scripts.reset_all_game_state --yes    # реальное удаление
```

Вручную в MySQL (порядок важен из‑за внешних ключей; строки `winners` уходят каскадом при удалении `winner_selections`, получатели рассылок — при удалении `broadcasts`, если в БД так настроен CASCADE):

```sql
-- Сделай бэкап или хотя бы SELECT COUNT(*) по таблицам ниже.
START TRANSACTION;

DELETE FROM broadcast_recipients;
DELETE FROM broadcasts;
DELETE FROM winner_selections;
DELETE FROM user_answers;
DELETE FROM user_topic_progress;
DELETE FROM user_round_progress;

COMMIT;
-- При сомнениях: ROLLBACK;
```

После сброса планировщик снова создаст рассылки по расписанию; пользователям не нужно заново регистрироваться, если не трогал `users`.

---

## Очистка прогресса одного пользователя (осторожно)

**Имеется в виду игровые данные** (ответы, прогресс, победители по этому `user_id`). Строка в `users`, email и рассылки **не** удаляются — человек остаётся зарегистрированным.

Сначала проверь `user_id` / `telegram_user_id`, затем удаляй. Для **одного тура** — в порядке: ответы → темы Тур 2 → прогресс тура.

### Все туры сразу (как логика `reset_all_game_progress_for_user` в приложении)

Подходит для полного «обнулить прохождение» тестового аккаунта:

```sql
-- Замени 123456789 на реальный telegram_user_id из Telegram
SET @uid := (SELECT id FROM users WHERE telegram_user_id = 123456789 LIMIT 1);

SELECT @uid AS user_id_check;  -- если NULL — пользователя нет, DELETE не выполняй

DELETE FROM user_answers WHERE user_id = @uid;
DELETE FROM user_topic_progress WHERE user_id = @uid;
DELETE FROM user_round_progress WHERE user_id = @uid;
DELETE FROM winners WHERE user_id = @uid;
```

### Снова пройти `/start` с подтверждением почты (только для теста)

Если нужно заново получить код на email **без смены аккаунта**:

```sql
SET @uid := 2;  -- users.id

UPDATE users
SET email_verified_at = NULL
WHERE id = @uid;
```

Не делай это на бою без понимания последствий: человек снова попадёт в сегмент «нужна верификация».

---

### По `telegram_user_id` — сброс только одного тура (пример: R2)

```sql
-- Проверка
SELECT id, telegram_user_id, email FROM users WHERE telegram_user_id = 296537944;
SELECT id, code FROM rounds WHERE code = 'R2';

SET @uid = (SELECT id FROM users WHERE telegram_user_id = 296537944 LIMIT 1);
SET @rid = (SELECT id FROM rounds WHERE code = 'R2' LIMIT 1);
SELECT @uid AS user_id, @rid AS round2_id;

DELETE FROM user_answers WHERE user_id = @uid AND round_id = @rid;
DELETE FROM user_topic_progress WHERE user_id = @uid AND round_id = @rid;
DELETE FROM user_round_progress WHERE user_id = @uid AND round_id = @rid;
```

Если `@uid` или `@rid` оказались `NULL`, `DELETE` затронет 0 строк — не удаляй ничего вручную без проверки.

### Общий шаблон по числовому `user_id`

```sql
SET @u := 1;  -- users.id
SET @rid := (SELECT id FROM rounds WHERE code = 'R1' LIMIT 1);

DELETE FROM user_answers WHERE user_id = @u AND round_id = @rid;
DELETE FROM user_topic_progress WHERE user_id = @u AND round_id = @rid;
DELETE FROM user_round_progress WHERE user_id = @u AND round_id = @rid;
```

Для **R1** и **R3** блок с `user_topic_progress` безопасен (просто удалит 0 строк). Для **R2** он обязателен.
