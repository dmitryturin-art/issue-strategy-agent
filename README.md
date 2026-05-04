# Issue Bot

Telegram-бот для оформления GitHub Issues из сообщений в группе.

Бот **не читает чат** и **не отвечает на обычные сообщения**. Реагирует только на явные обращения.

---

## Быстрый старт (локально)

```bash
git clone https://github.com/dmitryturin-art/issue-strategy-agent.git
cd issue-strategy-agent

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Заполните .env своими значениями

python -m app.main
```

---

## Заполнение .env

| Переменная | Описание |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Токен бота от [@BotFather](https://t.me/BotFather) |
| `BOT_USERNAME` | Username бота без `@` |
| `ALLOWED_CHAT_IDS` | Разрешённые `chat_id` через запятую. Пусто — без ограничений |
| `LLM_BASE_URL` | Base URL OpenAI-совместимого API |
| `LLM_API_KEY` | API-ключ основного провайдера |
| `LLM_MODEL` | Модель (например `openai/gpt-5.4-mini`) |
| `LLM_FALLBACK_BASE_URL` | Base URL запасного провайдера (опционально) |
| `LLM_FALLBACK_API_KEY` | API-ключ запасного провайдера |
| `LLM_FALLBACK_MODEL` | Модель запасного провайдера (например `openrouter/free`) |
| `LLM_TIMEOUT` | Таймаут LLM в секундах (по умолчанию `30`) |
| `GITHUB_TOKEN` | Personal Access Token с правами `repo` |
| `GITHUB_DEFAULT_REPO` | Репозиторий в формате `owner/repo` |
| `DATABASE_PATH` | Путь к SQLite-файлу (по умолчанию `./data/bot.db`) |

---

## Установка на VPS (Ubuntu/Debian)

### 1. Подготовка сервера

```bash
sudo apt update && sudo apt install -y python3.10 python3.10-venv git
sudo useradd -m -s /bin/bash botuser
sudo mkdir -p /opt/issue-bot
sudo chown botuser:botuser /opt/issue-bot
```

### 2. Клонирование и настройка

```bash
sudo -u botuser git clone https://github.com/dmitryturin-art/issue-strategy-agent.git /opt/issue-bot
cd /opt/issue-bot

sudo -u botuser python3.10 -m venv venv
sudo -u botuser venv/bin/pip install -r requirements.txt

sudo -u botuser cp .env.example .env
sudo -u botuser nano .env
```

### 3. Установка systemd service

```bash
# Отредактируйте User= в issue-bot.service если нужно
sudo cp issue-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable issue-bot
sudo systemctl start issue-bot
```

### 4. Просмотр логов

```bash
sudo journalctl -u issue-bot -f
# последние 100 строк:
sudo journalctl -u issue-bot -n 100
```

### 5. Перезапуск сервиса

```bash
sudo systemctl restart issue-bot
sudo systemctl status issue-bot
```

---

## Использование в группе

### Создание issue

Упомяните бота или используйте команду:

```
@hermeskimg_bot задача: при загрузке файла > 10MB падает 500
```

```
/task добавить фильтрацию по дате в отчётах
```

Или reply на чужое сообщение / скриншот с упоминанием бота.

Бот ответит preview через ~3-5 секунд.

### Правка preview

Reply на сообщение бота с preview **с @mention**:

```
@hermeskimg_bot измени — добавь, что это критический баг
@hermeskimg_bot поправь ожидаемый результат: файлы должны обрабатываться потоково
@hermeskimg_bot убери метку enhancement
@hermeskimg_bot сделай критерии приёмки конкретнее
```

### Подтверждение (approve)

Reply на preview **с @mention**:

```
@hermeskimg_bot approve
```

Также работает: `аппрув`, `создавай`, `заводи`, `да`, `ок`, `давай`, `го`, `подтверждаю`, `yes`

Бот создаст issue в GitHub и пришлёт ссылку.

---

## Команды бота

| Команда | Действие |
|---|---|
| `/task текст` | Создать preview для задачи |
| `/issue текст` | То же |
| `/add текст` | То же |
| `/start`, `/help` | Справка |

---

## Структура проекта

```
app/
  main.py          — точка входа, polling
  config.py        — переменные окружения
  bot.py           — aiogram handlers
  storage.py       — SQLite CRUD
  llm.py           — вызовы LLM (is_issue, preview, edit) + fallback
  github_client.py — создание issue через GitHub REST API
  trigger.py       — фильтр триггеров, approve, edit detection
  formatter.py     — форматирование preview
  project_context.py — контекст репозиториев для LLM
data/
  bot.db           — SQLite (создаётся автоматически)
docs/
  ARCHITECTURE.md  — архитектура
  WORKLOG.md       — журнал разработки
```
