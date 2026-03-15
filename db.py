"""
db.py — SQLite database for tracking already-posted Instagram posts.
Prevents duplicate reposts even across bot restarts.
"""

import sqlite3
import logging
from datetime import datetime, timezone, timedelta
from config import DB_PATH

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS seen_posts (
                post_id     TEXT PRIMARY KEY,
                username    TEXT NOT NULL,
                posted_at   TEXT NOT NULL,        -- ISO-8601 UTC
                sent_at     TEXT NOT NULL          -- when we forwarded it
            )
        """)
        conn.commit()
    logger.info("Database initialised at %s", DB_PATH)


def is_seen(post_id: str) -> bool:
    """Return True if this post has already been sent to Telegram."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM seen_posts WHERE post_id = ?", (post_id,)
        ).fetchone()
    return row is not None


def mark_seen(post_id: str, username: str, posted_at: datetime):
    """Record that a post has been forwarded."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO seen_posts (post_id, username, posted_at, sent_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                post_id,
                username,
                posted_at.isoformat(),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
    logger.debug("Marked post %s (%s) as seen.", post_id, username)


def cleanup_old_entries(older_than_hours: int = 72):
    """
    Remove entries older than `older_than_hours` to keep the DB small.
    Run this periodically (e.g., once a day).
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=older_than_hours)).isoformat()
    with get_connection() as conn:
        deleted = conn.execute(
            "DELETE FROM seen_posts WHERE sent_at < ?", (cutoff,)
        ).rowcount
        conn.commit()
    if deleted:
        logger.info("Cleaned up %d old DB entries.", deleted)
