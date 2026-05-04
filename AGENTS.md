# Project Instructions

Используй этот файл как короткий индекс, а не как единственный источник контекста.

## Как читать проектные инструкции

- Общие правила работы и язык: `docs/agent/communication.md`
- Границы между памятью продукта, проекта и агента: `docs/agent/memory-boundaries.md`
- Быстрый старт новой сессии: `docs/agent/session-start.md`
- Правила фиксации follow-up задач и GitHub issue: `docs/agent/tracking.md`
- Локальное окружение и команды запуска: `docs/agent/runtime.md`
- Типовой рабочий цикл по изменениям и перезапуску: `docs/agent/workflow.md`
- Частые рабочие команды проекта: `docs/agent/commands.md`
- Переносимый blueprint агентной памяти для других проектов: `docs/agent/agent-system-blueprint.md`
- Bootstrap-шаблон для нового проекта: `docs/agent/project-bootstrap-template.md`
- Работа с GitHub backlog и draft issues: `docs/agent/github.md`
- Типовые сценарии отладки: `docs/agent/debugging.md`
- Правила самоулучшения и работы со skills: `docs/agent/self-improvement.md`
- Локальные project-specific skills: `.codex/skills/`

## Базовые принципы

- Общение с пользователем и все user-facing тексты по умолчанию только на русском языке.
- Для явных и критичных сценариев предпочитай deterministic-логику.
- Для неявных формулировок и разговорных запросов предпочитай гибридный подход с LLM-assisted routing.
- Если по итогам обсуждения появляется конкретное улучшение, не оставляй его только в чате: фиксируй в `ROADMAP.md` и, когда уместно, в GitHub issue.
