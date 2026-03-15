"""
scraper.py — Fetch recent posts from Instagram public accounts.
Uses instaloader with optional login for better rate-limit resilience.
"""

import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import instaloader

import config

logger = logging.getLogger(__name__)


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class InstagramPost:
    post_id: str
    username: str
    caption: str
    taken_at: datetime                # timezone-aware UTC
    media_type: str                   # "photo" | "video" | "carousel"
    media_urls: list[str] = field(default_factory=list)
    thumbnail_url: Optional[str] = None
    shortcode: str = ""

    @property
    def permalink(self) -> str:
        return f"https://www.instagram.com/p/{self.shortcode}/"


# ── Loader singleton ──────────────────────────────────────────────────────────

_loader: Optional[instaloader.Instaloader] = None


def _get_loader() -> instaloader.Instaloader:
    global _loader
    if _loader is not None:
        return _loader

    L = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        quiet=True,
        sleep=True,
        max_connection_attempts=3,
    )

    session_file = Path(config.IG_SESSION_FILE) if config.IG_USERNAME else None

    if config.IG_USERNAME and config.IG_PASSWORD:
        # Try loading a saved session first
        if session_file and session_file.exists():
            try:
                L.load_session_from_file(config.IG_USERNAME, session_file)
                logger.info("Instaloader: loaded saved session for @%s.", config.IG_USERNAME)
                _loader = L
                return _loader
            except Exception as exc:
                logger.warning("Could not load saved session: %s. Logging in fresh.", exc)

        # Fresh login
        try:
            L.login(config.IG_USERNAME, config.IG_PASSWORD)
            logger.info("Instaloader: logged in as @%s.", config.IG_USERNAME)
            if session_file:
                L.save_session_to_file(session_file)
                logger.info("Session saved to %s.", session_file)
        except instaloader.exceptions.BadCredentialsException:
            logger.error(
                "Bad Instagram credentials. Check IG_USERNAME/IG_PASSWORD in .env."
            )
            sys.exit(1)
        except instaloader.exceptions.TwoFactorAuthRequiredException:
            code = input(
                f"\n🔑  2FA code required for @{config.IG_USERNAME}: "
            ).strip()
            L.two_factor_login(code)
            if session_file:
                L.save_session_to_file(session_file)
        except Exception as exc:
            logger.warning(
                "Instagram login failed (%s). Proceeding without login "
                "(may hit rate limits sooner).",
                exc,
            )
    else:
        logger.info("Instaloader initialised (no login — public profiles only).")

    _loader = L
    return _loader


# ── Post converter ────────────────────────────────────────────────────────────

def _post_to_dataclass(post: instaloader.Post, username: str) -> InstagramPost:
    taken_at = post.date_utc.replace(tzinfo=timezone.utc)

    media_urls: list[str] = []
    thumbnail_url: Optional[str] = None

    if post.is_video:
        kind = "video"
        media_urls = [post.video_url]
        thumbnail_url = post.url
    elif post.typename == "GraphSidecar":
        kind = "carousel"
        for node in post.get_sidecar_nodes():
            if node.is_video:
                media_urls.append(node.video_url)
            else:
                media_urls.append(node.display_url)
    else:
        kind = "photo"
        media_urls = [post.url]

    return InstagramPost(
        post_id=post.shortcode,
        username=username,
        caption=post.caption or "",
        taken_at=taken_at,
        media_type=kind,
        media_urls=[u for u in media_urls if u],
        thumbnail_url=thumbnail_url,
        shortcode=post.shortcode,
    )


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_recent_posts(username: str, lookback_hours: float = 24) -> list[InstagramPost]:
    """
    Return posts from `username` published within the last `lookback_hours`.
    Returns an empty list on error (logs the exception).
    """
    L = _get_loader()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    try:
        profile = instaloader.Profile.from_username(L.context, username)
    except instaloader.exceptions.ProfileNotExistsException:
        logger.error("Instagram profile @%s does not exist.", username)
        return []
    except instaloader.exceptions.ConnectionException as exc:
        logger.error("Connection error fetching @%s: %s", username, exc)
        return []
    except Exception as exc:
        logger.exception("Unexpected error loading profile @%s: %s", username, exc)
        return []

    posts: list[InstagramPost] = []
    try:
        for post in profile.get_posts():
            taken_at = post.date_utc.replace(tzinfo=timezone.utc)

            logger.debug(
                "  post %s taken_at=%s → %s",
                post.shortcode,
                taken_at.isoformat(),
                "✅ recent" if taken_at >= cutoff else "❌ too old",
            )

            # Stop scanning once we're 2× the lookback window in the past
            if taken_at < cutoff - timedelta(hours=lookback_hours):
                break

            if taken_at < cutoff:
                continue

            posts.append(_post_to_dataclass(post, username))
            time.sleep(config.IG_REQUEST_DELAY)

    except instaloader.exceptions.ConnectionException as exc:
        logger.error("Connection error while reading posts for @%s: %s", username, exc)
    except Exception as exc:
        logger.exception("Unexpected error reading posts for @%s: %s", username, exc)

    logger.info(
        "Fetched posts for @%s, %d within the last %.0fh.",
        username,
        len(posts),
        lookback_hours,
    )
    return posts
