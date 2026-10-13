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


def _run(monkeypatch, tickets, code, notifier, argv=None):
    monkeypatch.setattr(standup, "_load_env", lambda: None)
    monkeypatch.setattr(standup, "_validate_env", lambda: None)
    monkeypatch.setattr(standup, "build_ticket_provider", lambda env: tickets)
    monkeypatch.setattr(standup, "build_code_provider", lambda env: code)
    monkeypatch.setattr(standup, "build_notifier", lambda env: notifier)
    return standup.main(argv or [])


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


def test_main_returns_nonzero_with_a_clean_message_when_posting_fails(monkeypatch, capsys):
    class _FailingNotifier(_Notifier):
        def post(self, text):
            raise RuntimeError("Teams webhook returned HTTP 400: bad payload")

    exit_code = _run(monkeypatch, _Tickets(), _Code(), _FailingNotifier())

    assert exit_code == 1
    err = capsys.readouterr().err
    assert "Standup NOT posted" in err
    assert "HTTP 400: bad payload" in err


def test_main_prints_the_colored_logo_in_an_interactive_terminal(monkeypatch, capsys):
    import sys

    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr(standup, "_enable_ansi_on_windows", lambda: True)

    _run(monkeypatch, _Tickets(), _Code(), _Notifier())

    out = capsys.readouterr().out
    assert "a u b e" in out
    assert "\x1b[38;2;" in out


def test_main_prints_a_plain_logo_when_no_color_is_set(monkeypatch, capsys):
    import sys

    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

    _run(monkeypatch, _Tickets(), _Code(), _Notifier())

    out = capsys.readouterr().out
    assert "a u b e" in out
    assert "\x1b[" not in out


def test_main_skips_the_logo_when_output_is_piped(monkeypatch, capsys):
    _run(monkeypatch, _Tickets(), _Code(), _Notifier())

    assert "a u b e" not in capsys.readouterr().out


def _interactive(monkeypatch, answers):
    import builtins
    import sys

    it = iter(answers)
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(it))
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True, raising=False)


def test_review_flag_posts_the_reviewed_standup(monkeypatch):
    notifier = _Notifier()
    notifier.destination = "Slack"
    _interactive(monkeypatch, ["", "Pair on the release", "", "", "y"])

    exit_code = _run(monkeypatch, _Tickets(), _Code(), notifier, argv=["--review"])

    assert exit_code == 0
    assert len(notifier.posted) == 1
    assert "- Pair on the release" in notifier.posted[0]


def test_review_flag_does_not_post_when_declined(monkeypatch, capsys):
    notifier = _Notifier()
    notifier.destination = "Slack"
    _interactive(monkeypatch, ["", "", "", "n"])

    exit_code = _run(monkeypatch, _Tickets(), _Code(), notifier, argv=["--review"])

    assert exit_code == 0
    assert notifier.posted == []
    assert "not posted" in capsys.readouterr().out.lower()


def test_review_flag_refuses_to_run_without_an_interactive_terminal(monkeypatch, capsys):
    import sys

    monkeypatch.setattr(sys.stdin, "isatty", lambda: False, raising=False)
    notifier = _Notifier()

    exit_code = _run(monkeypatch, _Tickets(), _Code(), notifier, argv=["--review"])

    assert exit_code == 2
    assert notifier.posted == []
    assert "--review" in capsys.readouterr().err
