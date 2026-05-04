import base64
import json
import logging
import sqlite3
from typing import Optional

import httpx
from aiogram import Bot, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, PhotoSize

from app import config, storage, trigger
from app.formatter import format_preview, format_issue_body
from app.github_client import (
    create_issue, get_issue, add_comment,
    close_issue, reopen_issue, update_issue, search_issues,
)
from app.llm import (
    MessageContext, ActionIntent,
    check_is_issue, generate_preview, edit_preview,
    classify_action, generate_update_patch,
)

logger = logging.getLogger(__name__)
router = Router()

# Защита от race condition: сообщения, которые сейчас обрабатываются
_processing: set[tuple[int, int]] = set()

# Ожидаем ответа пользователя о статусе поиска: (chat_id, user_id) → search_query
_pending_search: dict[tuple[int, int], str] = {}


# ─── helpers ──────────────────────────────────────────────────────────────────

async def _download_photo(bot: Bot, photo: PhotoSize) -> str:
    """Download a Telegram photo and return it as base64 string."""
    file = await bot.get_file(photo.file_id)
    url = f"https://api.telegram.org/file/bot{config.TELEGRAM_BOT_TOKEN}/{file.file_path}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    return base64.b64encode(resp.content).decode()


async def _extract_context(message: Message, bot: Bot) -> MessageContext:
    """Build MessageContext from current message + replied message."""
    text = (message.text or message.caption or "").strip()
    replied_text: Optional[str] = None
    images_b64: list[str] = []

    # photos in current message
    if message.photo:
        largest = message.photo[-1]
        try:
            images_b64.append(await _download_photo(bot, largest))
        except Exception as e:
            logger.warning("Failed to download photo from current message: %s", e)

    # context from replied message
    replied = message.reply_to_message
    if replied:
        replied_text = (replied.text or replied.caption or "").strip() or None

        # photos in replied message (e.g., user replies to someone's screenshot)
        if replied.photo:
            largest = replied.photo[-1]
            try:
                images_b64.append(await _download_photo(bot, largest))
            except Exception as e:
                logger.warning("Failed to download photo from replied message: %s", e)

    return MessageContext(text=text, replied_text=replied_text, images_b64=images_b64)


def _clean_mention(text: str) -> str:
    """Remove @BOT_USERNAME from text for cleaner LLM input."""
    import re
    return re.sub(rf"@{re.escape(config.BOT_USERNAME)}", "", text, flags=re.IGNORECASE).strip()


# ─── main message handler ─────────────────────────────────────────────────────

@router.message()
async def handle_message(message: Message, bot: Bot) -> None:
    if not message.from_user:
        return

    if config.ALLOWED_CHAT_IDS and message.chat.id not in config.ALLOWED_CHAT_IDS:
        logger.info("Ignoring message from unauthorized chat: %s", message.chat.id)
        return

    bot_info = await bot.get_me()
    bot_id = bot_info.id

    text = (message.text or message.caption or "").strip()
    is_reply_to_bot = trigger.is_reply_to_bot(message, bot_id)
    has_explicit_trigger = trigger.is_triggered(message)

    if not has_explicit_trigger and not is_reply_to_bot:
        return

    # Reply на сообщение бота — проверяем, является ли оно известным preview
    replied_preview = None
    if is_reply_to_bot:
        replied_preview = storage.get_task_by_preview_msg(
            message.chat.id, message.reply_to_message.message_id
        )
        # Reply на НЕ-preview сообщение бота (ошибка, /start, итд.) — игнорируем
        if replied_preview is None and not has_explicit_trigger:
            return

    logger.info(
        "Triggered: chat=%s msg=%s user=%s text=%.80s",
        message.chat.id,
        message.message_id,
        message.from_user.id,
        text,
    )

    # ── voice stub ────────────────────────────────────────────────────────────
    if message.voice or message.audio:
        await message.reply(
            "Голосовые сообщения пока не поддерживаются. Скоро появится эта возможность."
        )
        return

    # ── approve (reply на известный preview + явный @mention или /команда) ───
    if replied_preview is not None and has_explicit_trigger and trigger.is_approve(text):
        await _handle_approve(message, replied_preview)
        return

    # ── edit (reply на известный preview + явный @mention или /команда) ──────
    if replied_preview is not None and has_explicit_trigger and trigger.is_edit_request(text):
        await _handle_edit(message, bot, replied_preview)
        return

    # ── reply на preview, но нет @mention → молча игнорируем ────────────────
    if replied_preview is not None and not has_explicit_trigger:
        return

    clean_text = _clean_mention(text)

    # ── ответ на вопрос о статусе поиска ─────────────────────────────────────
    pending_key = (message.chat.id, message.from_user.id)
    if pending_key in _pending_search:
        state = trigger.extract_state_filter(clean_text)
        if state:
            query = _pending_search.pop(pending_key)
            await _handle_issue_search(message, query, state)
            return
        _pending_search.pop(pending_key, None)

    # ── issue actions: комментарий, закрытие, обновление, поиск ──────────────
    if trigger.has_issue_action(clean_text):
        try:
            intent = await classify_action(clean_text)
        except Exception:
            await message.reply("Не удалось получить ответ от LLM.")
            return
        if intent.action != "new_preview":
            await _dispatch_issue_intent(message, intent)
            return

    # ── new issue preview ─────────────────────────────────────────────────────
    key = (message.chat.id, message.message_id)
    if key in _processing:
        return
    _processing.add(key)
    try:
        await _handle_new_preview(message, bot)
    finally:
        _processing.discard(key)


# ─── new preview ──────────────────────────────────────────────────────────────

async def _handle_new_preview(message: Message, bot: Bot) -> None:
    chat_id = message.chat.id
    source_id = message.message_id
    replied = message.reply_to_message
    reply_id = replied.message_id if replied else None

    # anti-duplicate
    existing = storage.get_task_by_source(chat_id, source_id)
    if existing:
        if existing["status"] == "created":
            await message.reply(f"Issue уже создан: {existing['github_issue_url']}")
        else:
            await message.reply("Preview для этого сообщения уже существует. Ответьте `approve` чтобы создать issue.")
        return

    ctx = await _extract_context(message, bot)
    # clean bot mention from text sent to LLM
    ctx = MessageContext(
        text=_clean_mention(ctx.text),
        replied_text=ctx.replied_text,
        images_b64=ctx.images_b64,
    )

    if not ctx.text and not ctx.replied_text and not ctx.images_b64:
        await message.reply("Не вижу текста или изображений для создания задачи.")
        return

    # is_issue check
    try:
        check = await check_is_issue(ctx)
    except Exception:
        await message.reply("Не удалось получить ответ от LLM.")
        return

    logger.info("is_issue=%s reason=%.100s", check.is_issue, check.reason)

    if not check.is_issue:
        await message.reply(
            "Похоже, это не задача для issue. Могу оформить, если уточните, что нужно сделать."
        )
        return

    # generate preview
    try:
        preview = await generate_preview(ctx)
    except Exception:
        await message.reply("Не удалось получить ответ от LLM.")
        return

    logger.info("Preview generated: title=%.80s", preview.title)

    body = format_issue_body(preview)
    preview_text = format_preview(preview)

    sent = await message.reply(preview_text)

    storage.create_task(
        chat_id=chat_id,
        source_message_id=source_id,
        reply_message_id=reply_id,
        preview_message_id=sent.message_id,
        author_id=message.from_user.id,
        author_username=message.from_user.username,
        repo=config.GITHUB_DEFAULT_REPO,
        title=preview.title,
        body=body,
        labels=preview.labels,
    )


# ─── edit preview ─────────────────────────────────────────────────────────────

async def _handle_edit(message: Message, bot: Bot, task: sqlite3.Row) -> None:
    if task["status"] == "created":
        await message.reply(f"Issue уже создан, изменить preview нельзя: {task['github_issue_url']}")
        return

    instruction = _clean_mention(message.text or "")

    try:
        updated = await edit_preview(task["body"], instruction)
    except Exception:
        await message.reply("Не удалось получить ответ от LLM.")
        return

    logger.info("Preview edited: task_id=%s", task["id"])

    new_body = format_issue_body(updated)
    new_text = format_preview(updated)

    sent = await message.reply(new_text)

    storage.update_task_preview(
        task["id"],
        title=updated.title,
        body=new_body,
        labels=updated.labels,
        preview_message_id=sent.message_id,
    )


# ─── approve ──────────────────────────────────────────────────────────────────

async def _handle_approve(message: Message, task: sqlite3.Row) -> None:
    if task["status"] == "created":
        await message.reply(f"Issue уже создан: {task['github_issue_url']}")
        return

    logger.info(
        "Approve received: task_id=%s user=%s",
        task["id"],
        message.from_user.id,
    )

    labels = json.loads(task["labels_json"] or "[]")

    try:
        url = await create_issue(
            title=task["title"],
            body=task["body"],
            labels=labels,
            repo=task["repo"],
        )
    except Exception as e:
        logger.error("GitHub API error: %s", e)
        await message.reply("Не удалось создать issue, ошибка GitHub API.")
        return

    storage.mark_task_created(task["id"], url)

    logger.info("Issue created: task_id=%s url=%s", task["id"], url)
    await message.reply(f"Issue создан: {url}")


# ─── issue action dispatch ────────────────────────────────────────────────────

async def _dispatch_issue_intent(message: Message, intent: ActionIntent) -> None:
    if intent.action in ("comment", "close", "reopen", "update") and not intent.issue_number:
        await message.reply("Не понял номер issue. Укажите, например: #123")
        return

    if intent.action == "comment":
        await _handle_issue_comment(message, intent.issue_number, intent.instruction)
    elif intent.action == "close":
        await _handle_issue_close(message, intent.issue_number, intent.instruction)
    elif intent.action == "reopen":
        await _handle_issue_reopen(message, intent.issue_number)
    elif intent.action == "update":
        await _handle_issue_update(message, intent.issue_number, intent.instruction)
    elif intent.action == "search":
        query = intent.search_query or intent.instruction
        if intent.state_filter:
            await _handle_issue_search(message, query, intent.state_filter)
        else:
            _pending_search[(message.chat.id, message.from_user.id)] = query
            await message.reply(
                "Искать среди открытых или закрытых?\n"
                "Ответьте: @" + config.BOT_USERNAME + " открытые / закрытые / все"
            )


async def _handle_issue_comment(message: Message, number: int, body: str) -> None:
    try:
        url = await add_comment(number=number, body=body)
    except Exception as e:
        logger.error("GitHub comment error: %s", e)
        await message.reply(f"Не удалось добавить комментарий к issue #{number}.")
        return
    await message.reply(f"Комментарий добавлен к #{number}: {url}")


async def _handle_issue_close(message: Message, number: int, comment: str) -> None:
    try:
        if comment and comment.strip():
            await add_comment(number=number, body=comment)
        await close_issue(number=number)
    except Exception as e:
        logger.error("GitHub close error: %s", e)
        await message.reply(f"Не удалось закрыть issue #{number}.")
        return
    await message.reply(f"Issue #{number} закрыт.")


async def _handle_issue_reopen(message: Message, number: int) -> None:
    try:
        await reopen_issue(number=number)
    except Exception as e:
        logger.error("GitHub reopen error: %s", e)
        await message.reply(f"Не удалось переоткрыть issue #{number}.")
        return
    await message.reply(f"Issue #{number} переоткрыт.")


async def _handle_issue_update(message: Message, number: int, instruction: str) -> None:
    try:
        current = await get_issue(number=number)
    except Exception as e:
        logger.error("GitHub get_issue error: %s", e)
        await message.reply(f"Не удалось получить issue #{number} с GitHub.")
        return

    try:
        patch = await generate_update_patch(current, instruction)
    except Exception:
        await message.reply("Не удалось получить ответ от LLM.")
        return

    kwargs: dict = {}
    if patch.get("title"):
        kwargs["title"] = patch["title"]
    if patch.get("body"):
        kwargs["body"] = patch["body"]
    if patch.get("labels") is not None:
        kwargs["labels"] = patch["labels"]

    if not kwargs:
        await message.reply(f"Не понял, что именно изменить в issue #{number}.")
        return

    try:
        await update_issue(number=number, **kwargs)
    except Exception as e:
        logger.error("GitHub update error: %s", e)
        await message.reply(f"Не удалось обновить issue #{number}.")
        return

    url = current.get("html_url", f"https://github.com/{config.GITHUB_DEFAULT_REPO}/issues/{number}")
    await message.reply(f"Issue #{number} обновлён: {url}")


async def _handle_issue_search(message: Message, query: str, state: str) -> None:
    state_label = {"open": "открытые", "closed": "закрытые", "all": "все"}.get(state, state)
    try:
        results = await search_issues(query=query, state=state)
    except Exception as e:
        logger.error("GitHub search error: %s", e)
        await message.reply("Не удалось выполнить поиск на GitHub.")
        return

    if not results:
        await message.reply(f"Issues по запросу «{query}» не найдены ({state_label}).")
        return

    lines = [f"Найдено {len(results)} issue ({state_label}):"]
    for r in results:
        lines.append(f"#{r['number']} — {r['title']}\n{r['url']}")
    await message.reply("\n\n".join(lines))


# ─── commands ─────────────────────────────────────────────────────────────────

@router.message(Command("start", "help"))
async def cmd_help(message: Message) -> None:
    await message.reply(
        "*Issue-бот*\n\n"
        "Упомяните меня `@bot` или ответьте на моё сообщение, чтобы:\n"
        "• Оформить задачу в GitHub issue\n"
        "• Поправить preview (`измени...`, `добавь...`)\n"
        "• Подтвердить создание (`approve`, `создавай`)\n\n"
        "Команды: `/task`, `/issue`, `/add`",
        parse_mode=ParseMode.MARKDOWN,
    )
