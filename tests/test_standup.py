import os

import standup
from standup_core.builder import SLACK
from standup_core.models import Issue


class _Tickets:
    def __init__(self, error=None):
        self.error = error

    def fetch_issues(self, lookback_days):
        if self.error:
            raise self.error
        return [Issue(identifier="ABC-1", title="Ship it", url=None, state_type="completed")]


class _Code:
    def __init__(self, prs_error=None, reviews_error=None):
        self.prs_error = prs_error
        self.reviews_error = reviews_error

    def validate_credentials(self):
        pass

    def fetch_prs(self, lookback_days):
        if self.prs_error:
            raise self.prs_error
        return {"merged": [], "opened": []}

    def fetch_reviews(self, lookback_days):
        if self.reviews_error:
            raise self.reviews_error
        return []


class _Notifier:
    message_format = SLACK

    def __init__(self):
        self.posted = []

    def post(self, text):
        self.posted.append(text)


def _run(monkeypatch, tickets, code, notifier):
    monkeypatch.setattr(standup, "_load_env", lambda: None)
    monkeypatch.setattr(standup, "_validate_env", lambda: None)
    monkeypatch.setattr(standup, "build_ticket_provider", lambda env: tickets)
    monkeypatch.setattr(standup, "build_code_provider", lambda env: code)
    monkeypatch.setattr(standup, "build_notifier", lambda env: notifier)
    return standup.main()


def test_main_posts_and_returns_zero_when_every_source_succeeds(monkeypatch):
    notifier = _Notifier()

    exit_code = _run(monkeypatch, _Tickets(), _Code(), notifier)

    assert exit_code == 0
    assert len(notifier.posted) == 1
    assert "ABC-1" in notifier.posted[0]


def test_main_does_not_post_and_fails_when_ticket_source_errors(monkeypatch, capsys):
    notifier = _Notifier()

    exit_code = _run(monkeypatch, _Tickets(error=RuntimeError("401 Unauthorized")), _Code(), notifier)

    assert exit_code == 1
    assert notifier.posted == []
    err = capsys.readouterr().err
    assert "tickets" in err
    assert "401 Unauthorized" in err


def test_main_does_not_post_and_fails_when_pr_or_review_fetch_errors(monkeypatch, capsys):
    for code in (_Code(prs_error=RuntimeError("boom")), _Code(reviews_error=RuntimeError("boom"))):
        notifier = _Notifier()

        exit_code = _run(monkeypatch, _Tickets(), code, notifier)

        assert exit_code == 1
        assert notifier.posted == []
        assert "boom" in capsys.readouterr().err


def test_load_env_does_not_override_variables_already_set_in_the_environment(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "STANDUP_TEST_FROM_SHELL=from-file\nexport STANDUP_TEST_FROM_FILE='octocat'\n", encoding="utf-8"
    )
    monkeypatch.setenv("STANDUP_TEST_FROM_SHELL", "from-shell")
    monkeypatch.delenv("STANDUP_TEST_FROM_FILE", raising=False)

    standup._load_env(str(env_file))

    assert os.environ["STANDUP_TEST_FROM_SHELL"] == "from-shell"
    assert os.environ["STANDUP_TEST_FROM_FILE"] == "octocat"
