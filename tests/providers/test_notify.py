from providers.notify import NullNotifier, SlackNotifier, TeamsNotifier


class _FakeResponse:
    def raise_for_status(self):
        pass


def test_slack_notifier_posts_text_as_mrkdwn_block(monkeypatch):
    captured = {}

    def fake_post(url, json=None, **kwargs):
        captured["url"] = url
        captured["json"] = json
        return _FakeResponse()

    monkeypatch.setattr("providers.notify.requests.post", fake_post)

    notifier = SlackNotifier(webhook_url="https://hooks.slack.com/services/x")
    notifier.post("hello standup")

    assert captured["url"] == "https://hooks.slack.com/services/x"
    assert captured["json"]["text"] == "hello standup"
    assert captured["json"]["blocks"][0]["text"]["text"] == "hello standup"


def test_slack_notifier_skips_when_no_webhook_configured(monkeypatch, capsys):
    def fake_post(*args, **kwargs):
        raise AssertionError("should not call requests.post without a webhook")

    monkeypatch.setattr("providers.notify.requests.post", fake_post)

    notifier = SlackNotifier(webhook_url="")
    notifier.post("hello standup")

    assert "SLACK_WEBHOOK_URL not set" in capsys.readouterr().out


def test_teams_notifier_posts_text_as_message_card(monkeypatch):
    captured = {}

    def fake_post(url, json=None, **kwargs):
        captured["url"] = url
        captured["json"] = json
        return _FakeResponse()

    monkeypatch.setattr("providers.notify.requests.post", fake_post)

    notifier = TeamsNotifier(webhook_url="https://outlook.office.com/webhook/x")
    notifier.post("hello standup")

    assert captured["url"] == "https://outlook.office.com/webhook/x"
    assert captured["json"]["@type"] == "MessageCard"
    assert captured["json"]["text"] == "hello standup"


def test_teams_notifier_skips_when_no_webhook_configured(monkeypatch, capsys):
    def fake_post(*args, **kwargs):
        raise AssertionError("should not call requests.post without a webhook")

    monkeypatch.setattr("providers.notify.requests.post", fake_post)

    notifier = TeamsNotifier(webhook_url="")
    notifier.post("hello standup")

    assert "TEAMS_WEBHOOK_URL not set" in capsys.readouterr().out


def test_null_notifier_does_nothing(monkeypatch):
    def fake_post(*args, **kwargs):
        raise AssertionError("should never call requests.post")

    monkeypatch.setattr("providers.notify.requests.post", fake_post)

    notifier = NullNotifier()
    notifier.post("hello standup")
