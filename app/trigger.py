import re
from typing import Optional

from aiogram.types import Message

from app.config import BOT_USERNAME

COMMANDS = {"/task", "/issue", "/add"}

EDIT_KEYWORDS = re.compile(
    r"^(измени|поправь|добавь|убери|переформулируй|исправь|удали|замени|сделай|напиши|уточни|расширь|сократи|перепиши)",
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
    "да",
    "ок",
    "ok",
    "давай",
    "го",
    "принято",
    "подтверждено",
    "create",
    "yes",
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
    # Убираем пунктуацию и лишние пробелы перед сравнением
    clean = re.sub(r"[.,!?;:)(\"']+", "", text.strip().lower()).strip()
    if clean in APPROVE_PHRASES:
        return True
    # Короткое сообщение (1-2 слова) содержит слово-апрув
    words = clean.split()
    if len(words) <= 2:
        approve_words = {"approve", "аппрув", "создавай", "подтверждаю", "заводи"}
        return bool(set(words) & approve_words)
    return False


def is_edit_request(text: str) -> bool:
    clean = text.strip()
    # strip bot mention first
    clean = re.sub(rf"@{re.escape(BOT_USERNAME)}", "", clean, flags=re.IGNORECASE).strip()
    return bool(EDIT_KEYWORDS.match(clean))


# ── issue action detection ────────────────────────────────────────────────────

_ISSUE_NUMBER_RE = re.compile(r"#(\d+)")

_ISSUE_ACTION_RE = re.compile(
    r"#\d+"
    r"|найди|найти|поищи|поиск|ищи"
    r"|закрой|закрыть|close"
    r"|открой|открыть|переоткрой|reopen"
    r"|прокомментируй|прокомментировать|добавь\s+коммент|comment"
    r"|обнови|обновить|update",
    re.IGNORECASE,
)

_STATE_OPEN_RE = re.compile(r"\b(открытые|открытых|открыт|open)\b", re.IGNORECASE)
_STATE_CLOSED_RE = re.compile(r"\b(закрытые|закрытых|закрыт|closed)\b", re.IGNORECASE)
_STATE_ALL_RE = re.compile(r"\b(все|all|любые)\b", re.IGNORECASE)


def extract_issue_number(text: str) -> Optional[int]:
    m = _ISSUE_NUMBER_RE.search(text)
    return int(m.group(1)) if m else None


def has_issue_action(text: str) -> bool:
    """True if the message likely refers to an existing issue action or search."""
    clean = re.sub(rf"@\w+", "", text)
    return bool(_ISSUE_ACTION_RE.search(clean))


def extract_state_filter(text: str) -> Optional[str]:
    """Extract open/closed/all state filter from text. None if unclear."""
    if _STATE_OPEN_RE.search(text):
        return "open"
    if _STATE_CLOSED_RE.search(text):
        return "closed"
    if _STATE_ALL_RE.search(text):
        return "all"
    return None
