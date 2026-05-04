import logging
from typing import Optional

import httpx

from app.config import GITHUB_TOKEN, GITHUB_DEFAULT_REPO

logger = logging.getLogger(__name__)

_BASE = "https://api.github.com"
_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
_TIMEOUT = 30.0


def _parse_repo(repo: str) -> tuple[str, str]:
    parts = repo.split("/")
    if len(parts) != 2:
        raise ValueError(f"Invalid repo format '{repo}', expected 'owner/repo'")
    return parts[0], parts[1]


async def create_issue(
    *,
    title: str,
    body: str,
    labels: list[str],
    repo: Optional[str] = None,
) -> str:
    """Create a GitHub issue and return its HTML URL."""
    target_repo = repo or GITHUB_DEFAULT_REPO
    owner, name = _parse_repo(target_repo)

    payload: dict = {"title": title, "body": body}
    if labels:
        payload["labels"] = labels

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            f"{_BASE}/repos/{owner}/{name}/issues",
            headers=_HEADERS,
            json=payload,
        )
        if resp.status_code == 410:
            raise RuntimeError("Issues are disabled for this repository.")
        resp.raise_for_status()
        url: str = resp.json()["html_url"]
        logger.info("GitHub issue created: %s", url)
        return url
