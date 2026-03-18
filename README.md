# 📸 Instagram → Telegram Repost Bot

Automatically reposts recent (last 24 h) Instagram public account posts to your Telegram channel — supports **photos**, **videos**, and **carousel albums**.

---

## 📁 Project Structure

```text
Insta-to-Telegram/
├── config.py          # Environment variable loading & validation
├── db.py              # SQLite deduplication tracker
├── scraper.py         # Instagram fetching via Instaloader (anonymous)
├── sender.py          # Telegram message sending (async)
├── main.py            # Scheduler & entry point
├── .env.example       # Config template → copy to .env
├── requirements.txt   # Python dependencies
└── .gitignore
```

---

## ⚙️ Setup

### 1. Clone & install dependencies

```bash
cd Insta-to-Telegram
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Create your `.env` file

```bash
cp .env.example .env
```

Then open `.env` and fill in:

| Variable | Description |
|---|---|
| `IG_REQUEST_DELAY` | Seconds to wait between scrapes to avoid blocks (Default: 5) |
| `IG_TARGET_ACCOUNTS` | Comma-separated list of accounts to monitor |
| `TELEGRAM_BOT_TOKEN` | Token from [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHANNEL_ID` | Your channel `@username` or numeric ID |

> **Tip:** Instaloader scrapes public profiles anonymously. You do not need an Instagram account or password for this to work!

### 3. Add the bot to your Telegram channel
In Telegram → your channel → Admins → add your bot with **Post Messages** permission.

---

## 🚀 Running the Bot

### Continuous mode (recommended)
Checks for new posts every `CHECK_INTERVAL_HOURS` (default: every 2 hours):

```bash
python main.py
```

### One-shot mode (for testing or cron)
Runs once and exits:

```bash
python main.py --once
```

### Cron example (every 2 hours)
```cron
0 */2 * * * /path/to/.venv/bin/python /path/to/main.py --once >> /path/to/bot.log 2>&1
```

---

## 🔧 Configuration Reference

All settings live in `.env`:

| Variable | Default | Description |
|---|---|---|
| `CHECK_INTERVAL_HOURS` | `2` | How often to check (hours) |
| `LOOKBACK_HOURS` | `24` | How far back to look for posts |
| `TELEGRAM_SEND_DELAY` | `2` | Delay (sec) between Telegram messages |
| `IG_REQUEST_DELAY` | `5` | Delay (sec) between Instagram requests |
| `PROXY` | _(none)_ | Optional HTTP proxy for Instagram |
| `DB_PATH` | `seen_posts.db` | SQLite database file location |

---

## ⚠️ Important Notes

- **Anonymous Scraping**: Because this bot does not log in, it can only see **public** Instagram accounts.
- **Rate Limiting**: Even without logging in, Instagram may temporarily block your IP if you refresh too often. Keep `CHECK_INTERVAL_HOURS` at 2 or higher, and `IG_REQUEST_DELAY` at 5+ seconds.
- **Telegram limits**: The bot API supports files up to **50 MB**. Very large videos may fail — the bot will log the error and continue.
- **Carousel albums**: Only the first 10 items are sent (Telegram's `sendMediaGroup` limit).

---

## 📜 Logs

The bot writes logs to both the console and `bot.log` in the project directory.

```bash
tail -f bot.log
```
