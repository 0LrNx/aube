"""Ticket sources: fetch a user's issues and normalize them to the shared model."""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone

import requests

from providers.azure_devops import basic_auth_header, url_segment
from standup_core.models import Issue

# Azure DevOps work item states vary per process template (Agile/Scrum/CMMI/custom),
# so states are matched by keyword rather than an exact enum.
_ADO_CANCELLED_STATE_KEYWORDS = ("removed",)
_ADO_COMPLETED_STATE_KEYWORDS = ("closed", "resolved", "done")
_ADO_STARTED_STATE_KEYWORDS = ("active", "in progress", "doing", "committed")

LINEAR_QUERY = """
query MyIssues($updatedAt: DateTimeOrDuration) {
  viewer {
    assignedIssues(
      filter: { updatedAt: { gt: $updatedAt } }
      orderBy: updatedAt
    ) {
      nodes {
        identifier
        title
        url
        state { name type }
        updatedAt
      }
    }
  }
}
"""


class TicketProvider(ABC):
    @abstractmethod
    def fetch_issues(self, lookback_days: int) -> list[Issue]:
        ...


class LinearProvider(TicketProvider):
    def __init__(self, token: str):
        self.token = token

    def fetch_issues(self, lookback_days: int) -> list[Issue]:
        since = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
        resp = requests.post(
            "https://api.linear.app/graphql",
            headers={
                "Authorization": self.token,
                "Content-Type": "application/json",
            },
            json={"query": LINEAR_QUERY, "variables": {"updatedAt": since}},
        )
        resp.raise_for_status()
        nodes = resp.json()["data"]["viewer"]["assignedIssues"]["nodes"]
        return [
            Issue(
                identifier=node["identifier"],
                title=node["title"],
                url=node.get("url"),
                state_type=node["state"]["type"],
            )
            for node in nodes
        ]


class AzureDevOpsBoardsProvider(TicketProvider):
    def __init__(self, organization: str, project: str, token: str):
        self.organization = organization
        self.project = project
        self.token = token

    @property
    def _headers(self) -> dict:
        return {**basic_auth_header(self.token), "Content-Type": "application/json"}

    def fetch_issues(self, lookback_days: int) -> list[Issue]:
        since = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        wiql = (
            "SELECT [System.Id] FROM WorkItems "
            "WHERE [System.AssignedTo] = @Me "
            f"AND [System.ChangedDate] >= '{since}'"
        )
        org, project = url_segment(self.organization), url_segment(self.project)
        wiql_resp = requests.post(
            f"https://dev.azure.com/{org}/{project}/_apis/wit/wiql?api-version=7.0",
            headers=self._headers,
            json={"query": wiql},
            timeout=15,
        )
        wiql_resp.raise_for_status()
        ids = [item["id"] for item in wiql_resp.json().get("workItems", [])]
        if not ids:
            return []

        ids_param = ",".join(str(i) for i in ids)
        items_resp = requests.get(
            f"https://dev.azure.com/{org}/{project}/_apis/wit/workitems"
            f"?ids={ids_param}&fields=System.Title,System.State&api-version=7.0",
            headers=self._headers,
            timeout=15,
        )
        items_resp.raise_for_status()
        return [self._to_issue(item) for item in items_resp.json().get("value", [])]

    @staticmethod
    def _to_issue(item: dict) -> Issue:
        fields = item["fields"]
        return Issue(
            identifier=f"AB#{item['id']}",
            title=fields["System.Title"],
            url=item.get("_links", {}).get("html", {}).get("href"),
            state_type=AzureDevOpsBoardsProvider._map_state(fields["System.State"]),
        )

    @staticmethod
    def _map_state(state: str) -> str:
        state_lower = state.lower()
        if any(keyword in state_lower for keyword in _ADO_CANCELLED_STATE_KEYWORDS):
            return "cancelled"
        if any(keyword in state_lower for keyword in _ADO_COMPLETED_STATE_KEYWORDS):
            return "completed"
        if any(keyword in state_lower for keyword in _ADO_STARTED_STATE_KEYWORDS):
            return "started"
        return "backlog"
