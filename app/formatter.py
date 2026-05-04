from app.llm import IssuePreview

_TYPE_LABELS = {
    "bug": "Баг",
    "feature": "Фича",
    "task": "Задача",
    "question": "Вопрос",
    "improvement": "Улучшение",
}


def format_preview(preview: IssuePreview) -> str:
    type_label = _TYPE_LABELS.get(preview.issue_type, preview.issue_type)

    criteria_lines = "\n".join(
        f"- [ ] {c}" for c in preview.acceptance_criteria
    ) if preview.acceptance_criteria else "- [ ] не указаны"

    labels_str = ", ".join(preview.labels) if preview.labels else "—"

    lines = [
        f"1. Название: {preview.title}",
        f"2. Тип: {type_label}",
        f"3. Суть: {preview.summary}",
        f"4. Ожидаемый результат: {preview.expected_result}",
        f"5. Критерии приёмки:\n{criteria_lines}",
        f"6. Метки (предложение): {labels_str}",
    ]

    if preview.question:
        lines.append("")
        lines.append(f"Уточнение: {preview.question}")

    lines += [
        "",
        "─────────────────────────────────────",
        "Reply: approve или создавай — создать issue, измени... — поправить.",
    ]

    return "\n".join(lines)


def format_issue_body(preview: IssuePreview) -> str:
    """Markdown body для GitHub issue."""
    criteria_lines = "\n".join(
        f"- [ ] {c}" for c in preview.acceptance_criteria
    ) if preview.acceptance_criteria else "— не указаны"

    return (
        f"## Суть\n{preview.summary}\n\n"
        f"## Ожидаемый результат\n{preview.expected_result}\n\n"
        f"## Критерии приёмки\n{criteria_lines}\n\n"
        f"---\n*Создано через issue-bot из Telegram*"
    )
