"""
main.py — Entry point for the Instagram → Telegram repost bot.

Runs a scheduled job every CHECK_INTERVAL_HOURS hours.
Can also be run once with:  python main.py --once
"""

import asyncio
import logging
import argparse
import sys
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
from db import init_db, is_seen, mark_seen, cleanup_old_entries
from scraper import fetch_recent_posts
from sender import send_posts

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)
# Show per-post timestamp debug info from the scraper
logging.getLogger("scraper").setLevel(logging.DEBUG)



# ── Core job ──────────────────────────────────────────────────────────────────

async def run_job():
    """Check all target accounts and forward new posts to Telegram."""
    logger.info("=== Job started at %s ===", datetime.now(timezone.utc).isoformat())

    for username in config.IG_TARGET_ACCOUNTS:
        logger.info("Checking @%s …", username)

        posts = fetch_recent_posts(username, lookback_hours=config.LOOKBACK_HOURS)
        new_posts = [p for p in posts if not is_seen(p.post_id)]

        if not new_posts:
            logger.info("No new posts for @%s.", username)
            continue

        logger.info("Sending %d new post(s) from @%s.", len(new_posts), username)
        await send_posts(new_posts)

        # Mark as seen after successful send
        for post in new_posts:
            mark_seen(post.post_id, post.username, post.taken_at)

    # Periodic DB cleanup
    cleanup_old_entries(older_than_hours=72)
    logger.info("=== Job finished ===")


# ── Entry point ───────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="Instagram → Telegram Repost Bot")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run the job once and exit (useful for testing or cron setups)",
    )
    args = parser.parse_args()

    # Validate config
    try:
        config.validate()
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        sys.exit(1)

    # Init DB
    init_db()

    if args.once:
        logger.info("Running in one-shot mode.")
        await run_job()
        return

    # Scheduler mode
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_job,
        trigger="interval",
        hours=config.CHECK_INTERVAL_HOURS,
        next_run_time=datetime.now(timezone.utc),  # Run immediately on start
    )
    scheduler.start()
    logger.info(
        "Scheduler started. Checking every %.1f hour(s). Press Ctrl+C to stop.",
        config.CHECK_INTERVAL_HOURS,
    )

    try:
        # Keep the event loop alive
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
