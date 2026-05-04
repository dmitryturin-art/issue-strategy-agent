import os
from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def _parse_chat_ids(raw_value: str) -> set[int]:
    chat_ids: set[int] = set()
    for item in raw_value.split(","):
        clean = item.strip()
        if not clean:
            continue
        try:
            chat_ids.add(int(clean))
        except ValueError as exc:
            raise RuntimeError(
                "Invalid ALLOWED_CHAT_IDS value. Use comma-separated numeric chat IDs."
            ) from exc
    return chat_ids


TELEGRAM_BOT_TOKEN: str = _require("TELEGRAM_BOT_TOKEN")

# Основной провайдер
LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
LLM_API_KEY: str = _require("LLM_API_KEY")
LLM_MODEL: str = os.getenv("LLM_MODEL", "meta-llama/llama-3.1-8b-instruct:free")

# Запасной провайдер (опционально) — включается при ошибках основного
LLM_FALLBACK_BASE_URL: str = os.getenv("LLM_FALLBACK_BASE_URL", "")
LLM_FALLBACK_API_KEY: str = os.getenv("LLM_FALLBACK_API_KEY", "")
LLM_FALLBACK_MODEL: str = os.getenv("LLM_FALLBACK_MODEL", "")

GITHUB_TOKEN: str = _require("GITHUB_TOKEN")
GITHUB_DEFAULT_REPO: str = _require("GITHUB_DEFAULT_REPO")

BOT_USERNAME: str = _require("BOT_USERNAME").lstrip("@")
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "./data/bot.db")
ALLOWED_CHAT_IDS: set[int] = _parse_chat_ids(os.getenv("ALLOWED_CHAT_IDS", ""))
