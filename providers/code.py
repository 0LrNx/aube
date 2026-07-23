"""Code sources: fetch a user's PRs and reviews, normalized to the shared model."""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone

import requests

from providers.azure_devops import basic_auth_header, url_segment
from standup_core.models import PullRequest, Review


class CodeProvider(ABC):
    @abstractmethod
    def fetch_prs(self, lookback_days: int) -> dict:
        ...

    @abstractmethod
    def fetch_reviews(self, lookback_days: int) -> list[Review]:
        ...

    def validate_credentials(self) -> None:
        """Optional pre-flight check; providers override this to warn about misconfigured tokens."""


class GitHubProvider(CodeProvider):
    def __init__(self, token: str, username: str):
        self.token = token
        self.username = username

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }

    def _window(self, lookback_days: int) -> tuple[str, str]:
        since = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")
        return since, today

    def validate_credentials(self) -> None:
        resp = requests.get("https://api.github.com/user", headers=self._headers, timeout=15)
        resp.raise_for_status()
        raw = resp.headers.get("X-OAuth-Scopes", "")
        scopes = {scope.strip() for scope in raw.split(",") if scope.strip()}
        if "repo" in scopes:
            return
        print(
            "WARNING: GITHUB_TOKEN is missing the 'repo' scope "
            f"(current scopes: {', '.join(sorted(scopes)) or 'none'}). "
            "GitHub PRs and code reviews will be empty. "
            "Regenerate a classic token with 'repo' at "
            "https://github.com/settings/tokens"
        )

    def fetch_prs(self, lookback_days: int) -> dict:
        since, today = self._window(lookback_days)

        merged_url = (
            "https://api.github.com/search/issues"
            f"?q=author:{self.username}+type:pr+merged:{since}..{today}"
            "&per_page=20"
        )
        opened_url = (
            "https://api.github.com/search/issues"
            f"?q=author:{self.username}+type:pr+created:{since}..{today}"
            "&per_page=20"
        )

        merged_resp = requests.get(merged_url, headers=self._headers, timeout=15)
        merged_resp.raise_for_status()
        opened_resp = requests.get(opened_url, headers=self._headers, timeout=15)
        opened_resp.raise_for_status()

        merged = merged_resp.json().get("items", [])
        opened = opened_resp.json().get("items", [])

        return {
            "merged": [self._to_pull_request(item) for item in merged],
            "opened": [self._to_pull_request(item) for item in opened],
        }

    def fetch_reviews(self, lookback_days: int) -> list[Review]:
        since, today = self._window(lookback_days)

        url = (
            "https://api.github.com/search/issues"
            f"?q=reviewed-by:{self.username}+-author:{self.username}+type:pr+updated:{since}..{today}"
            "&per_page=20"
        )
        resp = requests.get(url, headers=self._headers, timeout=30)
        resp.raise_for_status()
        items = resp.json().get("items", [])
        return [
            Review(
                number=item["number"],
                title=item["title"],
                url=item.get("html_url"),
                author=item["user"]["login"],
            )
            for item in items
        ]

    @staticmethod
    def _to_pull_request(item: dict) -> PullRequest:
        return PullRequest(
            number=item["number"],
            title=item["title"],
            url=item.get("html_url"),
            description=item.get("body"),
        )


class AzureDevOpsReposProvider(CodeProvider):
    """Fetches PRs/reviews across all repos of an Azure DevOps project, via PAT auth."""

    def __init__(
        self,
        organization: str,
        project: str,
        token: str,
        creator_id: str | None = None,
        reviewer_id: str | None = None,
    ):
        self.organization = organization
        self.project = project
        self.token = token
        self.creator_id = creator_id
        self.reviewer_id = reviewer_id

    @property
    def _headers(self) -> dict:
        return basic_auth_header(self.token)

    def _fetch(self, status: str, extra_query: str) -> list[dict]:
        org, project = url_segment(self.organization), url_segment(self.project)
        url = (
            f"https://dev.azure.com/{org}/{project}/_apis/git/pullrequests"
            f"?api-version=7.0&searchCriteria.status={status}{extra_query}"
        )
        resp = requests.get(url, headers=self._headers, timeout=15)
        resp.raise_for_status()
        return resp.json().get("value", [])

    def fetch_prs(self, lookback_days: int) -> dict:
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        creator_query = f"&searchCriteria.creatorId={self.creator_id}" if self.creator_id else ""

        merged_items = self._fetch("completed", creator_query)
        opened_items = self._fetch("active", creator_query)

        merged = [
            self._to_pull_request(item)
            for item in merged_items
            if self._parse_date(item.get("closedDate") or item["creationDate"]) >= cutoff
        ]
        opened = [
            self._to_pull_request(item)
            for item in opened_items
            if self._parse_date(item["creationDate"]) >= cutoff
        ]
        return {"merged": merged, "opened": opened}

    def fetch_reviews(self, lookback_days: int) -> list[Review]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        reviewer_query = f"&searchCriteria.reviewerId={self.reviewer_id}" if self.reviewer_id else ""

        reviews = []
        for item in self._fetch("all", reviewer_query):
            author = item["createdBy"]
            if self.reviewer_id and author.get("id") == self.reviewer_id:
                continue
            if self._parse_date(item["creationDate"]) < cutoff:
                continue
            reviews.append(
                Review(
                    number=item["pullRequestId"],
                    title=item["title"],
                    url=self._pr_url(item),
                    author=author["displayName"],
                )
            )
        return reviews

    @staticmethod
    def _parse_date(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    @staticmethod
    def _pr_url(item: dict) -> str:
        return f"{item['repository']['webUrl']}/pullrequest/{item['pullRequestId']}"

    @staticmethod
    def _to_pull_request(item: dict) -> PullRequest:
        return PullRequest(
            number=item["pullRequestId"],
            title=item["title"],
            url=AzureDevOpsReposProvider._pr_url(item),
            description=item.get("description"),
        )
