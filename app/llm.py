import base64
import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

import httpx

from app import config
from app.project_context import get_project_profile

logger = logging.getLogger(__name__)

TIMEOUT = config.LLM_TIMEOUT


@dataclass
class MessageContext:
    text: str
    replied_text: Optional[str]
    images_b64: list[str]  # base64-encoded images


@dataclass
class ActionIntent:
    action: str  # "comment"|"close"|"reopen"|"update"|"search"|"new_preview"
    issue_number: Optional[int]
    instruction: str   # комментарий / инструкция по изменению / текст запроса
    search_query: Optional[str]
    state_filter: Optional[str]  # "open"|"closed"|"all"|None (None = уточнить у пользователя)


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


def _project_context_block() -> str:
    profile = get_project_profile(config.GITHUB_DEFAULT_REPO)
    if not profile:
        return ""
    return f"Контекст проекта:\n{profile.short_context}\n\n"


async def check_is_issue(ctx: MessageContext) -> IssueCheck:
    combined = ctx.text
    if ctx.replied_text:
        combined = f"[Цитируемое сообщение]: {ctx.replied_text}\n[Новое сообщение]: {ctx.text}"

    project_context = _project_context_block()
    system = (
        "Ты помощник, который анализирует сообщения из рабочего Telegram-чата. "
        "Учитывай только переданный краткий контекст проекта, не придумывай детали сверх него. "
        "Определи, является ли сообщение задачей/багом/фичей для GitHub issue. "
        "Отвечай ТОЛЬКО валидным JSON без пояснений."
    )
    user_prompt = (
        f"{project_context}Сообщение:\n{combined}\n\n"
        "Верни JSON:\n"
        '{"is_issue": true/false, "reason": "...", "needs_question": true/false, "question": "..."}\n'
        "question — короткий уточняющий вопрос, если без него нельзя сформировать задачу, иначе null."
    )

    content = _build_content(user_prompt, ctx.images_b64) if ctx.images_b64 else user_prompt

    data = await _call_llm(
        model=config.LLM_MODEL,
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

    project_context = _project_context_block()
    image_note = ""
    if ctx.images_b64:
        image_note = "\nК задаче приложены изображения — учти их при формировании описания."

    system = (
        "Ты технический менеджер, который оформляет GitHub issue на русском языке. "
        "Учитывай только переданный краткий контекст проекта, не придумывай детали сверх него. "
        "Сохраняй смысл исходного сообщения точно. "
        "Отвечай ТОЛЬКО валидным JSON без пояснений."
    )
    user_prompt = (
        f"{project_context}Сообщение:{image_note}\n{combined}\n\n"
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

    content = _build_content(user_prompt, ctx.images_b64) if ctx.images_b64 else user_prompt

    data = await _call_llm(
        model=config.LLM_MODEL,
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
    project_context = _project_context_block()
    system = (
        "Ты технический менеджер, который редактирует GitHub issue на русском языке. "
        "Учитывай только переданный краткий контекст проекта, не придумывай детали сверх него. "
        "Применяй правку точно по инструкции, не меняя остальное. "
        "Отвечай ТОЛЬКО валидным JSON без пояснений."
    )
    user_prompt = (
        f"{project_context}Текущий issue (Markdown):\n{current_body}\n\n"
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


async def classify_action(text: str) -> ActionIntent:
    """Classify user intent: comment / close / reopen / update / search / new_preview."""
    system = (
        "Ты помощник Telegram-бота для управления GitHub issues. "
        "Определи намерение пользователя по его сообщению. "
        "Отвечай ТОЛЬКО валидным JSON без пояснений."
    )
    user_prompt = (
        f'Сообщение: "{text}"\n\n'
        "Верни JSON:\n"
        "{\n"
        '  "action": "comment|close|reopen|update|search|new_preview",\n'
        '  "issue_number": 123 или null,\n'
        '  "instruction": "текст комментария или инструкция по изменению или null",\n'
        '  "search_query": "поисковый запрос или null",\n'
        '  "state_filter": "open|closed|all или null если не указано"\n'
        "}\n\n"
        "Действия:\n"
        "- comment: добавить комментарий к существующему issue (#N)\n"
        "- close: закрыть issue (#N)\n"
        "- reopen: переоткрыть issue (#N)\n"
        "- update: изменить заголовок/описание/метки issue (#N)\n"
        "- search: найти issues по запросу (search_query = поисковые термины)\n"
        "- new_preview: создать новый issue\n"
        "issue_number: число из упоминания #N в тексте\n"
        "instruction: текст после указания действия и номера issue\n"
        "state_filter: open если 'открытые', closed если 'закрытые', all если 'все', иначе null"
    )
    data = await _call_llm(model=config.LLM_MODEL, system=system, content=user_prompt)
    try:
        parsed = _extract_json(data)
        return ActionIntent(
            action=parsed.get("action", "new_preview"),
            issue_number=parsed.get("issue_number"),
            instruction=parsed.get("instruction") or text,
            search_query=parsed.get("search_query"),
            state_filter=parsed.get("state_filter"),
        )
    except Exception as e:
        logger.error("Failed to parse classify_action: %s | raw: %s", e, data[:200])
        return ActionIntent(action="new_preview", issue_number=None, instruction=text, search_query=None, state_filter=None)


async def generate_update_patch(current_issue: dict, instruction: str) -> dict:
    """Ask LLM which fields to update in a GitHub issue. Returns patch dict."""
    labels = ", ".join(l["name"] for l in current_issue.get("labels", []))
    system = (
        "Ты помощник, который обновляет GitHub issues по инструкции. "
        "Верни только поля, которые нужно изменить. null = не менять. "
        "Отвечай ТОЛЬКО валидным JSON без пояснений."
    )
    user_prompt = (
        f"Issue #{current_issue.get('number')}:\n"
        f"Заголовок: {current_issue.get('title')}\n"
        f"Описание: {(current_issue.get('body') or '')[:600]}\n"
        f"Метки: {labels or '—'}\n\n"
        f"Инструкция: {instruction}\n\n"
        "Верни JSON с полями для обновления:\n"
        "{\n"
        '  "title": "новый заголовок или null",\n'
        '  "body": "новое описание или null",\n'
        '  "labels": ["метка"] или null\n'
        "}"
    )
    data = await _call_llm(model=config.LLM_MODEL, system=system, content=user_prompt)
    try:
        return _extract_json(data)
    except Exception as e:
        logger.error("Failed to parse update_patch: %s | raw: %s", e, data[:200])
        raise


def _should_fallback(exc: Exception) -> bool:
    """Переключаемся на запасной провайдер при сетевых и серверных ошибках."""
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        # 402 оплата, 429 лимит, 5xx сервер — всё это повод попробовать fallback
        return exc.response.status_code in {402, 429} or exc.response.status_code >= 500
    return False


async def _call_llm(model: str, system: str, content) -> str:
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": content},
    ]
    payload = {"model": model, "messages": messages, "temperature": 0.2}

    try:
        return await _do_request(config.LLM_BASE_URL, config.LLM_API_KEY, payload)
    except Exception as exc:
        if not _should_fallback(exc):
            raise

        fallback_url = config.LLM_FALLBACK_BASE_URL
        fallback_key = config.LLM_FALLBACK_API_KEY
        fallback_model = config.LLM_FALLBACK_MODEL

        if not (fallback_url and fallback_key and fallback_model):
            logger.warning("Основной LLM недоступен, запасной не настроен: %s", exc)
            raise

        logger.warning("Основной LLM недоступен (%s), переключаюсь на запасной провайдер", exc)
        payload["model"] = fallback_model
        return await _do_request(fallback_url, fallback_key, payload)


async def _do_request(base_url: str, api_key: str, payload: dict) -> str:
    logger.info("LLM запрос: модель=%s провайдер=%s", payload.get("model"), base_url)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
