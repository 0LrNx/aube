"""Pure standup message construction, independent of any provider."""

from datetime import datetime

from standup_core.models import Issue, PullRequest, Review


def _link(url: str | None, text: str) -> str:
    if url:
        return f"<{url}|{text}>"
    return text


def _format_issue(issue: Issue, pr: PullRequest | None = None, pr_status: str | None = None) -> str:
    line = f"- {_link(issue.url, issue.identifier)} — {issue.title}"
    if pr and pr_status:
        number = _link(pr.url, f"#{pr.number}")
        line += f" ({number} {pr_status})"
    return line


def _format_pr(pr: PullRequest, status: str) -> str:
    number = _link(pr.url, f"#{pr.number}")
    return f"- PR {number} {status} — {pr.title}"


def _format_review(review: Review) -> str:
    number = _link(review.url, f"#{review.number}")
    return f"- {number} — {review.title} (@{review.author}'s PR)"


def _matches_issue(pr: PullRequest, issue: Issue) -> bool:
    identifier = issue.identifier.lower()
    if identifier in pr.title.lower():
        return True
    return identifier in (pr.description or "").lower()


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
) -> None:
    paired, unmatched = pair_issues_prs(issues, prs)
    for issue, pr in paired:
        lines.append(_format_issue(issue, pr, pr_status if pr else None))
    for pr in unmatched:
        lines.append(_format_pr(pr, pr_status))


def build_standup(
    issues: list[Issue],
    merged_prs: list[PullRequest],
    opened_prs: list[PullRequest],
    reviews: list[Review],
) -> str:
    done_issues = [i for i in issues if i.state_type in ("completed", "cancelled")]
    in_progress = [i for i in issues if i.state_type == "started"]
    blockers = [i for i in issues if i.state_type == "backlog" and "block" in i.title.lower()]

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
