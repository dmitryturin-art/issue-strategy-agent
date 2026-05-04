import base64
import json
import logging
from typing import Optional

import httpx
from aiogram import Bot, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, PhotoSize

from app import config, storage, trigger
from app.formatter import format_preview, format_issue_body
from app.github_client import create_issue
from app.llm import MessageContext, check_is_issue, generate_preview, edit_preview

logger = logging.getLogger(__name__)
router = Router()

# Защита от race condition: сообщения, которые сейчас обрабатываются
_processing: set[tuple[int, int]] = set()


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
    is_triggered = trigger.is_triggered(message) or is_reply_to_bot

    if not is_triggered:
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

    # ── approve flow (reply to bot preview) ───────────────────────────────────
    if is_reply_to_bot and trigger.is_approve(text):
        await _handle_approve(message)
        return

    # ── edit flow (reply to bot preview) ──────────────────────────────────────
    if is_reply_to_bot and trigger.is_edit_request(text):
        await _handle_edit(message, bot)
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

async def _handle_edit(message: Message, bot: Bot) -> None:
    chat_id = message.chat.id
    replied_msg_id = message.reply_to_message.message_id

    task = storage.get_task_by_preview_msg(chat_id, replied_msg_id)
    if not task:
        await message.reply("Не нашёл preview, на который вы отвечаете.")
        return

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

async def _handle_approve(message: Message) -> None:
    chat_id = message.chat.id
    replied_msg_id = message.reply_to_message.message_id

    task = storage.get_task_by_preview_msg(chat_id, replied_msg_id)
    if not task:
        await message.reply("Не нашёл preview, на который вы отвечаете.")
        return

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
