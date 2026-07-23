from providers.code import AzureDevOpsReposProvider, GitHubProvider
from providers.factory import build_code_provider, build_notifier, build_ticket_provider, required_env
from providers.notify import NullNotifier, SlackNotifier, TeamsNotifier
from providers.tickets import AzureDevOpsBoardsProvider, LinearProvider


def test_build_ticket_provider_defaults_to_linear():
    provider = build_ticket_provider({"LINEAR_TOKEN": "lin-token"})

    assert isinstance(provider, LinearProvider)
    assert provider.token == "lin-token"


def test_build_ticket_provider_azure_devops_boards():
    provider = build_ticket_provider(
        {
            "TICKET_PROVIDER": "azure_devops_boards",
            "AZURE_DEVOPS_ORG": "my-org",
            "AZURE_DEVOPS_PROJECT": "my-project",
            "AZURE_DEVOPS_PAT": "my-pat",
        }
    )

    assert isinstance(provider, AzureDevOpsBoardsProvider)
    assert provider.organization == "my-org"
    assert provider.project == "my-project"
    assert provider.token == "my-pat"


def test_build_code_provider_defaults_to_github():
    provider = build_code_provider({"GITHUB_TOKEN": "gh-token", "GITHUB_USERNAME": "octocat"})

    assert isinstance(provider, GitHubProvider)
    assert provider.token == "gh-token"
    assert provider.username == "octocat"


def test_build_code_provider_azure_devops_repos():
    provider = build_code_provider(
        {
            "CODE_PROVIDER": "azure_devops_repos",
            "AZURE_DEVOPS_ORG": "my-org",
            "AZURE_DEVOPS_PROJECT": "my-project",
            "AZURE_DEVOPS_PAT": "my-pat",
            "AZURE_DEVOPS_USER_ID": "user-guid",
        }
    )

    assert isinstance(provider, AzureDevOpsReposProvider)
    assert provider.organization == "my-org"
    assert provider.creator_id == "user-guid"
    assert provider.reviewer_id == "user-guid"


def test_build_notifier_defaults_to_slack():
    notifier = build_notifier({"SLACK_WEBHOOK_URL": "https://hooks.slack.com/x"})

    assert isinstance(notifier, SlackNotifier)
    assert notifier.webhook_url == "https://hooks.slack.com/x"


def test_build_notifier_teams():
    notifier = build_notifier({"NOTIFY_PROVIDER": "teams", "TEAMS_WEBHOOK_URL": "https://outlook.office.com/x"})

    assert isinstance(notifier, TeamsNotifier)
    assert notifier.webhook_url == "https://outlook.office.com/x"


def test_build_notifier_none():
    notifier = build_notifier({"NOTIFY_PROVIDER": "none"})

    assert isinstance(notifier, NullNotifier)


def test_required_env_defaults_to_linear_and_github():
    assert required_env({}) == ("LINEAR_TOKEN", "GITHUB_TOKEN", "GITHUB_USERNAME")


def test_required_env_azure_devops_boards_tickets():
    required = required_env({"TICKET_PROVIDER": "azure_devops_boards"})

    assert "AZURE_DEVOPS_ORG" in required
    assert "AZURE_DEVOPS_PROJECT" in required
    assert "AZURE_DEVOPS_PAT" in required
    assert "LINEAR_TOKEN" not in required


def test_required_env_azure_devops_repos_code():
    required = required_env({"CODE_PROVIDER": "azure_devops_repos"})

    assert "AZURE_DEVOPS_ORG" in required
    assert "AZURE_DEVOPS_PROJECT" in required
    assert "AZURE_DEVOPS_PAT" in required
    assert "AZURE_DEVOPS_USER_ID" in required
    assert "GITHUB_TOKEN" not in required
    assert "GITHUB_USERNAME" not in required


def test_required_env_azure_devops_for_both_does_not_duplicate_shared_vars():
    required = required_env({"TICKET_PROVIDER": "azure_devops_boards", "CODE_PROVIDER": "azure_devops_repos"})

    assert required.count("AZURE_DEVOPS_ORG") == 1
    assert required.count("AZURE_DEVOPS_PROJECT") == 1
    assert required.count("AZURE_DEVOPS_PAT") == 1


def test_required_env_never_requires_notification_credentials():
    for notify_provider in ("slack", "teams", "none"):
        required = required_env({"NOTIFY_PROVIDER": notify_provider})
        assert "SLACK_WEBHOOK_URL" not in required
        assert "TEAMS_WEBHOOK_URL" not in required
