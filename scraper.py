"""
scraper.py — Fetch recent posts from Instagram public accounts.
Uses instagrapi under the hood, with session persistence to avoid re-logins.
"""

import logging
import time
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from instagrapi import Client
from instagrapi.exceptions import LoginRequired, ClientError, ChallengeRequired

import config

logger = logging.getLogger(__name__)


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class InstagramPost:
    post_id: str
    username: str
    caption: str
    taken_at: datetime                  # timezone-aware UTC
    media_type: str                     # "photo" | "video" | "carousel"
    media_urls: list[str] = field(default_factory=list)   # direct download URLs
    thumbnail_url: Optional[str] = None                   # for videos
    shortcode: str = ""                                    # for building profile link

    @property
    def permalink(self) -> str:
        return f"https://www.instagram.com/p/{self.shortcode}/"


# ── Client singleton ──────────────────────────────────────────────────────────

_client: Optional[Client] = None


def _get_client() -> Client:
    global _client
    if _client is not None:
        return _client

    cl = Client()
    cl.delay_range = [1, 3]  # random delays between requests

    if config.PROXY:
        cl.set_proxy(config.PROXY)

    session_path = Path(config.IG_SESSION_FILE)

    # Try to reuse a saved session first
    if session_path.exists():
        try:
            cl.load_settings(session_path)
            cl.login(config.IG_USERNAME, config.IG_PASSWORD)
            logger.info("Logged in using saved session.")
            _client = cl
            return _client
        except ChallengeRequired:
            _raise_challenge_error()
        except Exception as exc:
            logger.warning("Saved session invalid (%s), re-logging in.", exc)
            session_path.unlink(missing_ok=True)

    # Fresh login
    try:
        cl.login(config.IG_USERNAME, config.IG_PASSWORD)
    except ChallengeRequired:
        _raise_challenge_error()

    cl.dump_settings(session_path)
    logger.info("Logged in fresh and session saved.")
    _client = cl
    return _client


def _raise_challenge_error():
    """
    Instagram requires a security challenge (new IP / device).
    Print a clear, actionable message and exit — no point retrying automatically.
    """
    msg = (
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "❌  Instagram Security Challenge Required\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Instagram blocked the login because it doesn't recognise\n"
        "this server's IP address.\n\n"
        "Fix: copy your local session.json (which Instagram already\n"
        "trusts) to the server:\n\n"
        "  scp /path/to/Insta-to-Telegram/session.json \\\n"
        "      user@YOUR_SERVER:/path/to/Insta-to-Telegram/session.json\n\n"
        "Then re-run the bot on the server.\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    logger.error(msg)
    raise SystemExit(1)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _media_to_post(media, username: str) -> InstagramPost:
    """Convert an instagrapi Media object → our InstagramPost dataclass."""
    taken_at: datetime = media.taken_at
    if taken_at.tzinfo is None:
        taken_at = taken_at.replace(tzinfo=timezone.utc)

    media_type_id = media.media_type  # 1=photo, 2=video, 8=carousel
    media_urls: list[str] = []
    thumbnail_url: Optional[str] = None

    if media_type_id == 1:  # Photo
        kind = "photo"
        media_urls = [str(media.thumbnail_url or "")]
    elif media_type_id == 2:  # Video
        kind = "video"
        media_urls = [str(media.video_url or "")]
        thumbnail_url = str(media.thumbnail_url or "")
    elif media_type_id == 8:  # Carousel / album
        kind = "carousel"
        for resource in media.resources:
            if resource.media_type == 2:
                media_urls.append(str(resource.video_url or ""))
            else:
                media_urls.append(str(resource.thumbnail_url or ""))
    else:
        kind = "unknown"

    caption = media.caption_text or ""

    return InstagramPost(
        post_id=str(media.pk),
        username=username,
        caption=caption,
        taken_at=taken_at,
        media_type=kind,
        media_urls=[u for u in media_urls if u],
        thumbnail_url=thumbnail_url,
        shortcode=media.code or "",
    )


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_recent_posts(username: str, lookback_hours: float = 24) -> list[InstagramPost]:
    """
    Return posts from `username` published within the last `lookback_hours`.
    Returns an empty list on error (logs the exception).
    """
    cl = _get_client()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    try:
        user_id = cl.user_id_from_username(username)
        # Fetch up to 30 recent posts; filter by time
        medias = cl.user_medias(user_id, amount=30)
    except ChallengeRequired:
        _raise_challenge_error()
    except LoginRequired:
        logger.error("Instagram session expired. Clearing session file.")
        global _client
        _client = None
        Path(config.IG_SESSION_FILE).unlink(missing_ok=True)
        return []
    except ClientError as exc:
        logger.error("Instagram client error for @%s: %s", username, exc)
        return []
    except Exception as exc:
        logger.exception("Unexpected error fetching @%s: %s", username, exc)
        return []

    posts: list[InstagramPost] = []
    for media in medias:
        taken_at = media.taken_at

        # Normalize to UTC regardless of whether tzinfo is set
        if taken_at.tzinfo is None:
            # Naive datetime — instagrapi sometimes returns these; assume UTC
            taken_at = taken_at.replace(tzinfo=timezone.utc)
        else:
            # Aware datetime — convert to UTC to be safe
            taken_at = taken_at.astimezone(timezone.utc)

        logger.debug(
            "  post %s taken_at=%s (cutoff=%s) → %s",
            media.pk,
            taken_at.isoformat(),
            cutoff.isoformat(),
            "✅ recent" if taken_at >= cutoff else "❌ too old",
        )

        # Don't break — Instagram's feed order isn't strictly chronological.
        # Use continue so we don't miss a recent post after an older one.
        if taken_at < cutoff:
            continue

        posts.append(_media_to_post(media, username))

    logger.info(
        "Fetched %d post(s) for @%s, %d within the last %.0fh.",
        len(medias),
        username,
        len(posts),
        lookback_hours,
    )
    return posts
