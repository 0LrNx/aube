from datetime import datetime, timezone

from providers.code import AzureDevOpsReposProvider, GitHubProvider
from standup_core.models import PullRequest, Review

_NOW = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class _FakeResponse:
    def __init__(self, payload, headers=None):
        self._payload = payload
        self.headers = headers or {}

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_github_provider_fetch_prs_maps_merged_and_opened(monkeypatch):
    def fake_get(url, headers=None, timeout=None):
        if "merged:" in url:
            return _FakeResponse(
                {
                    "items": [
                        {
                            "number": 1,
                            "title": "ABC-1: ship it",
                            "html_url": "https://github.com/x/pull/1",
                            "body": "Closes ABC-1",
                        }
                    ]
                }
            )
        if "created:" in url:
            return _FakeResponse(
                {"items": [{"number": 2, "title": "ABC-2: wip", "html_url": "https://github.com/x/pull/2"}]}
            )
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("providers.code.requests.get", fake_get)

    provider = GitHubProvider(token="ghtoken", username="octocat")
    prs = provider.fetch_prs(lookback_days=1)

    assert prs["merged"] == [
        PullRequest(
            number=1, title="ABC-1: ship it", url="https://github.com/x/pull/1", description="Closes ABC-1"
        )
    ]
    assert prs["opened"] == [PullRequest(number=2, title="ABC-2: wip", url="https://github.com/x/pull/2")]


def test_github_provider_fetch_prs_passes_timeout_and_raises_on_http_error(monkeypatch):
    captured = {}

    class _FailingResponse:
        def __init__(self, url):
            self._url = url

        def raise_for_status(self):
            raise RuntimeError(f"403 rate limited: {self._url}")

        def json(self):
            raise AssertionError("json() should not be reached once raise_for_status raised")

    def fake_get(url, headers=None, timeout=None):
        captured["timeout"] = timeout
        return _FailingResponse(url)

    monkeypatch.setattr("providers.code.requests.get", fake_get)

    provider = GitHubProvider(token="ghtoken", username="octocat")

    try:
        provider.fetch_prs(lookback_days=1)
        raise AssertionError("expected fetch_prs to propagate the HTTP error")
    except RuntimeError as e:
        assert "403 rate limited" in str(e)

    assert captured["timeout"] == 15


def test_github_provider_fetch_reviews_maps_to_review_model(monkeypatch):
    def fake_get(url, headers=None, timeout=None):
        assert "reviewed-by:octocat" in url
        return _FakeResponse(
            {
                "items": [
                    {
                        "number": 9,
                        "title": "Add tests",
                        "html_url": "https://github.com/x/pull/9",
                        "user": {"login": "someone-else"},
                    }
                ]
            }
        )

    monkeypatch.setattr("providers.code.requests.get", fake_get)

    provider = GitHubProvider(token="ghtoken", username="octocat")
    reviews = provider.fetch_reviews(lookback_days=1)

    assert reviews == [
        Review(number=9, title="Add tests", url="https://github.com/x/pull/9", author="someone-else")
    ]


def test_github_provider_validate_credentials_warns_when_missing_repo_scope(monkeypatch, capsys):
    def fake_get(url, headers=None, timeout=None):
        return _FakeResponse({}, headers={"X-OAuth-Scopes": "public_repo"})

    monkeypatch.setattr("providers.code.requests.get", fake_get)

    provider = GitHubProvider(token="ghtoken", username="octocat")
    provider.validate_credentials()

    assert "missing the 'repo' scope" in capsys.readouterr().out


def test_github_provider_validate_credentials_silent_when_repo_scope_present(monkeypatch, capsys):
    def fake_get(url, headers=None, timeout=None):
        return _FakeResponse({}, headers={"X-OAuth-Scopes": "repo, gist"})

    monkeypatch.setattr("providers.code.requests.get", fake_get)

    provider = GitHubProvider(token="ghtoken", username="octocat")
    provider.validate_credentials()

    assert capsys.readouterr().out == ""


def test_ado_repos_provider_fetch_prs_maps_merged_and_opened(monkeypatch):
    def fake_get(url, headers=None, timeout=None):
        assert "dev.azure.com/my-org/my-project/_apis/git/pullrequests" in url
        if "searchCriteria.status=completed" in url:
            return _FakeResponse(
                {
                    "value": [
                        {
                            "pullRequestId": 1,
                            "title": "ABC-1: ship it",
                            "description": "Fixes AB#1",
                            "closedDate": _NOW,
                            "creationDate": _NOW,
                            "repository": {"webUrl": "https://dev.azure.com/my-org/my-project/_git/repo"},
                        }
                    ]
                }
            )
        if "searchCriteria.status=active" in url:
            return _FakeResponse(
                {
                    "value": [
                        {
                            "pullRequestId": 2,
                            "title": "ABC-2: wip",
                            "creationDate": _NOW,
                            "repository": {"webUrl": "https://dev.azure.com/my-org/my-project/_git/repo"},
                        }
                    ]
                }
            )
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("providers.code.requests.get", fake_get)

    provider = AzureDevOpsReposProvider(organization="my-org", project="my-project", token="pat-token")
    prs = provider.fetch_prs(lookback_days=1)

    assert prs["merged"] == [
        PullRequest(
            number=1,
            title="ABC-1: ship it",
            url="https://dev.azure.com/my-org/my-project/_git/repo/pullrequest/1",
            description="Fixes AB#1",
        )
    ]
    assert prs["opened"] == [
        PullRequest(
            number=2,
            title="ABC-2: wip",
            url="https://dev.azure.com/my-org/my-project/_git/repo/pullrequest/2",
        )
    ]


def test_ado_repos_provider_fetch_prs_excludes_pull_requests_outside_lookback_window(monkeypatch):
    def fake_get(url, headers=None, timeout=None):
        if "searchCriteria.status=completed" in url:
            return _FakeResponse(
                {
                    "value": [
                        {
                            "pullRequestId": 1,
                            "title": "ABC-1: too old",
                            "closedDate": "2020-01-01T10:00:00Z",
                            "creationDate": "2019-12-31T10:00:00Z",
                            "repository": {"webUrl": "https://dev.azure.com/my-org/my-project/_git/repo"},
                        }
                    ]
                }
            )
        return _FakeResponse({"value": []})

    monkeypatch.setattr("providers.code.requests.get", fake_get)

    provider = AzureDevOpsReposProvider(organization="my-org", project="my-project", token="pat-token")
    prs = provider.fetch_prs(lookback_days=1)

    assert prs["merged"] == []


def test_ado_repos_provider_fetch_reviews_maps_to_review_model_excluding_own_prs(monkeypatch):
    def fake_get(url, headers=None, timeout=None):
        assert "searchCriteria.reviewerId=my-user-id" in url
        return _FakeResponse(
            {
                "value": [
                    {
                        "pullRequestId": 9,
                        "title": "Add tests",
                        "creationDate": _NOW,
                        "createdBy": {"displayName": "someone-else", "id": "other-user-id"},
                        "repository": {"webUrl": "https://dev.azure.com/my-org/my-project/_git/repo"},
                    },
                    {
                        "pullRequestId": 10,
                        "title": "My own PR I also reviewed",
                        "creationDate": _NOW,
                        "createdBy": {"displayName": "me", "id": "my-user-id"},
                        "repository": {"webUrl": "https://dev.azure.com/my-org/my-project/_git/repo"},
                    },
                ]
            }
        )

    monkeypatch.setattr("providers.code.requests.get", fake_get)

    provider = AzureDevOpsReposProvider(
        organization="my-org", project="my-project", token="pat-token", reviewer_id="my-user-id"
    )
    reviews = provider.fetch_reviews(lookback_days=1)

    assert reviews == [
        Review(
            number=9,
            title="Add tests",
            url="https://dev.azure.com/my-org/my-project/_git/repo/pullrequest/9",
            author="someone-else",
        )
    ]


def test_ado_repos_provider_url_encodes_project_name_with_spaces(monkeypatch):
    captured = {}

    def fake_get(url, headers=None, timeout=None):
        captured["url"] = url
        return _FakeResponse({"value": []})

    monkeypatch.setattr("providers.code.requests.get", fake_get)

    provider = AzureDevOpsReposProvider(organization="my-org", project="Team Project 1", token="pat-token")
    provider.fetch_prs(lookback_days=1)

    assert "Team%20Project%201" in captured["url"]
    assert " " not in captured["url"]


def test_ado_repos_provider_validate_credentials_is_a_silent_noop():
    provider = AzureDevOpsReposProvider(organization="my-org", project="my-project", token="pat-token")

    provider.validate_credentials()
