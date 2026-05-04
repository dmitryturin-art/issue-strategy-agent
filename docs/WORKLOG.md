# Worklog

Журнал разработки проекта issue-bot.

---

## 2026-05-04 — Старт проекта / MVP

**Участники:** Dmitry Turin, Claude (AI assistant)

### Принятые решения

**Архитектура бота:**
- Бот — реактивный, не читает историю чата
- Жёсткий trigger-фильтр: только упоминание, reply на бота, команды
- Флоу: is_issue check → generate preview → approve → create GitHub issue
- Правки preview через reply с ключевыми словами (`измени`, `поправь` и др.)

**LLM:**
- OpenAI-compatible HTTP API (OpenRouter по умолчанию)
- Конфигурируется через `LLM_BASE_URL` + `LLM_API_KEY` — можно подключить любой провайдер
- Отдельная vision-модель (`LLM_VISION_MODEL`) для обработки изображений
- Fallback: если `LLM_VISION_MODEL` не задана — используется `LLM_MODEL`

**Изображения:**
- Реализованы в MVP: поддержка фото в прямых сообщениях и в replied message
- Передаются в LLM как base64 data URI (формат OpenAI vision)
- Оба сценария: фото от пользователя + reply на чужое фото со скриншотом

**Голосовые:**
- Заглушка в MVP, Whisper-интеграция — в ROADMAP v1.1

**Мультирепозиторий:**
- В MVP — один репозиторий из `.env`
- Мультирепо через ключевые слова/название проекта — ROADMAP v1.2

**Язык:**
- Все ответы бота и содержимое preview — на русском
- GitHub issue body — на русском

**Деплой:**
- systemd service, без Docker
- Ручной перенос на VPS (автодеплой — в планах)

### Созданные файлы

| Файл | Описание |
|---|---|
| `app/config.py` | Загрузка и валидация env переменных |
| `app/storage.py` | SQLite CRUD: tasks table |
| `app/trigger.py` | Фильтр триггеров, определение approve/edit |
| `app/llm.py` | is_issue check, generate_preview, edit_preview |
| `app/github_client.py` | GitHub REST API: create issue |
| `app/formatter.py` | Markdown для Telegram + GitHub issue body |
| `app/bot.py` | aiogram handlers: new/edit/approve |
| `app/main.py` | Точка входа, init DB, polling |
| `requirements.txt` | aiogram, httpx, python-dotenv |
| `.env.example` | Шаблон переменных окружения |
| `issue-bot.service` | systemd unit file |
| `README.md` | Установка, настройка, использование |
| `ROADMAP.md` | Планы на будущие версии |
| `docs/ARCHITECTURE.md` | Архитектурная документация |
| `docs/WORKLOG.md` | Этот файл |

### Открытые вопросы / TODO до первого запуска

- [ ] Протестировать с реальным Telegram-ботом и группой
- [ ] Проверить парсинг JSON из разных LLM-моделей (особенно free-tier)
- [ ] Убедиться, что `ParseMode.MARKDOWN` в aiogram 3 корректно обрабатывает спецсимволы в preview
- [ ] Проверить загрузку и передачу изображений через OpenRouter vision
- [ ] Создать GitHub Personal Access Token с нужными правами

---

## 2026-05-04 — Ограничение по chat_id и рабочий процесс

**Участники:** Dmitry Turin, Codex (AI assistant)

### Что сделано
- Добавлена env-переменная `ALLOWED_CHAT_IDS` для ограничения бота по списку Telegram chat ID
- Бот теперь молча игнорирует сообщения из чатов, которых нет в белом списке
- Обновлены `.env.example`, `README.md` и `ARCHITECTURE.md`
- Зафиксирован рабочий процесс: перед правками создавать git-чекпоинт с комментарием на русском

### Принятые решения
- Не создавать второй `worklog`-файл, а продолжать вести существующий `docs/WORKLOG.md`
- Формат `ALLOWED_CHAT_IDS`: список числовых `chat_id` через запятую
- Если `ALLOWED_CHAT_IDS` пустой, бот работает как раньше, без ограничения по чатам

### Следующий шаг
- Вписать реальный `chat_id` нужной группы в `.env`
- При желании добавить отдельную команду или лог для быстрого определения `chat_id` группы

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
