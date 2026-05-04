import base64
import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

import httpx

from app import config

logger = logging.getLogger(__name__)

HEADERS = {
    "Authorization": f"Bearer {config.LLM_API_KEY}",
    "Content-Type": "application/json",
}

TIMEOUT = 60.0


@dataclass
class MessageContext:
    text: str
    replied_text: Optional[str]
    images_b64: list[str]  # base64-encoded images


@dataclass
class IssueCheck:
    is_issue: bool
    reason: str
    needs_question: bool
    question: Optional[str]


@dataclass
class IssuePreview:
    title: str
    issue_type: str
    summary: str
    expected_result: str
    acceptance_criteria: list[str]
    labels: list[str]
    question: Optional[str]


def _build_content(text: str, images_b64: list[str]) -> list[dict]:
    parts: list[dict] = [{"type": "text", "text": text}]
    for img in images_b64:
        parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{img}"},
        })
    return parts


def _extract_json(raw: str) -> dict:
    """Extract first JSON object from LLM response, stripping markdown fences."""
    raw = re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON found in LLM response: {raw[:200]}")
    return json.loads(match.group())


def _choose_model(has_images: bool) -> str:
    return config.LLM_VISION_MODEL if has_images else config.LLM_MODEL


async def check_is_issue(ctx: MessageContext) -> IssueCheck:
    combined = ctx.text
    if ctx.replied_text:
        combined = f"[Цитируемое сообщение]: {ctx.replied_text}\n[Новое сообщение]: {ctx.text}"

    system = (
        "Ты помощник, который анализирует сообщения из рабочего Telegram-чата. "
        "Определи, является ли сообщение задачей/багом/фичей для GitHub issue. "
        "Отвечай ТОЛЬКО валидным JSON без пояснений."
    )
    user_prompt = (
        f"Сообщение:\n{combined}\n\n"
        "Верни JSON:\n"
        '{"is_issue": true/false, "reason": "...", "needs_question": true/false, "question": "..."}\n'
        "question — короткий уточняющий вопрос, если без него нельзя сформировать задачу, иначе null."
    )

    has_images = bool(ctx.images_b64)
    content = _build_content(user_prompt, ctx.images_b64) if has_images else user_prompt

    data = await _call_llm(
        model=_choose_model(has_images),
        system=system,
        content=content,
    )
    try:
        parsed = _extract_json(data)
        return IssueCheck(
            is_issue=bool(parsed.get("is_issue")),
            reason=parsed.get("reason", ""),
            needs_question=bool(parsed.get("needs_question")),
            question=parsed.get("question"),
        )
    except Exception as e:
        logger.error("Failed to parse is_issue response: %s | raw: %s", e, data[:300])
        raise


async def generate_preview(ctx: MessageContext) -> IssuePreview:
    combined = ctx.text
    if ctx.replied_text:
        combined = f"[Цитируемое сообщение]: {ctx.replied_text}\n[Новое сообщение]: {ctx.text}"

    image_note = ""
    if ctx.images_b64:
        image_note = "\nК задаче приложены изображения — учти их при формировании описания."

    system = (
        "Ты технический менеджер, который оформляет GitHub issue на русском языке. "
        "Сохраняй смысл исходного сообщения точно. "
        "Отвечай ТОЛЬКО валидным JSON без пояснений."
    )
    user_prompt = (
        f"Сообщение:{image_note}\n{combined}\n\n"
        "Сформируй GitHub issue. Верни JSON:\n"
        "{\n"
        '  "title": "краткое название",\n'
        '  "type": "bug|feature|task|question|improvement",\n'
        '  "summary": "суть задачи",\n'
        '  "expected_result": "ожидаемый результат",\n'
        '  "acceptance_criteria": ["критерий 1", "критерий 2"],\n'
        '  "labels": ["label1"],\n'
        '  "question": null\n'
        "}\n"
        "question — только если критически не хватает данных для формирования задачи, иначе null."
    )

    has_images = bool(ctx.images_b64)
    content = _build_content(user_prompt, ctx.images_b64) if has_images else user_prompt

    data = await _call_llm(
        model=_choose_model(has_images),
        system=system,
        content=content,
    )
    try:
        parsed = _extract_json(data)
        return IssuePreview(
            title=parsed["title"],
            issue_type=parsed.get("type", "task"),
            summary=parsed["summary"],
            expected_result=parsed.get("expected_result", ""),
            acceptance_criteria=parsed.get("acceptance_criteria", []),
            labels=parsed.get("labels", []),
            question=parsed.get("question"),
        )
    except Exception as e:
        logger.error("Failed to parse preview response: %s | raw: %s", e, data[:300])
        raise


async def edit_preview(current_body: str, edit_instruction: str) -> IssuePreview:
    system = (
        "Ты технический менеджер, который редактирует GitHub issue на русском языке. "
        "Применяй правку точно по инструкции, не меняя остальное. "
        "Отвечай ТОЛЬКО валидным JSON без пояснений."
    )
    user_prompt = (
        f"Текущий issue (Markdown):\n{current_body}\n\n"
        f"Правка: {edit_instruction}\n\n"
        "Верни обновлённый JSON:\n"
        "{\n"
        '  "title": "...",\n'
        '  "type": "bug|feature|task|question|improvement",\n'
        '  "summary": "...",\n'
        '  "expected_result": "...",\n'
        '  "acceptance_criteria": ["..."],\n'
        '  "labels": ["..."],\n'
        '  "question": null\n'
        "}"
    )

    data = await _call_llm(
        model=config.LLM_MODEL,
        system=system,
        content=user_prompt,
    )
    try:
        parsed = _extract_json(data)
        return IssuePreview(
            title=parsed["title"],
            issue_type=parsed.get("type", "task"),
            summary=parsed["summary"],
            expected_result=parsed.get("expected_result", ""),
            acceptance_criteria=parsed.get("acceptance_criteria", []),
            labels=parsed.get("labels", []),
            question=parsed.get("question"),
        )
    except Exception as e:
        logger.error("Failed to parse edit_preview response: %s | raw: %s", e, data[:300])
        raise


async def _call_llm(model: str, system: str, content) -> str:
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": content},
    ]
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
    }
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            f"{config.LLM_BASE_URL}/chat/completions",
            headers=HEADERS,
            json=payload,
        )
        resp.raise_for_status()
        result = resp.json()
        return result["choices"][0]["message"]["content"]
