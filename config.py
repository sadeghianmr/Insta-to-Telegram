"""
config.py — Load and validate all environment variables.
No Instagram login required — instaloader scrapes public profiles directly.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Instagram ──────────────────────────────────────────────────────────────────
# Optional: set these to log in and avoid anonymous rate limits.
# Leave blank to scrape public profiles without login.
IG_USERNAME: str = os.getenv("IG_USERNAME", "")
IG_PASSWORD: str = os.getenv("IG_PASSWORD", "")
IG_SESSION_FILE: str = os.getenv("IG_SESSION_FILE", "session.json")

# Comma-separated list of PUBLIC Instagram usernames to monitor
# e.g. "natgeo,nasa,bbcnews"
IG_TARGET_ACCOUNTS: list[str] = [
    acc.strip()
    for acc in os.getenv("IG_TARGET_ACCOUNTS", "").split(",")
    if acc.strip()
]

# ── Telegram ───────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL_ID: str = os.getenv("TELEGRAM_CHANNEL_ID", "")  # e.g. "@mychannel" or "-100xxxxxxxxx"

# ── Scheduler ──────────────────────────────────────────────────────────────────
# How often (in hours) the bot checks for new posts
CHECK_INTERVAL_HOURS: float = float(os.getenv("CHECK_INTERVAL_HOURS", "2"))

# How far back (in hours) to look for recent posts
LOOKBACK_HOURS: float = float(os.getenv("LOOKBACK_HOURS", "24"))

# ── Database ───────────────────────────────────────────────────────────────────
DB_PATH: str = os.getenv("DB_PATH", "seen_posts.db")

# ── Misc ───────────────────────────────────────────────────────────────────────
# Delay (seconds) between Telegram messages to respect rate limits
TELEGRAM_SEND_DELAY: float = float(os.getenv("TELEGRAM_SEND_DELAY", "2"))

# Delay (seconds) between Instagram requests to avoid rate limiting
IG_REQUEST_DELAY: float = float(os.getenv("IG_REQUEST_DELAY", "3"))


def validate():
    """Raise ValueError if required config is missing."""
    missing = []
    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not TELEGRAM_CHANNEL_ID:
        missing.append("TELEGRAM_CHANNEL_ID")
    if not IG_TARGET_ACCOUNTS:
        missing.append("IG_TARGET_ACCOUNTS")
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
