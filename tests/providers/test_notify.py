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


def test_teams_notifier_posts_text_as_adaptive_card_one_block_per_line(monkeypatch):
    captured = {}

    def fake_post(url, json=None, **kwargs):
        captured["url"] = url
        captured["json"] = json
        return _FakeResponse()

    monkeypatch.setattr("providers.notify.requests.post", fake_post)

    notifier = TeamsNotifier(webhook_url="https://prod.westeurope.logic.azure.com/workflows/x")
    notifier.post("**Standup**\n\n✅ **Done**\n- item")

    payload = captured["json"]
    assert captured["url"] == "https://prod.westeurope.logic.azure.com/workflows/x"
    assert payload["type"] == "message"
    attachment = payload["attachments"][0]
    assert attachment["contentType"] == "application/vnd.microsoft.card.adaptive"
    card = attachment["content"]
    assert card["type"] == "AdaptiveCard"
    body = card["body"]
    assert [block["text"] for block in body] == ["**Standup**", "✅ **Done**", "- item"]
    assert all(block["type"] == "TextBlock" and block["wrap"] for block in body)
    # A blank line in the text becomes extra spacing before the next block.
    assert body[1].get("spacing") == "Large"
    assert "spacing" not in body[2]


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


def test_teams_notifier_uses_markdown_format_and_others_use_slack_format():
    from standup_core.builder import MARKDOWN, SLACK

    assert TeamsNotifier(webhook_url="").message_format is MARKDOWN
    assert SlackNotifier(webhook_url="").message_format is SLACK
    assert NullNotifier().message_format is SLACK


def test_webhook_notifiers_pass_a_timeout(monkeypatch):
    timeouts = []

    def fake_post(url, json=None, timeout=None):
        timeouts.append(timeout)
        return _FakeResponse()

    monkeypatch.setattr("providers.notify.requests.post", fake_post)

    SlackNotifier(webhook_url="https://hooks.slack.com/services/x").post("hello")
    TeamsNotifier(webhook_url="https://outlook.office.com/webhook/x").post("hello")

    assert len(timeouts) == 2
    assert all(timeouts)
