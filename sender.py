"""
sender.py — Send Instagram posts to a Telegram channel.
Handles photos, videos, and carousel (album) posts.
"""

import asyncio
import logging
import tempfile
import os
from pathlib import Path

import aiohttp
from telegram import Bot, InputMediaPhoto, InputMediaVideo
from telegram.error import TelegramError
from telegram.constants import ParseMode

import config
from scraper import InstagramPost

logger = logging.getLogger(__name__)

MAX_CAPTION_LEN = 1024   # Telegram caption character limit


# ── Caption builder ───────────────────────────────────────────────────────────

def _build_caption(post: InstagramPost) -> str:
    """Format the caption to send alongside the media."""
    caption = post.caption or ""
    # Truncate if needed
    if len(caption) > MAX_CAPTION_LEN - 100:
        caption = caption[: MAX_CAPTION_LEN - 103] + "…"

    credit = f"\n\n📸 <a href=\"{post.permalink}\">@{post.username}</a>"
    return caption + credit


# ── Media downloader ──────────────────────────────────────────────────────────

async def _download(url: str, session: aiohttp.ClientSession, suffix: str) -> str:
    """Download a URL to a temp file and return the file path."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    async with session.get(url) as resp:
        resp.raise_for_status()
        while chunk := await resp.content.read(1 << 16):  # 64 KB chunks
            tmp.write(chunk)
    tmp.close()
    return tmp.name


# ── Sender ────────────────────────────────────────────────────────────────────

async def send_post(bot: Bot, post: InstagramPost):
    """
    Send a single InstagramPost to the configured Telegram channel.
    Cleans up any temp files afterwards.
    """
    channel = config.TELEGRAM_CHANNEL_ID
    caption = _build_caption(post)
    temp_files: list[str] = []

    try:
        async with aiohttp.ClientSession() as session:

            # ── Photo ──────────────────────────────────────────────────────
            if post.media_type == "photo" and post.media_urls:
                path = await _download(post.media_urls[0], session, ".jpg")
                temp_files.append(path)
                with open(path, "rb") as f:
                    await bot.send_photo(
                        chat_id=channel,
                        photo=f,
                        caption=caption,
                        parse_mode=ParseMode.HTML,
                    )

            # ── Video ──────────────────────────────────────────────────────
            elif post.media_type == "video" and post.media_urls:
                path = await _download(post.media_urls[0], session, ".mp4")
                temp_files.append(path)
                
                if os.path.getsize(path) > 49 * 1024 * 1024:
                    logger.warning("Video too large (%.1f MB). Falling back to text.", os.path.getsize(path)/1024/1024)
                    await bot.send_message(
                        chat_id=channel,
                        text=f"🎥 <b>[Video too large for Telegram]</b>\nWatch here: {post.permalink}\n\n{caption}",
                        parse_mode=ParseMode.HTML,
                    )
                else:
                    thumb_path: str | None = None
                    if post.thumbnail_url:
                        thumb_path = await _download(post.thumbnail_url, session, ".jpg")
                        temp_files.append(thumb_path)
                    with open(path, "rb") as f:
                        thumb_file = open(thumb_path, "rb") if thumb_path else None
                        try:
                            await bot.send_video(
                                chat_id=channel,
                                video=f,
                                thumbnail=thumb_file,
                                caption=caption,
                                parse_mode=ParseMode.HTML,
                                supports_streaming=True,
                            )
                        finally:
                            if thumb_file:
                                thumb_file.close()

            # ── Carousel / Album ───────────────────────────────────────────
            elif post.media_type == "carousel" and post.media_urls:
                media_group = []
                too_large = False
                for i, url in enumerate(post.media_urls[:10]):  # Telegram max = 10
                    ext = ".mp4" if "video" in url else ".jpg"
                    path = await _download(url, session, ext)
                    temp_files.append(path)
                    
                    if os.path.getsize(path) > 49 * 1024 * 1024:
                        too_large = True
                        break

                    cap_text = caption if i == 0 else None
                    if ext == ".mp4":
                        media_group.append(
                            InputMediaVideo(
                                media=open(path, "rb"),
                                caption=cap_text,
                                parse_mode=ParseMode.HTML if cap_text else None,
                            )
                        )
                    else:
                        media_group.append(
                            InputMediaPhoto(
                                media=open(path, "rb"),
                                caption=cap_text,
                                parse_mode=ParseMode.HTML if cap_text else None,
                            )
                        )
                
                if too_large:
                    logger.warning("Carousel contains a video too large for Telegram. Falling back to text.")
                    await bot.send_message(
                        chat_id=channel,
                        text=f"🎞 <b>[Album too large for Telegram]</b>\nView here: {post.permalink}\n\n{caption}",
                        parse_mode=ParseMode.HTML,
                    )
                else:
                    await bot.send_media_group(chat_id=channel, media=media_group)

            else:
                logger.warning("Unknown media type '%s' for post %s", post.media_type, post.post_id)

        logger.info("✅ Sent post %s from @%s", post.post_id, post.username)

    except TelegramError as exc:
        logger.error("Telegram error sending post %s: %s", post.post_id, exc)
        raise
    except aiohttp.ClientError as exc:
        logger.error("Download error for post %s: %s", post.post_id, exc)
        raise
    finally:
        # Always clean up temp files
        for p in temp_files:
            try:
                Path(p).unlink(missing_ok=True)
            except OSError:
                pass


async def send_posts(posts: list[InstagramPost]):
    """Send a list of posts, oldest first, with a delay between each."""
    if not posts:
        return

    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    # Send oldest first so the channel timeline looks natural
    for post in reversed(posts):
        try:
            await send_post(bot, post)
        except Exception:
            logger.error("Skipping post %s due to send error.", post.post_id)
        await asyncio.sleep(config.TELEGRAM_SEND_DELAY)
