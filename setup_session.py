"""
setup_session.py — One-time interactive script to create a trusted session.json.

Run this ONCE on your local machine (not the server) to go through any
Instagram security challenges (email/SMS code). Once session.json is saved,
copy it to the server with:

    scp session.json ubuntu@YOUR_SERVER:/home/ubuntu/Insta-to-Telegram/session.json
"""

import sys
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from instagrapi import Client
from instagrapi.exceptions import (
    BadPassword,
    ChallengeRequired,
    FeedbackRequired,
    LoginRequired,
    TwoFactorRequired,
)
import config


def challenge_code_handler(username: str, choice) -> str:
    """Called by instagrapi when Instagram sends a verification code."""
    print(f"\n📧  Instagram sent a verification code to: {choice}")
    code = input("   → Enter the code here: ").strip()
    return code


def change_password_handler(username: str) -> str:
    """Called if Instagram forces a password re-entry."""
    import getpass
    print(f"\n🔒  Instagram is asking to re-confirm your password for @{username}")
    return getpass.getpass("   → Enter password: ")


def main():
    session_path = Path(config.IG_SESSION_FILE)

    print("=" * 55)
    print("  Instagram Session Setup")
    print("=" * 55)
    print(f"  Account  : @{config.IG_USERNAME}")
    print(f"  Session  : {session_path}")
    print("=" * 55)

    # Delete stale/flagged session if it exists
    if session_path.exists():
        print(f"\n⚠️  Deleting old session: {session_path}")
        session_path.unlink()

    cl = Client()
    cl.delay_range = [1, 3]

    # Register our handlers so instagrapi can prompt us interactively
    cl.challenge_code_handler = challenge_code_handler
    cl.change_password_handler = change_password_handler

    if config.PROXY:
        cl.set_proxy(config.PROXY)

    print("\n🔐  Logging in to Instagram…")

    try:
        cl.login(config.IG_USERNAME, config.IG_PASSWORD)

    except BadPassword:
        print("\n❌  Wrong password. Double-check IG_PASSWORD in your .env file.")
        sys.exit(1)

    except TwoFactorRequired:
        print("\n🔑  Two-factor authentication is enabled on this account.")
        code = input("   → Enter your 2FA code: ").strip()
        try:
            cl.login(config.IG_USERNAME, config.IG_PASSWORD, verification_code=code)
        except Exception as exc:
            print(f"\n❌  2FA login failed: {exc}")
            sys.exit(1)

    except ChallengeRequired:
        print("\n⚠️  Instagram requires a security challenge.")
        print("   instagrapi will now try to resolve it automatically…")
        try:
            cl.challenge_resolve(cl.last_json)
        except Exception as exc:
            print(f"\n❌  Automatic challenge resolution failed: {exc}")
            print(
                "\n   Manual steps:\n"
                "   1. Open Instagram on your phone\n"
                "   2. Complete any security prompts\n"
                "   3. Run this script again"
            )
            sys.exit(1)

    except FeedbackRequired:
        msg = cl.last_json.get("feedback_message", "No details available.")
        print(f"\n❌  Instagram rejected the login: {msg}")
        print("   This usually means the account is temporarily restricted.")
        print("   Wait a few hours and try again, or use a different account.")
        sys.exit(1)

    except Exception as exc:
        print(f"\n❌  Unexpected error: {exc}")
        sys.exit(1)

    # ── Success ───────────────────────────────────────────────────────────────
    cl.dump_settings(session_path)

    # Verify the session works
    print("\n✅  Logged in successfully! Verifying session…")
    try:
        info = cl.account_info()
        print(f"   Verified as: @{info.username} ({info.full_name})")
    except Exception as exc:
        print(f"   ⚠️  Could not verify account info: {exc}")

    print(f"\n💾  Session saved to: {session_path}")
    print("\nNext steps:")
    print("  • Run locally:   python main.py --once")
    print("  • Copy to server:")
    print(f"    scp {session_path} ubuntu@YOUR_SERVER:/home/ubuntu/Insta-to-Telegram/session.json")
    print("=" * 55)


if __name__ == "__main__":
    main()
