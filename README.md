# Issue Bot

Telegram-бот для оформления GitHub Issues из сообщений в группе.

Бот **не читает чат** и **не отвечает на обычные сообщения**. Он реагирует только если:
- сообщение содержит `@bot_username`
- сообщение — reply на сообщение бота
- сообщение начинается с `/task`, `/issue`, `/add`

---

## Быстрый старт (локально)

```bash
git clone https://github.com/your/issue-bot.git
cd issue-bot

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
| `BOT_USERNAME` | Username бота без `@` (например `issue_helper_bot`) |
| `LLM_BASE_URL` | Base URL OpenAI-совместимого API (OpenRouter, OpenAI, свой) |
| `LLM_API_KEY` | API-ключ провайдера |
| `LLM_MODEL` | Модель по умолчанию (например `meta-llama/llama-3.1-8b-instruct:free`) |
| `LLM_VISION_MODEL` | Модель для обработки изображений (например `google/gemini-flash-1.5`) |
| `GITHUB_TOKEN` | Personal Access Token GitHub с правами `repo` |
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
sudo -u botuser git clone https://github.com/your/issue-bot.git /opt/issue-bot
cd /opt/issue-bot

sudo -u botuser python3.10 -m venv venv
sudo -u botuser venv/bin/pip install -r requirements.txt

sudo -u botuser cp .env.example .env
sudo -u botuser nano .env  # заполнить переменные
```

### 3. Установка systemd service

```bash
# Отредактируйте User= в issue-bot.service если нужно (по умолчанию ubuntu)
sudo cp issue-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable issue-bot
sudo systemctl start issue-bot
```

### 4. Просмотр логов

```bash
sudo journalctl -u issue-bot -f
# или последние 100 строк:
sudo journalctl -u issue-bot -n 100
```

### 5. Перезапуск сервиса

```bash
sudo systemctl restart issue-bot
# статус:
sudo systemctl status issue-bot
```

---

## Использование в группе

### Создание issue

Упомяните бота в любом сообщении или reply на чужое сообщение:

```
Нужно добавить фильтрацию по дате в отчётах @issue_bot
```

или

```
@issue_bot задача: при загрузке файла > 10MB падает 500
```

или reply на сообщение/скриншот с `@issue_bot`.

Бот проверит, похоже ли это на задачу, и пришлёт preview.

### Правка preview

Ответьте reply на сообщение бота с preview:

```
измени — добавь, что это критический баг
поправь ожидаемый результат: файлы должны обрабатываться потоково
убери метку enhancement
```

### Подтверждение

Ответьте reply на preview:

```
approve
```

или: `создавай`, `подтверждаю`, `аппрув`, `да, заводи`

Бот создаст issue в GitHub и пришлёт ссылку.

---

## Структура проекта

```
app/
  main.py          — точка входа, polling
  config.py        — переменные окружения
  bot.py           — aiogram handlers
  storage.py       — SQLite CRUD
  llm.py           — вызовы LLM (is_issue, preview, edit)
  github_client.py — создание issue через GitHub REST API
  trigger.py       — фильтр: кому отвечать
  formatter.py     — Markdown-форматирование preview
data/
  bot.db           — SQLite база (создаётся автоматически)
docs/
  ARCHITECTURE.md  — архитектура и принципы работы
  WORKLOG.md       — журнал разработки
```
