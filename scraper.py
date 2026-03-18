"""
scraper.py — Fetch recent posts using Instaloader.
No Instagram login required for public profiles.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
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
    taken_at: datetime                  # timezone-aware UTC
    media_type: str                     # "photo" | "video" | "carousel" | "unknown"
    media_urls: list[str] = field(default_factory=list)   # direct download URLs
    thumbnail_url: Optional[str] = None                   # for videos
    permalink: str = ""                                   # link to post


# ── Initialization ────────────────────────────────────────────────────────────

def _get_loader() -> instaloader.Instaloader:
    """Return a configured Instaloader instance (anonymous mode)."""
    L = instaloader.Instaloader(
        download_pictures=False,
        download_video_thumbnails=False,
        download_videos=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
    )
    
    # Optional: If you want to configure proxy, do so here
    # L.context._session.proxies = {"http": config.PROXY, "https": config.PROXY}
    
    return L


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_recent_posts(username: str, lookback_hours: float = 24) -> list[InstagramPost]:
    """
    Return posts from `username` published within the last `lookback_hours`.
    Returns an empty list on error.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    
    logger.info("Fetching public profile for @%s (Instaloader)", username)
    L = _get_loader()
    
    try:
        profile = instaloader.Profile.from_username(L.context, username)
        # Sleep slightly to avoid blasting Instagram
        time.sleep(config.IG_REQUEST_DELAY)
    except instaloader.exceptions.ProfileNotExistsException:
        logger.error("Profile @%s does not exist or is private/blocked.", username)
        return []
    except Exception as exc:
        logger.exception("Failed to fetch profile @%s: %s", username, exc)
        return []

    posts: list[InstagramPost] = []
    
    logger.debug("Scanning posts for @%s…", username)
    try:
        count = 0
        for post in profile.get_posts():
            # Respect delay between post iterations if needed (Instaloader handles some internally)
            
            # taken_at is already UTC from instaloader
            taken_at = post.date_utc.replace(tzinfo=timezone.utc)
            
            logger.debug(
                "  post %s taken_at=%s (cutoff=%s)",
                post.shortcode,
                taken_at.isoformat(),
                cutoff.isoformat(),
            )

            # Instaloader iterates from newest to oldest. 
            # If we hit a post older than cutoff, we can stop asking for more.
            # (Note: Pinned posts might mess this up, so we skip them instead of breaking)
            if taken_at < cutoff:
                if count > 5: # ensure we check past any pinned posts
                    logger.debug("  → Reached an old post (%s < %s), stopping.", taken_at, cutoff)
                    break
                else:
                    logger.debug("  → Post too old, skipping (might be pinned).")
                    count += 1
                    continue

            # Figure out media type and URLs
            # instaloader post.typename is typically GraphImage, GraphVideo, GraphSidecar
            media_urls = []
            thumbnail_url = None
            
            if post.typename == 'GraphVideo':
                media_type = "video"
                media_urls.append(post.video_url)
                thumbnail_url = post.url
            elif post.typename == 'GraphSidecar':
                media_type = "carousel"
                # To get slide URLs, we have to iterate post.get_sidecar_nodes()
                for node in post.get_sidecar_nodes():
                    if node.is_video:
                        media_urls.append(node.video_url)
                    else:
                        media_urls.append(node.display_url)
            else:
                # GraphImage or anything else
                media_type = "photo"
                media_urls.append(post.url)

            p = InstagramPost(
                post_id=post.shortcode,
                username=username,
                caption=post.caption or "",
                taken_at=taken_at,
                media_type=media_type,
                media_urls=media_urls,
                thumbnail_url=thumbnail_url,
                permalink=f"https://www.instagram.com/p/{post.shortcode}/",
            )
            posts.append(p)
            count += 1
            
            # Small delay to keep Instagram happy while paginating
            time.sleep(1)

    except Exception as exc:
        logger.exception("Error while iterating posts for @%s: %s", username, exc)

    logger.info(
        "Found %d post(s) for @%s within the last %.0fh.",
        len(posts),
        username,
        lookback_hours,
    )
    
    return posts
