from standup_core.builder import MARKDOWN, build_standup, pair_issues_prs
from standup_core.models import Issue, PullRequest, Review


def _issue(identifier, title, state_type, url="https://linear.app/x"):
    return Issue(identifier=identifier, title=title, url=url, state_type=state_type)


def _pr(number, title, url="https://github.com/x/pull/1", description=None):
    return PullRequest(number=number, title=title, url=url, description=description)


def test_pair_issues_prs_matches_by_identifier_in_title():
    issue = _issue("ABC-123", "Fix login bug", "completed")
    pr = _pr(42, "ABC-123: fix login bug")

    paired, unmatched = pair_issues_prs([issue], [pr])

    assert paired == [(issue, pr)]
    assert unmatched == []


def test_pair_issues_prs_matches_by_identifier_in_description():
    issue = _issue("AB#123", "Fix login bug", "completed")
    pr = _pr(42, "Fix the thing", description="Fixes AB#123 via a small patch")

    paired, unmatched = pair_issues_prs([issue], [pr])

    assert paired == [(issue, pr)]
    assert unmatched == []


def test_pair_issues_prs_does_not_match_identifier_prefix_of_longer_one():
    issue = _issue("ENG-1", "Small fix", "completed")
    ado_issue = _issue("AB#12", "Other fix", "completed")
    pr = _pr(42, "ENG-12: unrelated work", description="Fixes AB#123")

    paired, unmatched = pair_issues_prs([issue, ado_issue], [pr])

    assert paired == [(issue, None), (ado_issue, None)]
    assert unmatched == [pr]


def test_pair_issues_prs_does_not_match_identifier_suffix_of_longer_one():
    issue = _issue("ENG-1", "Small fix", "completed")
    pr = _pr(42, "XENG-1: unrelated work")

    paired, unmatched = pair_issues_prs([issue], [pr])

    assert paired == [(issue, None)]
    assert unmatched == [pr]


def test_pair_issues_prs_matches_identifier_case_insensitively_next_to_punctuation():
    issue = _issue("ENG-1", "Small fix", "completed")
    pr = _pr(42, "[eng-1] small fix")

    paired, unmatched = pair_issues_prs([issue], [pr])

    assert paired == [(issue, pr)]
    assert unmatched == []


def test_pair_issues_prs_returns_unmatched_prs():
    issue = _issue("ABC-123", "Fix login bug", "completed")
    unrelated_pr = _pr(7, "Unrelated cleanup")

    paired, unmatched = pair_issues_prs([issue], [unrelated_pr])

    assert paired == [(issue, None)]
    assert unmatched == [unrelated_pr]


def test_build_standup_lists_done_and_in_progress_sections():
    done_issue = _issue("ABC-1", "Ship feature", "completed")
    in_progress_issue = _issue("ABC-2", "Work on thing", "started")
    merged_pr = _pr(10, "ABC-1: ship feature")
    opened_pr = _pr(11, "ABC-2: work on thing")

    standup = build_standup(
        issues=[done_issue, in_progress_issue],
        merged_prs=[merged_pr],
        opened_prs=[opened_pr],
        reviews=[],
    )

    assert "Done" in standup
    assert "ABC-1" in standup
    assert "Working on today" in standup
    assert "ABC-2" in standup


def test_build_standup_shows_empty_states_when_nothing_happened():
    standup = build_standup(issues=[], merged_prs=[], opened_prs=[], reviews=[])

    assert "nothing completed" in standup
    assert "TBD" in standup


def test_build_standup_lists_blockers_with_block_in_title():
    blocker = _issue("ABC-9", "Blocked on infra", "backlog")

    standup = build_standup(issues=[blocker], merged_prs=[], opened_prs=[], reviews=[])

    assert "Blockers" in standup
    assert "ABC-9" in standup


def test_build_standup_lists_reviews():
    review = Review(number=5, title="Add tests", url="https://github.com/x/pull/5", author="octocat")

    standup = build_standup(issues=[], merged_prs=[], opened_prs=[], reviews=[review])

    assert "Reviews" in standup
    assert "@octocat" in standup


def test_build_standup_uses_slack_links_by_default():
    issue = _issue("ABC-1", "Ship feature", "completed", url="https://linear.app/x/ABC-1")

    standup = build_standup(issues=[issue], merged_prs=[], opened_prs=[], reviews=[])

    assert "<https://linear.app/x/ABC-1|ABC-1>" in standup
    assert "✅ *Done" in standup


def test_build_standup_uses_given_message_format_everywhere():
    issue = _issue("ABC-1", "Ship feature", "completed", url="https://linear.app/x/ABC-1")
    pr = _pr(10, "ABC-1: ship feature", url="https://github.com/x/pull/10")
    review = Review(number=5, title="Add tests", url="https://github.com/x/pull/5", author="octocat")

    standup = build_standup(issues=[issue], merged_prs=[pr], opened_prs=[], reviews=[review], fmt=MARKDOWN)

    assert "[ABC-1](https://linear.app/x/ABC-1)" in standup
    assert "[#10](https://github.com/x/pull/10)" in standup
    assert "[#5](https://github.com/x/pull/5)" in standup
    assert "<https://" not in standup
    assert "✅ **Done" in standup
    assert "**Reviews**" in standup
    assert "**Working on today**" in standup
