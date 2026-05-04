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


async def get_issue(*, repo: Optional[str] = None, number: int) -> dict:
    """Fetch issue data from GitHub."""
    target_repo = repo or GITHUB_DEFAULT_REPO
    owner, name = _parse_repo(target_repo)
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{_BASE}/repos/{owner}/{name}/issues/{number}",
            headers=_HEADERS,
        )
        resp.raise_for_status()
        return resp.json()


async def add_comment(*, repo: Optional[str] = None, number: int, body: str) -> str:
    """Add a comment to an issue. Returns the comment URL."""
    target_repo = repo or GITHUB_DEFAULT_REPO
    owner, name = _parse_repo(target_repo)
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            f"{_BASE}/repos/{owner}/{name}/issues/{number}/comments",
            headers=_HEADERS,
            json={"body": body},
        )
        resp.raise_for_status()
        url: str = resp.json()["html_url"]
        logger.info("GitHub comment added: %s", url)
        return url


async def close_issue(*, repo: Optional[str] = None, number: int) -> None:
    """Close a GitHub issue."""
    target_repo = repo or GITHUB_DEFAULT_REPO
    owner, name = _parse_repo(target_repo)
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.patch(
            f"{_BASE}/repos/{owner}/{name}/issues/{number}",
            headers=_HEADERS,
            json={"state": "closed", "state_reason": "completed"},
        )
        resp.raise_for_status()
        logger.info("GitHub issue #%s closed", number)


async def reopen_issue(*, repo: Optional[str] = None, number: int) -> None:
    """Reopen a closed GitHub issue."""
    target_repo = repo or GITHUB_DEFAULT_REPO
    owner, name = _parse_repo(target_repo)
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.patch(
            f"{_BASE}/repos/{owner}/{name}/issues/{number}",
            headers=_HEADERS,
            json={"state": "open"},
        )
        resp.raise_for_status()
        logger.info("GitHub issue #%s reopened", number)


async def update_issue(
    *,
    repo: Optional[str] = None,
    number: int,
    title: Optional[str] = None,
    body: Optional[str] = None,
    labels: Optional[list[str]] = None,
) -> None:
    """Update issue fields. Only provided fields are changed."""
    target_repo = repo or GITHUB_DEFAULT_REPO
    owner, name = _parse_repo(target_repo)
    payload: dict = {}
    if title is not None:
        payload["title"] = title
    if body is not None:
        payload["body"] = body
    if labels is not None:
        payload["labels"] = labels
    if not payload:
        return
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.patch(
            f"{_BASE}/repos/{owner}/{name}/issues/{number}",
            headers=_HEADERS,
            json=payload,
        )
        resp.raise_for_status()
        logger.info("GitHub issue #%s updated: %s", number, list(payload.keys()))


async def search_issues(
    *,
    repo: Optional[str] = None,
    query: str,
    state: str = "open",
) -> list[dict]:
    """Search issues in the repo. Returns up to 100 results."""
    target_repo = repo or GITHUB_DEFAULT_REPO
    qualifiers = [f"repo:{target_repo}", "is:issue"]
    if state in {"open", "closed"}:
        qualifiers.append(f"state:{state}")
    q = " ".join(([query] if query else []) + qualifiers)
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{_BASE}/search/issues",
            headers=_HEADERS,
            params={"q": q, "per_page": 100},
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
    return [
        {
            "number": i["number"],
            "title": i["title"],
            "state": i["state"],
            "url": i["html_url"],
        }
        for i in items
    ]


async def list_issues(
    *,
    repo: Optional[str] = None,
    state: str = "open",
) -> list[dict]:
    """List repo issues by state. Returns up to 100 issues, excluding pull requests."""
    target_repo = repo or GITHUB_DEFAULT_REPO
    owner, name = _parse_repo(target_repo)
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{_BASE}/repos/{owner}/{name}/issues",
            headers=_HEADERS,
            params={"state": state, "per_page": 100},
        )
        resp.raise_for_status()
        items = resp.json()
    return [
        {
            "number": i["number"],
            "title": i["title"],
            "state": i["state"],
            "url": i["html_url"],
        }
        for i in items
        if "pull_request" not in i
    ]
