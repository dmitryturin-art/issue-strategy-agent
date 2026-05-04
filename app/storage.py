import json
import sqlite3
import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

from app.config import DATABASE_PATH

logger = logging.getLogger(__name__)


@contextmanager
def _conn():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                platform            TEXT    NOT NULL DEFAULT 'telegram',
                chat_id             INTEGER NOT NULL,
                source_message_id   INTEGER NOT NULL,
                reply_message_id    INTEGER,
                preview_message_id  INTEGER,
                author_id           INTEGER NOT NULL,
                author_username     TEXT,
                repo                TEXT    NOT NULL,
                title               TEXT,
                body                TEXT,
                labels_json         TEXT    DEFAULT '[]',
                status              TEXT    NOT NULL DEFAULT 'preview',
                github_issue_url    TEXT,
                created_at          TEXT    NOT NULL,
                updated_at          TEXT    NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_source
            ON tasks(chat_id, source_message_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_preview_msg
            ON tasks(chat_id, preview_message_id)
        """)
    logger.info("Database initialized at %s", DATABASE_PATH)


def get_task_by_source(chat_id: int, source_message_id: int) -> Optional[sqlite3.Row]:
    with _conn() as conn:
        return conn.execute(
            "SELECT * FROM tasks WHERE chat_id=? AND source_message_id=? LIMIT 1",
            (chat_id, source_message_id),
        ).fetchone()


def get_task_by_preview_msg(chat_id: int, preview_message_id: int) -> Optional[sqlite3.Row]:
    with _conn() as conn:
        return conn.execute(
            "SELECT * FROM tasks WHERE chat_id=? AND preview_message_id=? LIMIT 1",
            (chat_id, preview_message_id),
        ).fetchone()


def create_task(
    *,
    chat_id: int,
    source_message_id: int,
    reply_message_id: Optional[int],
    preview_message_id: int,
    author_id: int,
    author_username: Optional[str],
    repo: str,
    title: str,
    body: str,
    labels: list[str],
) -> int:
    now = datetime.utcnow().isoformat()
    with _conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO tasks
              (chat_id, source_message_id, reply_message_id, preview_message_id,
               author_id, author_username, repo, title, body, labels_json,
               status, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                chat_id,
                source_message_id,
                reply_message_id,
                preview_message_id,
                author_id,
                author_username,
                repo,
                title,
                body,
                json.dumps(labels, ensure_ascii=False),
                "preview",
                now,
                now,
            ),
        )
        return cur.lastrowid


def update_task_preview(
    task_id: int,
    *,
    title: str,
    body: str,
    labels: list[str],
    preview_message_id: int,
) -> None:
    now = datetime.utcnow().isoformat()
    with _conn() as conn:
        conn.execute(
            """
            UPDATE tasks
            SET title=?, body=?, labels_json=?, preview_message_id=?, updated_at=?
            WHERE id=?
            """,
            (title, body, json.dumps(labels, ensure_ascii=False), preview_message_id, now, task_id),
        )


def mark_task_created(task_id: int, github_issue_url: str) -> None:
    now = datetime.utcnow().isoformat()
    with _conn() as conn:
        conn.execute(
            "UPDATE tasks SET status='created', github_issue_url=?, updated_at=? WHERE id=?",
            (github_issue_url, now, task_id),
        )
