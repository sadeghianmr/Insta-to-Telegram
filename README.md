# 📸 Instagram → Telegram Repost Bot

Automatically reposts recent (last 24 h) Instagram public account posts to your Telegram channel — supports **photos**, **videos**, and **carousel albums**.

---

## 📁 Project Structure

```
Insta-to-Telegram/
├── config.py          # Environment variable loading & validation
├── db.py              # SQLite deduplication tracker
├── scraper.py         # Instagram scraping (instagrapi)
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
| `IG_USERNAME` | Your Instagram login username |
| `IG_PASSWORD` | Your Instagram login password |
| `IG_TARGET_ACCOUNTS` | Comma-separated list of accounts to monitor |
| `TELEGRAM_BOT_TOKEN` | Token from [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHANNEL_ID` | Your channel `@username` or numeric ID |

> **Tip:** Use a dedicated Instagram account for scraping to protect your main account.

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

- **Instagram scraping**: Instagram may temporarily restrict accounts that make many requests. Use delays, and consider using a dedicated account + a residential proxy if you monitor many accounts.
- **Session persistence**: The bot saves your Instagram session to `session.json` to avoid re-logging in on each run. This file contains sensitive credentials — keep it private!
- **Telegram limits**: The bot API supports files up to **50 MB**. Very large videos may fail — the bot will log the error and continue.
- **Carousel albums**: Only the first 10 items are sent (Telegram's `sendMediaGroup` limit).

---

## 📜 Logs

The bot writes logs to both the console and `bot.log` in the project directory.

```bash
tail -f bot.log
```
