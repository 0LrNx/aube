#!/usr/bin/env python3
"""
standup.py
Fetches your tickets + PRs from the last 24h (whichever stack you configured
via `python install.py`) and prints a ready-to-paste standup message.

Usage:
    python standup.py

Cron (every weekday at 8am):
    0 8 * * 1-5 cd /path/to/script && python standup.py | pbcopy
    (pbcopy = copies to clipboard on macOS, use xclip on Linux)
"""

import os
import sys
from datetime import datetime

from providers.factory import build_code_provider, build_notifier, build_ticket_provider, required_env
from standup_core.builder import build_standup


def _load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    try:
        f = open(env_path, encoding="utf-8")
    except FileNotFoundError:
        return
    with f:
        for line in f:
            line = line.strip()
            if line.startswith("export "):
                line = line[7:]
            if "=" in line and not line.startswith("#"):
                key, _, val = line.partition("=")
                os.environ[key.strip()] = val.strip().strip('"').strip("'")


_load_env()


def _validate_env() -> None:
    missing = [key for key in required_env(os.environ) if not os.environ.get(key, "").strip()]
    if not missing:
        return
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    print("Missing required environment variables:", ", ".join(missing), file=sys.stderr)
    if not os.path.exists(env_path):
        print("\nNo .env file found. Run the interactive installer:", file=sys.stderr)
        print("  python install.py", file=sys.stderr)
        print("...or configure by hand:", file=sys.stderr)
        print("  cp .env.example .env", file=sys.stderr)
    else:
        print(f"\nFill in the missing values in {env_path}", file=sys.stderr)
    sys.exit(1)


_validate_env()


def _lookback_days() -> int:
    """Return 3 on Monday (to cover Fri→Mon), 1 otherwise."""
    return 3 if datetime.now().weekday() == 0 else 1


def main():
    tickets = build_ticket_provider(os.environ)
    code = build_code_provider(os.environ)
    notifier = build_notifier(os.environ)
    days = _lookback_days()

    print("Fetching tickets...")
    try:
        issues = tickets.fetch_issues(days)
        print(f"  {len(issues)} issues updated in last {days * 24}h")
    except Exception as e:
        print(f"  Ticket source error: {e}")
        issues = []

    print("Checking code provider credentials...")
    try:
        code.validate_credentials()
    except Exception as e:
        print(f"  Code provider credential error: {e}")

    print("Fetching PRs...")
    try:
        prs = code.fetch_prs(days)
        print(f"  {len(prs['merged'])} merged, {len(prs['opened'])} opened")
    except Exception as e:
        print(f"  PR fetch error: {e}")
        prs = {"merged": [], "opened": []}

    print("Fetching reviews...")
    try:
        reviews = code.fetch_reviews(days)
        print(f"  {len(reviews)} reviewed")
    except Exception as e:
        print(f"  Review fetch error: {e}")
        reviews = []

    standup = build_standup(issues, prs["merged"], prs["opened"], reviews)

    print("\n" + "─" * 50)
    print(standup)
    print("─" * 50)

    notifier.post(standup)


if __name__ == "__main__":
    main()
