---
name: bot-debug-routing
description: "Диагностика случаев, когда Telegram-бот в этом проекте выбрал не тот сценарий: не туда зароутил сообщение, не понял формулировку или пошел не в ту ветку обработки."
---

# Bot Debug Routing

Используй этот skill, когда бот среагировал не так, как ожидалось.

## Что делать

1. Быстро прочитай:
   `docs/agent/debugging.md`, `docs/WORKLOG.md`, при необходимости `docs/ARCHITECTURE.md`
2. Зафиксируй реальную входную фразу пользователя и фактический ответ бота.
3. Определи ожидаемый сценарий.
4. Проверь по цепочке:
   - `app/bot.py` — порядок веток
   - `app/trigger.py` — regex, cleaning, state extraction, search heuristics
   - `app/llm.py` — prompts и fallback в `new_preview`
5. Сформулируй, где именно поломка:
   - триггер
   - deterministic routing
   - LLM classification
   - GitHub-side search/list behavior
6. После исправления предложи короткий regression smoke-check.

## Принцип

- Ищи минимальную точку поломки, а не переписывай весь роутинг.
- Сначала восстанавливай ожидаемое поведение на конкретной фразе пользователя.
- Если можно закрыть кейс deterministic-веткой без ухудшения UX, это обычно предпочтительнее.

## Когда читать references

- Для чеклиста по диагностике открой `references/checklist.md`.
