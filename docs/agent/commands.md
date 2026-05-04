# Common Commands

## Запуск и перезапуск

- Запустить бота из корня проекта:
  `venv/bin/python -m app.main`
- Перед перезапуском, если менялась логика:
  `PYTHONPYCACHEPREFIX=/private/tmp/issue-bot-pycache venv/bin/python -m py_compile app/*.py`
- Если бот уже запущен, сначала остановить текущий процесс `python -m app.main`, затем поднять новый из этого проекта.

## Быстрые проверки проекта

- Проверить версию Python в `venv`:
  `venv/bin/python -V`
- Проверить установленные зависимости:
  `pip show aiogram httpx python-dotenv`
- Посмотреть измененные файлы:
  `git status --short`
- Посмотреть последние коммиты:
  `git log --oneline -n 12`

## Поиск по коду и документации

- Найти текст по проекту:
  `rg -n "шаблон_поиска" .`
- Найти файлы:
  `rg --files`
- Открыть рабочий журнал:
  `sed -n '1,220p' docs/WORKLOG.md`
- Открыть roadmap:
  `sed -n '1,260p' ROADMAP.md`
- Открыть архитектуру:
  `sed -n '1,220p' docs/ARCHITECTURE.md`

## Локальная база данных

- Посмотреть список таблиц:
  `sqlite3 data/bot.db ".tables"`
- Посмотреть последние задачи:
  `sqlite3 data/bot.db "SELECT id, status, title, github_issue_url, updated_at FROM tasks ORDER BY id DESC LIMIT 10;"`

## GitHub и backlog

- Если нужно создать issue через GitHub CLI/API, сначала проверить, что задача не дублирует `ROADMAP.md`, `docs/WORKLOG.md` и текущие открытые issues.
- Если issue нельзя создать сразу, подготовить draft в ответе пользователю.
- Для сетевых операций с GitHub помнить, что может потребоваться явное разрешение на команду вне sandbox.

## Практика для этого проекта

- Для поведения бота сначала смотреть `docs/WORKLOG.md`, потом `app/bot.py`, `app/trigger.py`, `app/llm.py`.
- Если проблема в понимании формулировок пользователя, проверять и deterministic-ветки, и LLM-routing.
- После изменения поведения по возможности прогонять живой сценарий в Telegram.
