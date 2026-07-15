<div align="center">

# Linear GitHub Standup

**Daily standup generator from Linear tickets, GitHub pull requests and code reviews.**

Fetches your work, formats it, posts to Slack.

<p>
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/Linear-5E6AD2.svg?logo=linear&logoColor=white" alt="Linear">
  <img src="https://img.shields.io/badge/GitHub-181717.svg?logo=github&logoColor=white" alt="GitHub">
  <img src="https://img.shields.io/badge/Slack-4A154B.svg?logo=slack&logoColor=white" alt="Slack">
</p>

```
*Standup — Wednesday 15 Jul*

*Done yesterday*
- ENG-42 — Fix login bug (#123 merged)
- PR #124 merged — Refactor auth module

*Working on today*
- ENG-43 — New dashboard (#125 open)

*Blockers*
- ENG-44 — Blocked on API access
```

</div>

## What it does

Every weekday morning, the script pulls your recent activity and posts a ready-to-paste standup to Slack.

- **Done** — completed Linear issues + merged PRs from the lookback window
- **Reviews** — PRs you reviewed (excluding your own)
- **Working on today** — in-progress issues + open PRs
- **Blockers** — flagged issues with "block" in the title
- **Ticket ↔ PR pairing** — links a Linear issue to its PR when the ID appears in the title

On Mondays, the lookback extends to Friday to cover the weekend.

## Quickstart

```bash
git clone https://github.com/y2-znt/linear-github-standup.git && cd linear-github-standup
python3 -m venv .venv && source .venv/bin/activate
pip install requests && cp .env.example .env
python standup.py
```

Fill `.env` with your tokens (see below). Without `SLACK_WEBHOOK_URL`, output prints to the terminal.

**Cron** — weekdays at 9am:

```
0 9 * * 1-5 cd /path/to/linear-github-standup && .venv/bin/python standup.py
```

## Stack

```
Linear API + GitHub API → standup.py → Slack Incoming Webhook
```

## Tokens

**GitHub** — [Settings → Tokens (classic)](https://github.com/settings/tokens) → Generate → `repo` scope → `GITHUB_TOKEN` + `GITHUB_USERNAME`

**Linear** — [Settings → API](https://linear.app/settings/api) → Personal API keys → Create key → `LINEAR_TOKEN`

**Slack** — [api.slack.com/apps](https://api.slack.com/apps) → Create app → Incoming Webhooks → enable → Add to workspace → `SLACK_WEBHOOK_URL`

> **Note:** All API calls run locally. Your tokens never leave your machine.
