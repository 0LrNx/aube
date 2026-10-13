"""Interactive review of the standup before posting (python standup.py --review)."""

from collections.abc import Callable

from standup_core.builder import SLACK, MessageFormat, build_standup
from standup_core.models import Issue, PullRequest, Review

Ask = Callable[[str], str]
Show = Callable[[str], None]


def _ask_lines(ask: Ask, show: Show, title: str) -> list[str]:
    show(f"\n{title} (one per line, empty line to finish):")
    lines = []
    while line := ask("> ").strip():
        lines.append(line)
    return lines


def _ask_drop(ask: Ask, show: Show, count: int) -> set[int]:
    while True:
        answer = ask("Numbers to drop (e.g. 2,5), Enter to keep all: ").strip()
        if not answer:
            return set()
        try:
            numbers = {int(token) for token in answer.replace(" ", "").split(",") if token}
        except ValueError:
            numbers = None
        if numbers and all(1 <= n <= count for n in numbers):
            return numbers
        show(f"Invalid selection: use numbers between 1 and {count}, separated by commas.")


def review(
    issues: list[Issue],
    merged_prs: list[PullRequest],
    opened_prs: list[PullRequest],
    reviews: list[Review],
    *,
    ask: Ask,
    show: Show,
    fmt: MessageFormat = SLACK,
    destination: str | None = None,
) -> str | None:
    """Let the user drop items, add today's work and blockers; return the final standup, or None if declined."""
    items: list[tuple[str, object]] = (
        [("ticket", i) for i in issues]
        + [("merged PR", pr) for pr in merged_prs]
        + [("open PR", pr) for pr in opened_prs]
        + [("review", r) for r in reviews]
    )

    dropped: set[int] = set()
    if items:
        show("\nItems in this standup:")
        for n, (kind, item) in enumerate(items, start=1):
            label = item.identifier if isinstance(item, Issue) else f"#{item.number}"
            show(f"  {n}. [{kind}] {label} — {item.title}")
        dropped = _ask_drop(ask, show, len(items))

    def kept(kind: str) -> list:
        return [item for n, (k, item) in enumerate(items, start=1) if k == kind and n not in dropped]

    today = _ask_lines(ask, show, "Add to 'Working on today'")
    blockers = _ask_lines(ask, show, "Any blockers")

    standup = build_standup(
        kept("ticket"),
        kept("merged PR"),
        kept("open PR"),
        kept("review"),
        fmt=fmt,
        extra_today=today,
        extra_blockers=blockers,
    )
    show("\n" + standup + "\n")

    if destination is None:
        return standup
    answer = ask(f"Post it to {destination}? [Y/n]: ").strip().lower()
    return standup if answer in ("", "y", "yes", "o", "oui") else None
