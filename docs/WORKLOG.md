# Worklog

Журнал разработки проекта issue-bot.

---

## 2026-05-04 — Старт проекта / MVP

**Участники:** Dmitry Turin, Claude

### Принятые решения

- Бот реактивный, не читает историю чата
- Жёсткий trigger-фильтр: только упоминание, reply на бота, команды
- Флоу: is_issue check → generate preview → approve → create GitHub issue
- LLM: OpenAI-compatible HTTP API, конфигурируется через `LLM_BASE_URL` + `LLM_API_KEY`
- Fallback-провайдер: `LLM_FALLBACK_*` — автопереключение при ошибках основного
- Изображения: base64 vision в обоих сценариях (прямое фото + reply на чужое фото)
- Голосовые: заглушка, Whisper в ROADMAP
- Язык: всё на русском

### Созданные файлы

`app/` — config, storage, trigger, llm, github_client, formatter, bot, main  
`docs/` — ARCHITECTURE.md, WORKLOG.md  
`README.md`, `ROADMAP.md`, `.env.example`, `issue-bot.service`

---

## 2026-05-04 — Ограничение по chat_id

**Участники:** Dmitry Turin, Codex

### Что сделано
- Добавлена `ALLOWED_CHAT_IDS` — белый список Telegram chat_id через запятую
- Бот молча игнорирует чаты не из списка
- Обновлены `.env.example`, `README.md`, `ARCHITECTURE.md`

---

## 2026-05-04 — Память проекта / контекст репозитория

**Участники:** Dmitry Turin, Codex

### Что сделано
- Создан `app/project_context.py` — реестр профилей проектов
- Краткий `short_context` подмешивается в system prompt при `is_issue`, `generate_preview`, `edit_preview`
- Первый профиль: `dmitryturin-art/pavodok_map`

### Принятые решения
- Не читать полный markdown-файл на каждый LLM-запрос — только короткая сводка
- Lookup по `GITHUB_DEFAULT_REPO`, чтобы позже легко расширить на мультирепо

---

## 2026-05-04 — Отладка и исправление багов после первого запуска

**Участники:** Dmitry Turin, Claude

### Проблемы и причины

| Проблема | Причина | Исправление |
|---|---|---|
| Несколько превью подряд | Бот переобрабатывал старые апдейты при рестарте | `drop_pending_updates=True` при старте |
| Несколько превью подряд | Race condition в async | In-memory set `_processing` |
| Апрув не находил preview | Пользователь апрувил не то превью (следствие дублей) | UNIQUE индекс `(chat_id, source_message_id)` |
| Reply на бота создавал новый preview | Не approved/edit — падало в `_handle_new_preview`, которая подхватывала текст превью из replied_message | Добавлена подсказка вместо fallthrough |
| Модель не видна в логах | Не логировалась | `logger.info("LLM запрос: модель=...")` |
| Формат превью | Эмодзи, Markdown, разметка | Нумерованный список, plain text |
| `openrouter/free` заменён без разрешения | Ошибка — алиас валидный | Возврат к `openrouter/free` |

### Итоговая конфигурация (локальный запуск)
- Основная модель: `openai/gpt-5.4-mini` @ wormsoft (~2.6с)
- Fallback: `openrouter/free` → `google/gemma-4-26b:free`
- Таймаут: 30с (`LLM_TIMEOUT`)

### Первый успешный issue
- Создан через бота в группе, approve сработал с reply без @mention

---

## 2026-05-04 — Строгий @mention для всех действий

**Участники:** Dmitry Turin, Claude

### Что сделано
- `bot.py`: approve и edit через reply на preview теперь тоже требуют явного `@mention` или `/команды`
- Reply на preview без @mention — молча игнорируется (раньше показывалась подсказка)
- Обновлены README, ARCHITECTURE.md

### Принятые решения
- Любое взаимодействие с ботом — только через явный @mention. Без исключений.
- Убрана подсказка при непонятной команде без mention (бот не должен реагировать вообще)

---

## 2026-05-04 — Управление существующими issues

**Участники:** Dmitry Turin, Claude

### Что сделано
- `github_client.py`: добавлены `get_issue`, `add_comment`, `close_issue`, `reopen_issue`, `update_issue`, `search_issues`
- `llm.py`: добавлены `ActionIntent`, `classify_action`, `generate_update_patch`
- `trigger.py`: добавлены `has_issue_action`, `extract_issue_number`, `extract_state_filter`
- `bot.py`: новые handlers + dispatch через LLM-классификацию намерений

### Принятые решения
- Все команды понимаются через LLM — нет жёсткого парсинга, широкий диапазон формулировок
- Быстрый путь: если в тексте нет ключевых слов управления issue → сразу `new_preview` (без LLM-классификации)
- Поиск без указания статуса → бот уточняет: открытые / закрытые / все
- При закрытии с текстом — сначала добавляется комментарий, потом issue закрывается

### Новые возможности
| Действие | Пример |
|---|---|
| Комментарий | `@bot прокомментируй #42: всё готово` |
| Закрытие | `@bot закрой #42 — не актуально` |
| Переоткрытие | `@bot переоткрой #15` |
| Обновление | `@bot обнови #7: поменяй метку на bug` |
| Поиск | `@bot найди открытые issue про авторизацию` |

---

## Шаблон для следующих записей

```
## YYYY-MM-DD — [тема]

**Участники:** ...

### Что сделано
- ...

### Принятые решения
- ...

### Проблемы / баги
- ...

### Следующий шаг
- ...
```
