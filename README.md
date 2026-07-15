<div align="center">

# Linear GitHub Standup

**Turn your Linear tickets & GitHub PRs into a daily standup for Slack.**

Single Python script. Fetches your activity, formats a message, posts it (or prints to terminal).

<p>
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/Linear-5E6AD2.svg?logo=linear&logoColor=white" alt="Linear">
  <img src="https://img.shields.io/badge/GitHub-181717.svg?logo=github&logoColor=white" alt="GitHub">
  <img src="https://img.shields.io/badge/Slack-4A154B.svg?logo=slack&logoColor=white" alt="Slack">
</p>

</div>

```
*Standup — Wednesday 15 Jul*

✅ *Done yesterday*
- ENG-42 — Fix login redirect (#128 merged)
- PR #129 merged — Add rate limiting middleware

👀 *Reviews*
- #127 — Refactor auth module (by @teammate)

🔨 *Working on today*
- ENG-43 — Dashboard v2 (#130 open)

🚧 *Blockers*
- ENG-44 — Waiting on API credentials
```

## What it does

- **Done** — completed Linear issues + merged PRs
- **Reviews** — PRs you reviewed (not your own)
- **In progress** — started issues + open PRs
- **Blockers** — issues with "block" in the title
- **Ticket ↔ PR pairing** — when the Linear ID appears in the PR title
- **Monday-aware** — lookback goes back to Friday

## Setup

```bash
git clone https://github.com/y2-znt/linear-github-standup.git
cd linear-github-standup
python3 -m venv .venv && source .venv/bin/activate
pip install requests
cp .env.example .env
```

`.env`:

```
GITHUB_TOKEN=       # PAT with repo scope
GITHUB_USERNAME=
LINEAR_TOKEN=       # Linear personal API key
SLACK_WEBHOOK_URL=  # optional
```

```bash
python standup.py
```

**Cron** (weekdays 9am):

```
0 9 * * 1-5 cd /path/to/Linear-GitHub-Standup && .venv/bin/python standup.py
```

## Tokens

- **GitHub** — [Settings → Tokens (classic)](https://github.com/settings/tokens), `repo` scope
- **Linear** — [Settings → API](https://linear.app/settings/api) → Personal API keys
- **Slack** — [api.slack.com/apps](https://api.slack.com/apps) → Incoming Webhooks → add to workspace

Everything runs locally. Tokens stay in your `.env`.
