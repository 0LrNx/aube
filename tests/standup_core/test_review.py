from standup_core.models import Issue, PullRequest, Review
from standup_core.review import review


def _scripted(answers):
    it = iter(answers)
    prompts = []

    def ask(prompt):
        prompts.append(prompt)
        return next(it)

    return ask, prompts


def _data():
    issues = [
        Issue(identifier="AB#1", title="Ship feature", url=None, state_type="completed"),
        Issue(identifier="AB#2", title="Support call", url=None, state_type="completed"),
    ]
    merged = [PullRequest(number=10, title="Unrelated cleanup", url=None)]
    reviews = [Review(number=7, title="Add tests", url=None, author="alice")]
    return issues, merged, [], reviews


def test_review_drops_selected_items_and_adds_today_and_blockers():
    issues, merged, opened, reviews = _data()
    ask, _ = _scripted([
        "2, 4",  # drop AB#2 and the review
        "Pair on the release", "Write the migration", "",  # working on today
        "Waiting on legal", "",  # blockers
        "y",  # post it
    ])
    shown = []

    standup = review(issues, merged, opened, reviews, ask=ask, show=shown.append, destination="Slack")

    assert standup is not None
    assert "AB#1" in standup
    assert "AB#2" not in standup
    assert "#7" not in standup
    assert "#10" in standup
    assert "- Pair on the release" in standup
    assert "- Write the migration" in standup
    assert "TBD" not in standup
    assert "Blockers" in standup
    assert "- Waiting on legal" in standup
    assert any("1." in s and "AB#1" in s for s in shown)


def test_review_keeps_everything_on_empty_answers():
    issues, merged, opened, reviews = _data()
    ask, _ = _scripted(["", "", "", ""])

    standup = review(issues, merged, opened, reviews, ask=ask, show=lambda _: None, destination="Teams")

    assert all(token in standup for token in ("AB#1", "AB#2", "#10", "#7"))


def test_review_returns_none_when_posting_is_declined():
    issues, merged, opened, reviews = _data()
    ask, _ = _scripted(["", "", "", "n"])

    assert review(issues, merged, opened, reviews, ask=ask, show=lambda _: None, destination="Slack") is None


def test_review_asks_again_on_an_invalid_selection():
    issues, merged, opened, reviews = _data()
    ask, prompts = _scripted(["9", "abc", "1", "", "", "y"])
    shown = []

    standup = review(issues, merged, opened, reviews, ask=ask, show=shown.append, destination="Slack")

    assert "AB#1" not in standup
    assert sum("drop" in p.lower() for p in prompts) == 3
    assert any("invalid" in s.lower() for s in shown)


def test_review_does_not_ask_for_confirmation_without_a_destination():
    issues, merged, opened, reviews = _data()
    ask, prompts = _scripted(["", "", ""])

    standup = review(issues, merged, opened, reviews, ask=ask, show=lambda _: None, destination=None)

    assert standup is not None
    assert len(prompts) == 3
