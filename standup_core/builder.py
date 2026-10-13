"""Pure standup message construction, independent of any provider."""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from standup_core.models import Issue, PullRequest, Review

LinkFormat = Callable[[str, str], str]

# "block", "blocked", "blocker(s)", "blocking" as a whole word — but not "unblock".
_BLOCKER_PATTERN = re.compile(r"\bblock(?:s|ed|er|ers|ing)?\b", re.IGNORECASE)


def slack_link(url: str, text: str) -> str:
    return f"<{url}|{text}>"


def markdown_link(url: str, text: str) -> str:
    return f"[{text}]({url})"


@dataclass(frozen=True)
class MessageFormat:
    """How links and bold text are written, so the standup renders in the target channel."""

    link: LinkFormat
    bold: Callable[[str], str]


SLACK = MessageFormat(link=slack_link, bold=lambda text: f"*{text}*")
MARKDOWN = MessageFormat(link=markdown_link, bold=lambda text: f"**{text}**")


def _link(link: LinkFormat, url: str | None, text: str) -> str:
    if url:
        return link(url, text)
    return text


def _format_issue(
    link: LinkFormat, issue: Issue, pr: PullRequest | None = None, pr_status: str | None = None
) -> str:
    line = f"- {_link(link, issue.url, issue.identifier)} — {issue.title}"
    if pr and pr_status:
        number = _link(link, pr.url, f"#{pr.number}")
        line += f" ({number} {pr_status})"
    return line


def _format_pr(link: LinkFormat, pr: PullRequest, status: str) -> str:
    number = _link(link, pr.url, f"#{pr.number}")
    return f"- PR {number} {status} — {pr.title}"


def _format_review(link: LinkFormat, review: Review) -> str:
    number = _link(link, review.url, f"#{review.number}")
    return f"- {number} — {review.title} (@{review.author}'s PR)"


def _matches_issue(pr: PullRequest, issue: Issue) -> bool:
    # Bounded match so "ENG-1" doesn't pair with "ENG-12" (or "AB#12" with "AB#123").
    pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(issue.identifier)}(?![0-9])", re.IGNORECASE)
    return bool(pattern.search(pr.title) or pattern.search(pr.description or ""))


def pair_issues_prs(
    issues: list[Issue], prs: list[PullRequest]
) -> tuple[list[tuple[Issue, PullRequest | None]], list[PullRequest]]:
    used_pr_numbers: set[int] = set()
    paired: list[tuple[Issue, PullRequest | None]] = []
    for issue in issues:
        match = next(
            (pr for pr in prs if pr.number not in used_pr_numbers and _matches_issue(pr, issue)),
            None,
        )
        if match:
            used_pr_numbers.add(match.number)
        paired.append((issue, match))
    unmatched = [pr for pr in prs if pr.number not in used_pr_numbers]
    return paired, unmatched


def _append_section(
    lines: list[str],
    issues: list[Issue],
    prs: list[PullRequest],
    pr_status: str,
    fmt: MessageFormat,
) -> None:
    paired, unmatched = pair_issues_prs(issues, prs)
    for issue, pr in paired:
        lines.append(_format_issue(fmt.link, issue, pr, pr_status if pr else None))
    for pr in unmatched:
        lines.append(_format_pr(fmt.link, pr, pr_status))


def _split_issues(issues: list[Issue]) -> tuple[list[Issue], list[Issue], list[Issue]]:
    """Done, in progress, blockers. Issues in any other state don't appear in the standup."""
    done = [i for i in issues if i.state_type in ("completed", "cancelled")]
    in_progress = [i for i in issues if i.state_type == "started"]
    blockers = [i for i in issues if i.state_type == "backlog" and _BLOCKER_PATTERN.search(i.title)]
    return done, in_progress, blockers


def shown_issues(issues: list[Issue]) -> list[Issue]:
    """The issues build_standup will actually display, in display order."""
    done, in_progress, blockers = _split_issues(issues)
    return done + in_progress + blockers


def build_standup(
    issues: list[Issue],
    merged_prs: list[PullRequest],
    opened_prs: list[PullRequest],
    reviews: list[Review],
    fmt: MessageFormat = SLACK,
    extra_today: Sequence[str] = (),
    extra_blockers: Sequence[str] = (),
) -> str:
    """Compose the standup; extra_* are free-text lines typed by the user (see --review)."""
    done_issues, in_progress, blockers = _split_issues(issues)

    lines = []
    today_str = datetime.now().strftime("%A %d %b")
    lines.append(fmt.bold(f"Standup — {today_str}") + "\n")

    period = "Friday" if datetime.now().weekday() == 0 else "yesterday"
    lines.append(f"✅ {fmt.bold(f'Done {period}')}")
    if not done_issues and not merged_prs:
        lines.append("— nothing completed")
    else:
        _append_section(lines, done_issues, merged_prs, "merged", fmt)

    if reviews:
        lines.append(f"\n👀 {fmt.bold('Reviews')}")
        for review in reviews:
            lines.append(_format_review(fmt.link, review))

    lines.append(f"\n🔨 {fmt.bold('Working on today')}")
    if not in_progress and not opened_prs and not extra_today:
        lines.append("— TBD")
    else:
        _append_section(lines, in_progress, opened_prs, "open", fmt)
        lines.extend(f"- {line}" for line in extra_today)

    if blockers or extra_blockers:
        lines.append(f"\n🚧 {fmt.bold('Blockers')}")
        for i in blockers:
            lines.append(_format_issue(fmt.link, i))
        lines.extend(f"- {line}" for line in extra_blockers)

    return "\n".join(lines)
