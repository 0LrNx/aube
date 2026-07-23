"""Builds the configured providers from an environment mapping (os.environ or a plain dict)."""

from providers.code import AzureDevOpsReposProvider, CodeProvider, GitHubProvider
from providers.notify import NotificationSink, NullNotifier, SlackNotifier, TeamsNotifier
from providers.tickets import AzureDevOpsBoardsProvider, LinearProvider, TicketProvider

TICKET_PROVIDER_REQUIRED_ENV = {
    "linear": ("LINEAR_TOKEN",),
    "azure_devops_boards": ("AZURE_DEVOPS_ORG", "AZURE_DEVOPS_PROJECT", "AZURE_DEVOPS_PAT"),
}

CODE_PROVIDER_REQUIRED_ENV = {
    "github": ("GITHUB_TOKEN", "GITHUB_USERNAME"),
    "azure_devops_repos": ("AZURE_DEVOPS_ORG", "AZURE_DEVOPS_PROJECT", "AZURE_DEVOPS_PAT", "AZURE_DEVOPS_USER_ID"),
}


def build_ticket_provider(env: dict) -> TicketProvider:
    if env.get("TICKET_PROVIDER", "linear") == "azure_devops_boards":
        return AzureDevOpsBoardsProvider(
            organization=env["AZURE_DEVOPS_ORG"],
            project=env["AZURE_DEVOPS_PROJECT"],
            token=env["AZURE_DEVOPS_PAT"],
        )
    return LinearProvider(token=env["LINEAR_TOKEN"])


def build_code_provider(env: dict) -> CodeProvider:
    if env.get("CODE_PROVIDER", "github") == "azure_devops_repos":
        user_id = env.get("AZURE_DEVOPS_USER_ID")
        return AzureDevOpsReposProvider(
            organization=env["AZURE_DEVOPS_ORG"],
            project=env["AZURE_DEVOPS_PROJECT"],
            token=env["AZURE_DEVOPS_PAT"],
            creator_id=user_id,
            reviewer_id=user_id,
        )
    return GitHubProvider(token=env["GITHUB_TOKEN"], username=env["GITHUB_USERNAME"])


def build_notifier(env: dict) -> NotificationSink:
    provider = env.get("NOTIFY_PROVIDER", "slack")
    if provider == "teams":
        return TeamsNotifier(webhook_url=env.get("TEAMS_WEBHOOK_URL", ""))
    if provider == "none":
        return NullNotifier()
    return SlackNotifier(webhook_url=env.get("SLACK_WEBHOOK_URL", ""))


def required_env(env: dict) -> tuple[str, ...]:
    ticket_provider = env.get("TICKET_PROVIDER", "linear")
    code_provider = env.get("CODE_PROVIDER", "github")

    required = dict.fromkeys(
        TICKET_PROVIDER_REQUIRED_ENV.get(ticket_provider, TICKET_PROVIDER_REQUIRED_ENV["linear"])
    )
    required.update(
        dict.fromkeys(CODE_PROVIDER_REQUIRED_ENV.get(code_provider, CODE_PROVIDER_REQUIRED_ENV["github"]))
    )
    return tuple(required)
