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

_SEARCH_VERB_RE = re.compile(
    r"\b(найди|найти|поищи|поиск|ищи|покажи|показать|список|списком|дай|выведи)\b",
    re.IGNORECASE,
)
_ISSUE_ENTITY_RE = re.compile(r"\b(issue|issues|задач[аиуы]?|тикет(?:ы|ов|а)?)\b", re.IGNORECASE)
_STATE_OPEN_RE = re.compile(r"\b(открытые|открытых|открыт|open)\b", re.IGNORECASE)
_STATE_CLOSED_RE = re.compile(r"\b(закрытые|закрытых|закрыт|closed)\b", re.IGNORECASE)
_STATE_ALL_RE = re.compile(r"\b(все|всех|всем|всеми|all|любые)\b", re.IGNORECASE)
_SEARCH_NOISE_RE = re.compile(
    r"\b("
    r"найди|найти|поищи|поиск|ищи|покажи|показать|дай|выведи|список|списком|"
    r"issue|issues|задач[аиуы]?|тикет(?:ы|ов|а)?|"
    r"открытые|открытых|открыт|open|закрытые|закрытых|закрыт|closed|все|всех|всем|всеми|all|любые|"
    r"мне|пожалуйста"
    r")\b",
    re.IGNORECASE,
)


def extract_issue_number(text: str) -> Optional[int]:
    m = _ISSUE_NUMBER_RE.search(text)
    return int(m.group(1)) if m else None


def has_issue_action(text: str) -> bool:
    """True if the message likely refers to an existing issue action or search."""
    clean = re.sub(rf"@\w+", "", text)
    if _ISSUE_ACTION_RE.search(clean):
        return True
    return looks_like_issue_search(clean)


def extract_state_filter(text: str) -> Optional[str]:
    """Extract open/closed/all state filter from text. None if unclear."""
    if _STATE_OPEN_RE.search(text):
        return "open"
    if _STATE_CLOSED_RE.search(text):
        return "closed"
    if _STATE_ALL_RE.search(text):
        return "all"
    return None


def normalize_issue_search_query(text: str) -> str:
    """Strip service words from issue search text. Empty string means list by state."""
    clean = re.sub(rf"@\w+", "", text)
    clean = _SEARCH_NOISE_RE.sub(" ", clean)
    clean = re.sub(r"[\"'`«»“”„:;!?.,()]+", " ", clean)
    clean = re.sub(r"^\s*(про|по|о|об|насчет)\b", " ", clean, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", clean).strip()


def looks_like_issue_search(text: str) -> bool:
    clean = re.sub(rf"@\w+", "", text)
    return bool(_SEARCH_VERB_RE.search(clean) and (_ISSUE_ENTITY_RE.search(clean) or extract_state_filter(clean)))
