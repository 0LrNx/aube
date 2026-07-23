from providers.tickets import AzureDevOpsBoardsProvider, LinearProvider
from standup_core.models import Issue


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_linear_provider_maps_graphql_response_to_issues(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, **kwargs):
        captured["url"] = url
        captured["headers"] = headers
        return _FakeResponse(
            {
                "data": {
                    "viewer": {
                        "assignedIssues": {
                            "nodes": [
                                {
                                    "identifier": "ABC-1",
                                    "title": "Ship feature",
                                    "url": "https://linear.app/x/issue/ABC-1",
                                    "state": {"name": "Done", "type": "completed"},
                                    "updatedAt": "2026-07-22T00:00:00Z",
                                }
                            ]
                        }
                    }
                }
            }
        )

    monkeypatch.setattr("providers.tickets.requests.post", fake_post)

    provider = LinearProvider(token="secret-token")
    issues = provider.fetch_issues(lookback_days=1)

    assert issues == [
        Issue(
            identifier="ABC-1",
            title="Ship feature",
            url="https://linear.app/x/issue/ABC-1",
            state_type="completed",
        )
    ]
    assert captured["url"] == "https://api.linear.app/graphql"
    assert captured["headers"]["Authorization"] == "secret-token"


def test_azure_devops_boards_provider_maps_work_items_to_issues(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, **kwargs):
        captured["wiql_url"] = url
        captured["wiql_headers"] = headers
        return _FakeResponse({"workItems": [{"id": 1}, {"id": 2}]})

    def fake_get(url, headers=None, **kwargs):
        captured["workitems_url"] = url
        captured["workitems_headers"] = headers
        return _FakeResponse(
            {
                "value": [
                    {
                        "id": 1,
                        "fields": {"System.Title": "Ship feature", "System.State": "Closed"},
                        "_links": {"html": {"href": "https://dev.azure.com/x/y/_workitems/edit/1"}},
                    },
                    {
                        "id": 2,
                        "fields": {"System.Title": "Work on thing", "System.State": "Active"},
                        "_links": {"html": {"href": "https://dev.azure.com/x/y/_workitems/edit/2"}},
                    },
                ]
            }
        )

    monkeypatch.setattr("providers.tickets.requests.post", fake_post)
    monkeypatch.setattr("providers.tickets.requests.get", fake_get)

    provider = AzureDevOpsBoardsProvider(organization="org", project="proj", token="pat-token")
    issues = provider.fetch_issues(lookback_days=1)

    assert issues == [
        Issue(
            identifier="AB#1",
            title="Ship feature",
            url="https://dev.azure.com/x/y/_workitems/edit/1",
            state_type="completed",
        ),
        Issue(
            identifier="AB#2",
            title="Work on thing",
            url="https://dev.azure.com/x/y/_workitems/edit/2",
            state_type="started",
        ),
    ]
    assert "dev.azure.com/org/proj/_apis/wit/wiql" in captured["wiql_url"]
    assert "dev.azure.com/org/proj/_apis/wit/workitems" in captured["workitems_url"]
    assert captured["wiql_headers"]["Authorization"].startswith("Basic ")


def test_azure_devops_boards_provider_maps_removed_state_to_cancelled(monkeypatch):
    def fake_post(url, headers=None, json=None, **kwargs):
        return _FakeResponse({"workItems": [{"id": 3}]})

    def fake_get(url, headers=None, **kwargs):
        return _FakeResponse(
            {
                "value": [
                    {
                        "id": 3,
                        "fields": {"System.Title": "Dropped idea", "System.State": "Removed"},
                        "_links": {"html": {"href": "https://dev.azure.com/x/y/_workitems/edit/3"}},
                    }
                ]
            }
        )

    monkeypatch.setattr("providers.tickets.requests.post", fake_post)
    monkeypatch.setattr("providers.tickets.requests.get", fake_get)

    provider = AzureDevOpsBoardsProvider(organization="org", project="proj", token="pat-token")
    issues = provider.fetch_issues(lookback_days=1)

    assert issues[0].state_type == "cancelled"


def test_azure_devops_boards_provider_url_encodes_project_name_with_spaces(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, **kwargs):
        captured["wiql_url"] = url
        return _FakeResponse({"workItems": []})

    monkeypatch.setattr("providers.tickets.requests.post", fake_post)

    provider = AzureDevOpsBoardsProvider(organization="my-org", project="Team Project 1", token="pat-token")
    provider.fetch_issues(lookback_days=1)

    assert "Team%20Project%201" in captured["wiql_url"]
    assert " " not in captured["wiql_url"]


def test_azure_devops_boards_provider_returns_empty_when_no_work_items(monkeypatch):
    def fake_post(url, headers=None, json=None, **kwargs):
        return _FakeResponse({"workItems": []})

    def fake_get(url, headers=None, **kwargs):
        raise AssertionError("should not fetch work item details when there are no ids")

    monkeypatch.setattr("providers.tickets.requests.post", fake_post)
    monkeypatch.setattr("providers.tickets.requests.get", fake_get)

    provider = AzureDevOpsBoardsProvider(organization="org", project="proj", token="pat-token")
    issues = provider.fetch_issues(lookback_days=1)

    assert issues == []
