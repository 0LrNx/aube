from install import resolve_azure_devops_user_id, run_questionnaire, write_env_file


def _scripted_ask(responses):
    it = iter(responses)
    return lambda prompt: next(it)


def test_questionnaire_linear_github_slack():
    ask = _scripted_ask(["1", "lin-token", "1", "gh-token", "octocat", "1", "https://hooks.slack.com/x"])

    env = run_questionnaire(ask)

    assert env == {
        "TICKET_PROVIDER": "linear",
        "LINEAR_TOKEN": "lin-token",
        "CODE_PROVIDER": "github",
        "GITHUB_TOKEN": "gh-token",
        "GITHUB_USERNAME": "octocat",
        "NOTIFY_PROVIDER": "slack",
        "SLACK_WEBHOOK_URL": "https://hooks.slack.com/x",
    }


def test_questionnaire_no_notification_channel():
    ask = _scripted_ask(["1", "lin-token", "1", "gh-token", "octocat", "3"])

    env = run_questionnaire(ask)

    assert env["NOTIFY_PROVIDER"] == "none"
    assert "SLACK_WEBHOOK_URL" not in env
    assert "TEAMS_WEBHOOK_URL" not in env


def test_questionnaire_azure_devops_for_both_tickets_and_code_reuses_credentials():
    ask = _scripted_ask(
        [
            "2", "my-org", "my-project", "my-pat",  # tickets: Azure DevOps Boards
            "2", "y",  # code: Azure DevOps Repos, reuse credentials
            "2", "https://outlook.office.com/webhook/x",  # notify: Teams
        ]
    )

    env = run_questionnaire(ask, resolve_user_id=lambda org, token: "resolved-user-id")

    assert env["TICKET_PROVIDER"] == "azure_devops_boards"
    assert env["CODE_PROVIDER"] == "azure_devops_repos"
    assert env["AZURE_DEVOPS_ORG"] == "my-org"
    assert env["AZURE_DEVOPS_PROJECT"] == "my-project"
    assert env["AZURE_DEVOPS_PAT"] == "my-pat"
    assert env["AZURE_DEVOPS_USER_ID"] == "resolved-user-id"
    assert env["NOTIFY_PROVIDER"] == "teams"
    assert env["TEAMS_WEBHOOK_URL"] == "https://outlook.office.com/webhook/x"


def test_questionnaire_azure_devops_for_code_only_asks_credentials_once():
    ask = _scripted_ask(
        [
            "1", "lin-token",  # tickets: Linear
            "2", "my-org", "my-project", "my-pat",  # code: Azure DevOps Repos (no reuse prompt, fresh creds)
            "3",  # notify: none
        ]
    )

    env = run_questionnaire(ask, resolve_user_id=lambda org, token: "resolved-user-id")

    assert env["TICKET_PROVIDER"] == "linear"
    assert env["CODE_PROVIDER"] == "azure_devops_repos"
    assert env["AZURE_DEVOPS_ORG"] == "my-org"
    assert env["AZURE_DEVOPS_USER_ID"] == "resolved-user-id"


def test_questionnaire_declining_reuse_asks_for_fresh_azure_devops_credentials():
    ask = _scripted_ask(
        [
            "2", "board-org", "board-project", "board-pat",  # tickets: Azure DevOps Boards
            "2", "n", "repo-org", "repo-project", "repo-pat",  # code: decline reuse, fresh creds
            "3",  # notify: none
        ]
    )

    env = run_questionnaire(ask, resolve_user_id=lambda org, token: "resolved-user-id")

    assert env["AZURE_DEVOPS_ORG"] == "repo-org"
    assert env["AZURE_DEVOPS_PROJECT"] == "repo-project"
    assert env["AZURE_DEVOPS_PAT"] == "repo-pat"


def test_questionnaire_retries_azure_devops_credentials_when_resolution_fails():
    attempts = {"n": 0}

    def flaky_resolve_user_id(organization, token):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("401 Unauthorized")
        return "resolved-user-id"

    ask = _scripted_ask(
        [
            "1", "lin-token",  # tickets: Linear
            "2", "my-org", "my-project", "bad-pat",  # code: Azure DevOps Repos, first PAT is invalid
            "good-pat",  # retry: re-enter just the PAT
            "3",  # notify: none
        ]
    )

    env = run_questionnaire(ask, resolve_user_id=flaky_resolve_user_id)

    assert env["AZURE_DEVOPS_PAT"] == "good-pat"
    assert env["AZURE_DEVOPS_USER_ID"] == "resolved-user-id"
    assert attempts["n"] == 2


def test_write_env_file_writes_key_value_pairs(tmp_path):
    env_path = tmp_path / ".env"

    write_env_file({"FOO": "bar", "BAZ": "qux"}, str(env_path))

    content = env_path.read_text(encoding="utf-8")
    assert "FOO=bar" in content
    assert "BAZ=qux" in content


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_resolve_azure_devops_user_id_calls_profile_api(monkeypatch):
    captured = {}

    def fake_get(url, headers=None, **kwargs):
        captured["url"] = url
        captured["headers"] = headers
        return _FakeResponse({"id": "user-guid-123"})

    monkeypatch.setattr("install.requests.get", fake_get)

    user_id = resolve_azure_devops_user_id("my-org", "my-pat")

    assert user_id == "user-guid-123"
    assert "vssps.dev.azure.com/my-org" in captured["url"]
    assert captured["headers"]["Authorization"].startswith("Basic ")
