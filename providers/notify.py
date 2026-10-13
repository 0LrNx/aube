"""Notification sinks: post the built standup message somewhere."""

from abc import ABC, abstractmethod

import requests

from standup_core.builder import MARKDOWN, SLACK, MessageFormat


class NotificationSink(ABC):
    # How links and bold are written in the standup text, so they render in this channel.
    message_format: MessageFormat = SLACK

    @abstractmethod
    def post(self, text: str) -> None:
        ...


class _WebhookNotifier(NotificationSink):
    """Shared behavior for simple webhook channels: post a payload, or skip with a warning if unconfigured."""

    _label: str
    _env_var: str

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def _payload(self, text: str) -> dict:
        raise NotImplementedError

    def post(self, text: str) -> None:
        if not self.webhook_url:
            print(f"WARNING: {self._env_var} not set, skipping {self._label} post")
            return
        # The webhook URL is a credential (anyone holding it can post), so it must never end up in
        # an error message: requests' own exceptions include it, hence the re-raise without context.
        try:
            resp = requests.post(self.webhook_url, json=self._payload(text), timeout=15)
        except requests.RequestException as e:
            raise RuntimeError(f"{self._label} webhook request failed ({type(e).__name__})") from None
        if not resp.ok:
            raise RuntimeError(f"{self._label} webhook returned HTTP {resp.status_code}: {resp.text[:500]}")
        print(f"Standup posted to {self._label}.")


class SlackNotifier(_WebhookNotifier):
    _label = "Slack"
    _env_var = "SLACK_WEBHOOK_URL"

    def _payload(self, text: str) -> dict:
        return {
            "text": text,
            "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": text}}],
        }


class TeamsNotifier(_WebhookNotifier):
    _label = "Teams"
    _env_var = "TEAMS_WEBHOOK_URL"
    message_format = MARKDOWN

    def _payload(self, text: str) -> dict:
        # Adaptive Card: accepted by Workflows webhooks (which replace the retired Office 365
        # connectors) and by legacy Incoming Webhooks. One TextBlock per line keeps line breaks.
        body = []
        spacing = None
        for line in text.split("\n"):
            if not line.strip():
                spacing = "Large"
                continue
            block = {"type": "TextBlock", "text": line, "wrap": True}
            if spacing:
                block["spacing"] = spacing
                spacing = None
            body.append(block)
        return {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "body": body,
                    },
                }
            ],
        }


class NullNotifier(NotificationSink):
    """No notification channel configured — the standup already prints to the terminal."""

    def post(self, text: str) -> None:
        pass
