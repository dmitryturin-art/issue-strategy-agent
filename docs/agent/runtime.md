# Runtime Memory

## Локальное окружение

- Корень проекта: `/Users/dmitrijturin/VibeCoding/issue-strategy-agent`
- Виртуальное окружение: `venv`
- Python в текущем окружении: `Python 3.9.6`
- Точка входа бота: `venv/bin/python -m app.main`
- Бот обычно запускается локально, не через `systemd`, если пользователь отдельно не сказал обратное.

## Текущий стек зависимостей

- `aiogram==3.13.1`
- `httpx==0.27.2`
- `python-dotenv==1.0.1`

## Быстрые команды

- Запуск бота:
  `venv/bin/python -m app.main`
- Синтаксическая проверка Python без проблем с macOS pycache:
  `PYTHONPYCACHEPREFIX=/private/tmp/issue-bot-pycache venv/bin/python -m py_compile app/*.py`

## Практические замечания

- После изменений в логике бота желательно сначала прогнать синтаксическую проверку.
- Если бот уже запущен, нужно остановить текущий процесс и поднять новый из корня этого проекта, иначе будет работать старый код.
