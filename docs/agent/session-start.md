# Session Start

## Что открыть в новой сессии за 30 секунд

1. `AGENTS.md` — короткий индекс правил проекта.
2. `docs/agent/runtime.md` — как запускать проект и в каком окружении он живет.
3. `docs/agent/workflow.md` — стандартный рабочий цикл.
4. `docs/WORKLOG.md` — что менялось недавно.
5. `ROADMAP.md` — куда проект движется и что уже запланировано.

## Что быстро вспомнить

- Общение с пользователем и все user-facing тексты по умолчанию только на русском.
- Бот обычно запущен локально, точка входа:
  `venv/bin/python -m app.main`
- После изменений в логике сначала полезно прогнать:
  `PYTHONPYCACHEPREFIX=/private/tmp/issue-bot-pycache venv/bin/python -m py_compile app/*.py`
- Если задача про поведение бота, после правок нужен живой smoke-check в Telegram.

## Если задача уже понятна по типу

- Перезапуск и быстрая проверка: `.codex/skills/bot-restart-smoke-check/`
- Разбор обращения к боту и выбор нужного действия: `.codex/skills/issue-triage/`
- Диагностика неверного роутинга: `.codex/skills/bot-debug-routing/`
- Подготовка backlog item / draft issue: `.codex/skills/github-followup-draft/`
