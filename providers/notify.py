"""Notification sinks: post the built standup message somewhere."""

from abc import ABC, abstractmethod

import requests


class NotificationSink(ABC):
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
        resp = requests.post(self.webhook_url, json=self._payload(text))
        resp.raise_for_status()
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

    def _payload(self, text: str) -> dict:
        return {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "text": text,
        }


class NullNotifier(NotificationSink):
    """No notification channel configured — the standup already prints to the terminal."""

    def post(self, text: str) -> None:
        pass
