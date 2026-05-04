import re
from aiogram.types import Message

from app.config import BOT_USERNAME

COMMANDS = {"/task", "/issue", "/add"}

EDIT_KEYWORDS = re.compile(
    r"^(измени|поправь|добавь|убери|переформулируй|исправь|удали|замени)",
    re.IGNORECASE,
)

APPROVE_PHRASES = {
    "approve",
    "аппрув",
    "создавай",
    "подтверждаю",
    "ок, создавай",
    "да, заводи",
    "заводи",
    "ок создавай",
    "да заводи",
}


def _mention_in_text(text: str) -> bool:
    return f"@{BOT_USERNAME}".lower() in text.lower()


def is_triggered(message: Message) -> bool:
    """Return True if the bot should process this message."""
    text = (message.text or message.caption or "").strip()
    has_mention = _mention_in_text(text)

    # /task, /issue, /add commands
    first_word = text.split()[0].lower() if text else ""
    if first_word in COMMANDS:
        return True

    # direct mention
    if has_mention:
        return True

    # reply to a bot message (bot_id checked in bot.py via reply_is_to_bot)
    # trigger.py can't access bot id directly, so we expose a helper used in bot.py
    return False


def is_reply_to_bot(message: Message, bot_id: int) -> bool:
    return (
        message.reply_to_message is not None
        and message.reply_to_message.from_user is not None
        and message.reply_to_message.from_user.id == bot_id
    )


def is_approve(text: str) -> bool:
    return text.strip().lower() in APPROVE_PHRASES


def is_edit_request(text: str) -> bool:
    clean = text.strip()
    # strip bot mention first
    clean = re.sub(rf"@{re.escape(BOT_USERNAME)}", "", clean, flags=re.IGNORECASE).strip()
    return bool(EDIT_KEYWORDS.match(clean))
