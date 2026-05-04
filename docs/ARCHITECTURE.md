# Архитектура Issue Bot

## Общий принцип

Бот — **реактивный агент с жёстким trigger-фильтром**. Не является LLM-агентом, читающим весь чат. Обрабатывает только явно адресованные ему сообщения.

---

## Флоу сообщения

```
Входящее сообщение
      │
      ▼
[trigger.py] — пропускаем только: @упоминание / reply на бота / /task /issue /add
      │ нет → ИГНОР
      │ да
      ▼
Голосовое/аудио? → заглушка-ответ, return

Reply на бота?
  ├─ нет @mention и не /команда → ИГНОР (молча)   ← все действия требуют явного mention
  ├─ is_approve(text) + has_explicit_trigger?  → _handle_approve()
  ├─ is_edit_request(text) + has_explicit_trigger? → _handle_edit()
  └─ иначе → _handle_new_preview()

_handle_new_preview():
  1. In-memory lock (защита от race condition)
  2. Anti-dup: get_task_by_source(chat_id, source_message_id)
  3. _extract_context() → text + replied_text + images_b64
  4. llm.check_is_issue() → is_issue?
     NO  → "Похоже, это не задача..."
     YES → llm.generate_preview() → IssuePreview
  5. formatter.format_preview() → plain text
  6. bot.reply(preview) → sent.message_id
  7. storage.create_task() (UNIQUE constraint защищает от дублей)

_handle_edit():
  1. get_task_by_preview_msg(replied_msg_id)
  2. llm.edit_preview(body, instruction)
  3. bot.reply(new_preview) → new sent.message_id
  4. storage.update_task_preview(new_preview_message_id)

_handle_approve():
  1. get_task_by_preview_msg(replied_msg_id)
  2. status == 'created'? → вернуть ссылку
  3. github_client.create_issue()
  4. storage.mark_task_created(url)
  5. bot.reply("Issue создан: <url>")
```

---

## Триггеры и команды

### Что активирует бота

| Условие | Пример |
|---|---|
| `@BOT_USERNAME` в тексте | `@hermeskimg_bot добавить фичу` |
| Reply на сообщение бота | ответ на превью |
| Команды `/task`, `/issue`, `/add` | `/task исправить баг` |

### Approve (создать issue)

Работает **только** через reply на превью-сообщение бота **с явным @mention**.

Распознаёт: `approve`, `аппрув`, `создавай`, `заводи`, `подтверждаю`, `да`, `ок`, `ok`, `давай`, `го`, `принято`, `подтверждено`, `yes`, `create`  
Нечёткое: убирает пунктуацию, в коротких сообщениях (1-2 слова) ищет ключевые слова.

### Правка preview

Reply на превью **с явным @mention**, начинающийся с: `измени`, `поправь`, `добавь`, `убери`, `переформулируй`, `исправь`, `удали`, `замени`, `сделай`, `напиши`, `уточни`, `расширь`, `сократи`, `перепиши`

---

## Модули

### `config.py`
Единственный источник конфигурации. Читает `.env` через `python-dotenv`. Падает с ошибкой при старте, если обязательная переменная не задана.

Ключевые переменные:
- `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` — основной провайдер
- `LLM_FALLBACK_*` — запасной провайдер (опционально)
- `LLM_TIMEOUT` — таймаут в секундах (по умолчанию 30)
- `ALLOWED_CHAT_IDS` — белый список chat_id через запятую (пусто = без ограничений)

### `trigger.py`
Отвечает на вопрос: "надо ли обрабатывать это сообщение?"  
Определяет тип действия: `is_approve()`, `is_edit_request()`.

### `llm.py`
Три функции: `check_is_issue()`, `generate_preview()`, `edit_preview()`.  
Все вызывают `_call_llm()` → `_do_request()` через `httpx`.  
При ошибке основного провайдера (timeout, 402, 429, 5xx) — автопереключение на `LLM_FALLBACK_*`.  
Логирует модель и провайдер на каждый запрос.

Поддержка изображений: фото передаются как `image_url` (base64 data URI, формат OpenAI vision).

### `storage.py`
SQLite через стандартный `sqlite3`. Таблица `tasks`.  
UNIQUE индекс на `(chat_id, source_message_id)` — гарантирует отсутствие дублей на уровне БД.  
`create_task()` возвращает `None` при конфликте вместо исключения.

### `github_client.py`
`POST /repos/{owner}/{repo}/issues` через GitHub REST API v3.

### `formatter.py`
`format_preview()` — нумерованный список для Telegram (plain text, без ParseMode).  
`format_issue_body()` — Markdown для тела GitHub issue.

### `bot.py`
Один `@router.message()` handler. In-memory set `_processing` защищает от race condition.

---

## Работа с изображениями

**Сценарий 1 — фото напрямую:**
```
User: [📷 скриншот] + "@bot вот баг"
```

**Сценарий 2 — reply на чужое фото:**
```
User_A: [📷 макет интерфейса]
User_B: reply → "@bot нужно реализовать этот экран"
```

`_extract_context()` собирает фото из обоих сообщений, передаёт в LLM как base64 image_url.

---

## Защита от дублей

1. `drop_pending_updates=True` при старте — не обрабатываем накопившиеся апдейты
2. In-memory set `_processing` — блокирует параллельную обработку одного сообщения
3. UNIQUE индекс в БД — последний рубеж, `IntegrityError` обрабатывается мягко

---

## Деплой

Запуск через `systemd`. Логи через `journald`.

```
/opt/issue-bot/
  venv/          ← виртуальное окружение
  app/           ← исходники
  data/bot.db    ← SQLite
  .env           ← секреты (не в git)
```

---

## Будущие расширения

Смотри [ROADMAP.md](../ROADMAP.md).
