#!/usr/bin/env python3
"""
standup.py
Fetches your Linear tickets + GitHub PRs from the last 24h
and prints a ready-to-paste standup message.

Usage:
    python standup.py

Cron (every weekday at 9am):
    0 9 * * 1-5 cd /path/to/script && python standup.py | pbcopy
    (pbcopy = copies to clipboard on macOS, use xclip on Linux)
"""

import os
from datetime import datetime, timedelta, timezone

import requests


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

# ── Config ────────────────────────────────────────────────────────────────────
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_USERNAME = os.environ["GITHUB_USERNAME"]
LINEAR_TOKEN = os.environ["LINEAR_TOKEN"]
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
# ──────────────────────────────────────────────────────────────────────────────

GH_HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}


def _github_token_scopes() -> set[str]:
    resp = requests.get("https://api.github.com/user", headers=GH_HEADERS, timeout=15)
    resp.raise_for_status()
    raw = resp.headers.get("X-OAuth-Scopes", "")
    return {scope.strip() for scope in raw.split(",") if scope.strip()}


def _validate_github_token() -> None:
    scopes = _github_token_scopes()
    if "repo" in scopes:
        return
    print(
        "WARNING: GITHUB_TOKEN is missing the 'repo' scope "
        f"(current scopes: {', '.join(sorted(scopes)) or 'none'}). "
        "GitHub PRs and code reviews will be empty. "
        "Regenerate a classic token with 'repo' at "
        "https://github.com/settings/tokens"
    )


def _lookback_days() -> int:
    """Return 3 on Monday (to cover Fri→Mon), 1 otherwise."""
    return 3 if datetime.now().weekday() == 0 else 1


# ── GitHub ────────────────────────────────────────────────────────────────────


def fetch_yesterday_prs() -> dict:
    since = (datetime.now() - timedelta(days=_lookback_days())).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")

    merged_url = (
        f"https://api.github.com/search/issues"
        f"?q=author:{GITHUB_USERNAME}+type:pr+merged:{since}..{today}"
        f"&per_page=20"
    )
    opened_url = (
        f"https://api.github.com/search/issues"
        f"?q=author:{GITHUB_USERNAME}+type:pr+created:{since}..{today}"
        f"&per_page=20"
    )

    merged = requests.get(merged_url, headers=GH_HEADERS).json().get("items", [])
    opened = requests.get(opened_url, headers=GH_HEADERS).json().get("items", [])

    return {"merged": merged, "opened": opened}


def fetch_reviews() -> list[dict]:
    since = (datetime.now() - timedelta(days=_lookback_days())).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")

    url = (
        f"https://api.github.com/search/issues"
        f"?q=reviewed-by:{GITHUB_USERNAME}+-author:{GITHUB_USERNAME}+type:pr+updated:{since}..{today}"
        f"&per_page=20"
    )
    resp = requests.get(url, headers=GH_HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json().get("items", [])


# ── Linear ────────────────────────────────────────────────────────────────────

LINEAR_QUERY = """
query MyIssues($updatedAt: DateTimeOrDuration) {
  viewer {
    assignedIssues(
      filter: { updatedAt: { gt: $updatedAt } }
      orderBy: updatedAt
    ) {
      nodes {
        identifier
        title
        url
        state { name type }
        updatedAt
      }
    }
  }
}
"""


def fetch_linear_issues() -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=_lookback_days())).isoformat()
    resp = requests.post(
        "https://api.linear.app/graphql",
        headers={
            "Authorization": LINEAR_TOKEN,
            "Content-Type": "application/json",
        },
        json={"query": LINEAR_QUERY, "variables": {"updatedAt": since}},
    )
    resp.raise_for_status()
    data = resp.json()
    return data["data"]["viewer"]["assignedIssues"]["nodes"]


# ── Standup builder ───────────────────────────────────────────────────────────


def _link(url: str | None, text: str) -> str:
    if url:
        return f"<{url}|{text}>"
    return text


def _format_issue(issue: dict, pr: dict | None = None, pr_status: str | None = None) -> str:
    line = f"- {_link(issue.get('url'), issue['identifier'])} — {issue['title']}"
    if pr and pr_status:
        number = _link(pr.get("html_url"), f"#{pr['number']}")
        line += f" ({number} {pr_status})"
    return line


def _format_pr(pr: dict, status: str) -> str:
    number = _link(pr.get("html_url"), f"#{pr['number']}")
    return f"- PR {number} {status} — {pr['title']}"


def _format_review(review: dict) -> str:
    number = _link(review.get("html_url"), f"#{review['number']}")
    author = review["user"]["login"]
    return f"- {number} — {review['title']} (@{author}'s PR)"


def _matches_issue(pr: dict, issue: dict) -> bool:
    return issue["identifier"].lower() in pr["title"].lower()


def _pair_issues_prs(
    issues: list[dict], prs: list[dict]
) -> tuple[list[tuple[dict, dict | None]], list[dict]]:
    used_pr_numbers: set[int] = set()
    paired: list[tuple[dict, dict | None]] = []
    for issue in issues:
        match = next(
            (
                pr
                for pr in prs
                if pr["number"] not in used_pr_numbers and _matches_issue(pr, issue)
            ),
            None,
        )
        if match:
            used_pr_numbers.add(match["number"])
        paired.append((issue, match))
    unmatched = [p for p in prs if p["number"] not in used_pr_numbers]
    return paired, unmatched


def _append_section(
    lines: list[str],
    issues: list[dict],
    prs: list[dict],
    pr_status: str,
) -> None:
    paired, unmatched = _pair_issues_prs(issues, prs)
    for issue, pr in paired:
        lines.append(_format_issue(issue, pr, pr_status if pr else None))
    for pr in unmatched:
        lines.append(_format_pr(pr, pr_status))


def build_standup(issues: list[dict], prs: dict, reviews: list[dict]) -> str:
    done_issues = [
        i for i in issues if i["state"]["type"] in ("completed", "cancelled")
    ]
    in_progress = [i for i in issues if i["state"]["type"] == "started"]
    blockers = [
        i
        for i in issues
        if i["state"]["type"] == "backlog" and "block" in i["title"].lower()
    ]

    merged_prs = prs["merged"]
    opened_prs = prs["opened"]

    lines = []
    today_str = datetime.now().strftime("%A %d %b")
    lines.append(f"*Standup — {today_str}*\n")

    period = "Friday" if datetime.now().weekday() == 0 else "yesterday"
    lines.append(f"✅ *Done {period}*")
    if not done_issues and not merged_prs:
        lines.append("— nothing completed")
    else:
        _append_section(lines, done_issues, merged_prs, "merged")

    if reviews:
        lines.append("\n👀 *Reviews*")
        for review in reviews:
            lines.append(_format_review(review))

    lines.append("\n🔨 *Working on today*")
    if not in_progress and not opened_prs:
        lines.append("— TBD")
    else:
        _append_section(lines, in_progress, opened_prs, "open")

    if blockers:
        lines.append("\n🚧 *Blockers*")
        for i in blockers:
            lines.append(_format_issue(i))

    return "\n".join(lines)


# ── Slack ─────────────────────────────────────────────────────────────────────


def post_to_slack(text: str) -> None:
    if not SLACK_WEBHOOK_URL:
        print("WARNING: SLACK_WEBHOOK_URL not set, skipping Slack post")
        return
    resp = requests.post(
        SLACK_WEBHOOK_URL,
        json={
            "text": text,
            "blocks": [
                {"type": "section", "text": {"type": "mrkdwn", "text": text}}
            ],
        },
    )
    resp.raise_for_status()
    print("Standup posted to Slack.")


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    print("Fetching Linear issues...")
    try:
        issues = fetch_linear_issues()
        days = _lookback_days()
        print(f"  {len(issues)} issues updated in last {days * 24}h")
    except Exception as e:
        print(f"  Linear error: {e}")
        issues = []

    print("Checking GitHub token...")
    try:
        _validate_github_token()
    except Exception as e:
        print(f"  GitHub token error: {e}")

    print("Fetching GitHub PRs...")
    try:
        prs = fetch_yesterday_prs()
        print(f"  {len(prs['merged'])} merged, {len(prs['opened'])} opened")
    except Exception as e:
        print(f"  GitHub error: {e}")
        prs = {"merged": [], "opened": []}

    print("Fetching GitHub reviews...")
    try:
        reviews = fetch_reviews()
        print(f"  {len(reviews)} reviewed")
    except Exception as e:
        print(f"  GitHub reviews error: {e}")
        reviews = []

    standup = build_standup(issues, prs, reviews)

    print("\n" + "─" * 50)
    print(standup)
    print("─" * 50)

    post_to_slack(standup)


if __name__ == "__main__":
    main()
