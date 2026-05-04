# Архитектура Issue Bot

## Общий принцип

Бот — это **реактивный агент с жёстким trigger-фильтром**. Он не является полноценным LLM-агентом, читающим весь чат. Он обрабатывает только явно адресованные ему сообщения.
Если задан `ALLOWED_CHAT_IDS`, бот дополнительно игнорирует все чаты, которых нет в белом списке.

```
Telegram Group
      │
      │  (все сообщения)
      ▼
┌─────────────────┐
│  trigger.py     │  ← жёсткий фильтр
│  is_triggered() │
└────────┬────────┘
         │ не для бота → ИГНОР
         │ для бота ↓
┌────────▼────────┐
│   bot.py        │  ← главный обработчик
│  handle_message │
└────────┬────────┘
         │
    ┌────┴────────────────┬────────────────┐
    │                     │                │
    ▼                     ▼                ▼
[новая задача]      [правка preview]   [approve]
    │                     │                │
    ▼                     ▼                ▼
[llm.py]            [llm.py]         [github_client.py]
check_is_issue()    edit_preview()   create_issue()
generate_preview()       │                │
    │                    ▼                ▼
    ▼              [storage.py]     [storage.py]
[formatter.py]    update_task()    mark_created()
format_preview()
    │
    ▼
[storage.py]
create_task()
```

---

## Модули

### `config.py`
Единственный источник конфигурации. Читает `.env` через `python-dotenv`. Падает с ошибкой при старте, если обязательная переменная не задана.

### `trigger.py`
Отвечает на вопрос: "Надо ли обрабатывать это сообщение?"

Правила:
1. Текст содержит `@BOT_USERNAME` → да
2. Первое слово `/task`, `/issue`, `/add` → да
3. Reply на сообщение бота (check по `bot_id`) → да
4. Иначе → нет

Дополнительно определяет тип действия:
- `is_approve(text)` — пользователь подтверждает создание issue
- `is_edit_request(text)` — пользователь просит поправить preview

### `llm.py`
Три функции:
- `check_is_issue(ctx)` → `IssueCheck` — определяет, похоже ли сообщение на задачу
- `generate_preview(ctx)` → `IssuePreview` — формирует структурированный issue
- `edit_preview(body, instruction)` → `IssuePreview` — применяет правку

Все три вызывают один `_call_llm()` через `httpx`. Всегда используется `LLM_MODEL`. Если модель не поддерживает vision — API вернёт ошибку, бот сообщит пользователю.

**Контекст (`MessageContext`):**
```python
@dataclass
class MessageContext:
    text: str               # текст текущего сообщения
    replied_text: str|None  # текст replied message (если есть)
    images_b64: list[str]   # base64-картинки из обоих сообщений
```

### `storage.py`
SQLite через стандартный `sqlite3`. Один файл БД. Таблица `tasks`.

Схема:
| Поле | Описание |
|---|---|
| `source_message_id` | ID сообщения, которое триггернуло бота |
| `reply_message_id` | ID сообщения, на которое ответил пользователь (если было) |
| `preview_message_id` | ID сообщения бота с preview (обновляется при правках) |
| `status` | `preview` → `created` |
| `github_issue_url` | Заполняется после создания issue |

Антидубликат: при создании нового preview проверяем `source_message_id`. Если запись есть — не создаём повторно.

### `github_client.py`
Один метод `create_issue()`. Вызывает `POST /repos/{owner}/{repo}/issues` через GitHub REST API v3. Авторизация через Bearer token.

### `formatter.py`
Два метода:
- `format_preview(preview)` → Markdown для Telegram (с ParseMode.MARKDOWN)
- `format_issue_body(preview)` → Markdown для тела GitHub issue

### `bot.py`
Aiogram Router с единственным `@router.message()` handler. Внутри — диспетчеризация по типу действия. Команды `/start` и `/help` обрабатываются отдельно.

---

## Работа с изображениями

Бот поддерживает два сценария:

**1. Фото в текущем сообщении**
```
User: [📷 скриншот] + "вот баг @bot"
```

**2. Reply на чужое фото**
```
User_A: [📷 макет интерфейса]
User_B: reply → "@bot нужно реализовать этот экран"
```

В обоих случаях `_extract_context()` собирает фото из обоих сообщений и передаёт их в LLM как `image_url` (base64 data URI, формат OpenAI vision API).

---

## Флоу сообщения

```
1. Incoming message
2. trigger.py → is_triggered? (+ is_reply_to_bot?)
   NO  → return (silence)
   YES ↓
3. Voice/audio? → stub reply, return
4. is_approve + reply_to_bot? → _handle_approve()
5. is_edit + reply_to_bot?    → _handle_edit()
6. else                        → _handle_new_preview()

_handle_new_preview():
  1. Anti-dup check (source_message_id)
  2. _extract_context() → text + replied_text + images
  3. llm.check_is_issue() → is_issue?
     NO  → "Похоже, это не задача..."
     YES ↓
  4. llm.generate_preview() → IssuePreview
  5. formatter.format_preview() → Markdown text
  6. bot.reply(preview_text) → get sent.message_id
  7. storage.create_task()

_handle_edit():
  1. get_task_by_preview_msg(replied_msg_id)
  2. llm.edit_preview(current_body, instruction)
  3. bot.reply(new_preview_text) → get new sent.message_id
  4. storage.update_task_preview(new_preview_message_id)

_handle_approve():
  1. get_task_by_preview_msg(replied_msg_id)
  2. status == 'created'? → return existing url
  3. github_client.create_issue()
  4. storage.mark_task_created(url)
  5. bot.reply("Issue создан: <url>")
```

---

## Зависимости

| Пакет | Зачем |
|---|---|
| `aiogram 3` | Telegram Bot framework |
| `httpx` | Async HTTP для LLM и GitHub API |
| `python-dotenv` | Чтение `.env` файла |

Нет ORM, нет тяжёлых фреймворков. SQLite через стандартную библиотеку.

---

## Деплой

Запуск через `systemd`. Бинарник — Python в venv. Логи через `journald`.

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
