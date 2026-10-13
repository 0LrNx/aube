#!/usr/bin/env python3
"""
standup.py
Fetches your tickets + PRs from the last 24h (whichever stack you configured
via `python install.py`) and prints a ready-to-paste standup message.

Usage:
    python standup.py            # compose and post
    python standup.py --review   # drop items, add today's work / blockers, confirm before posting

Scheduling: see the README (cron on macOS/Linux, Task Scheduler on Windows).
Exits with code 1, without posting, if any ticket/PR/review source fails.
"""

import argparse
import os
import sys
from datetime import datetime

from providers.factory import build_code_provider, build_notifier, build_ticket_provider, required_env
from standup_core.builder import build_standup
from standup_core.logo import render as render_logo
from standup_core.review import review


def _load_env(env_path: str | None = None) -> None:
    env_path = env_path or os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
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
                # Variables already set in the environment win over .env, like python-dotenv / docker.
                os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


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


def _lookback_days() -> int:
    """Return 3 on Monday (to cover Fri→Mon), 1 otherwise."""
    return 3 if datetime.now().weekday() == 0 else 1


def _enable_ansi_on_windows() -> bool:
    """Turn on ANSI escape support in the Windows console; return False if it can't be enabled."""
    if os.name != "nt":
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        return False


def _print_logo() -> None:
    # Only for a human at a terminal: keep piped output, cron logs and tests free of the banner.
    if not sys.stdout.isatty():
        return
    color = "NO_COLOR" not in os.environ and _enable_ansi_on_windows()
    print(render_logo(color=color) + "\n")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compose your daily standup and post it.")
    parser.add_argument(
        "--review",
        action="store_true",
        help="review before posting: drop items, add today's work and blockers, then confirm",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.review and not sys.stdin.isatty():
        print("--review needs an interactive terminal (it asks questions); run it without --review here.",
              file=sys.stderr)
        return 2

    _load_env()
    _validate_env()
    _print_logo()

    tickets = build_ticket_provider(os.environ)
    code = build_code_provider(os.environ)
    notifier = build_notifier(os.environ)
    days = _lookback_days()
    failures = []

    print("Fetching tickets...")
    try:
        issues = tickets.fetch_issues(days)
        print(f"  {len(issues)} issues updated in last {days * 24}h")
    except Exception as e:
        failures.append(f"tickets: {e}")
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
        failures.append(f"pull requests: {e}")
        prs = {"merged": [], "opened": []}

    print("Fetching reviews...")
    try:
        reviews = code.fetch_reviews(days)
        print(f"  {len(reviews)} reviewed")
    except Exception as e:
        failures.append(f"reviews: {e}")
        reviews = []

    standup = build_standup(issues, prs["merged"], prs["opened"], reviews, fmt=notifier.message_format)

    print("\n" + "─" * 50)
    print(standup)
    print("─" * 50)

    # A partial standup would silently claim "nothing completed": show it, but don't post it.
    if failures:
        print("\nStandup NOT posted — some sources failed:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    if args.review:
        try:
            reviewed = review(
                issues, prs["merged"], prs["opened"], reviews,
                ask=input, show=print, fmt=notifier.message_format, destination=notifier.destination,
            )
        except (KeyboardInterrupt, EOFError):
            # Ctrl+C / Ctrl+Z: a deliberate abort, not a crash. 130 is the usual "interrupted" exit code.
            print("\nCancelled — standup not posted.")
            return 130
        if reviewed is None:
            print("Standup not posted (cancelled during review).")
            return 0
        standup = reviewed

    try:
        notifier.post(standup)
    except Exception as e:
        print(f"\nStandup NOT posted — {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
