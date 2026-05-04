---
name: issue-triage
description: "Разбор пользовательского обращения к Telegram-боту в этом проекте: понять, что это за сценарий, где deterministic-ветка, где LLM-routing, и какое действие бот должен выполнить."
---

# Issue Triage

Используй этот skill, когда нужно понять, как бот должен интерпретировать обращение пользователя.

## Что делать

1. Быстро прочитай:
   `docs/agent/debugging.md`, `docs/agent/workflow.md`, `docs/WORKLOG.md`
2. Определи тип сценария:
   - новый issue preview
   - поиск issues
   - comment / close / reopen / update
   - approve / edit reply на preview
   - неявная формулировка, где нужен LLM-routing
3. Проверь:
   - `app/bot.py` — порядок роутинга
   - `app/trigger.py` — deterministic-эвристики
   - `app/llm.py` — classify_action, check_is_issue, prompts
4. Явно сформулируй, какую команду или intent бот должен был выбрать.
5. Если поведение спорное, предложи 1-3 контрольные фразы для живой проверки в Telegram.

## Принцип

- Сначала пытайся понять, должен ли кейс решаться deterministic-веткой.
- Если формулировка разговорная или неоднозначная, смотри в сторону LLM-assisted routing.
- Не пытайся “лечить” LLM там, где простое правило надежнее.

## Когда читать references

- Для примеров типовых формулировок и маршрутов открой `references/patterns.md`.
