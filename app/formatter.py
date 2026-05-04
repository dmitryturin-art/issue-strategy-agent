from app.llm import IssuePreview

_TYPE_LABELS = {
    "bug": "🐛 Баг",
    "feature": "✨ Фича",
    "task": "📋 Задача",
    "question": "❓ Вопрос",
    "improvement": "🔧 Улучшение",
}


def format_preview(preview: IssuePreview) -> str:
    type_label = _TYPE_LABELS.get(preview.issue_type, preview.issue_type)

    criteria_lines = "\n".join(
        f"  - {c}" for c in preview.acceptance_criteria
    ) if preview.acceptance_criteria else "  — не указаны"

    labels_str = ", ".join(f"`{l}`" for l in preview.labels) if preview.labels else "—"

    lines = [
        f"*{preview.title}*",
        "",
        f"*Тип:* {type_label}",
        "",
        f"*Суть:*\n{preview.summary}",
        "",
        f"*Ожидаемый результат:*\n{preview.expected_result}",
        "",
        f"*Критерии приёмки:*\n{criteria_lines}",
        "",
        f"*Метки:* {labels_str}",
    ]

    if preview.question:
        lines += [
            "",
            "─" * 30,
            f"❓ *Уточнение:* {preview.question}",
        ]

    lines += [
        "",
        "─" * 30,
        "_Напишите reply: `approve` — чтобы создать issue, или `измени...` — чтобы поправить._",
    ]

    return "\n".join(lines)


def format_issue_body(preview: IssuePreview) -> str:
    """Markdown body for GitHub issue."""
    criteria_lines = "\n".join(
        f"- {c}" for c in preview.acceptance_criteria
    ) if preview.acceptance_criteria else "— не указаны"

    return (
        f"## Суть\n{preview.summary}\n\n"
        f"## Ожидаемый результат\n{preview.expected_result}\n\n"
        f"## Критерии приёмки\n{criteria_lines}\n\n"
        f"---\n*Создано через issue-bot из Telegram*"
    )
