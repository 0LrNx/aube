#!/usr/bin/env python3
"""
install.py
Interactive questionnaire that picks your ticket / code / notification stack
and writes the resulting configuration to .env.

Usage:
    python install.py
"""

import getpass
import os

import requests

from providers.azure_devops import basic_auth_header, url_segment

_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")


def resolve_azure_devops_user_id(organization: str, token: str) -> str:
    resp = requests.get(
        f"https://vssps.dev.azure.com/{url_segment(organization)}/_apis/profile/profiles/me?api-version=7.0",
        headers=basic_auth_header(token),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def _ask_azure_devops_credentials(ask, ask_secret, env: dict) -> None:
    env["AZURE_DEVOPS_ORG"] = ask("Azure DevOps organization: ")
    env["AZURE_DEVOPS_PROJECT"] = ask("Azure DevOps project: ")
    env["AZURE_DEVOPS_PAT"] = ask_secret("Azure DevOps Personal Access Token: ")


def _resolve_user_id_with_retry(ask, ask_secret, resolve_user_id, env: dict) -> str:
    while True:
        try:
            return resolve_user_id(env["AZURE_DEVOPS_ORG"], env["AZURE_DEVOPS_PAT"])
        except Exception as e:
            print(f"Could not validate the Azure DevOps organization or Personal Access Token ({e}).")
            env["AZURE_DEVOPS_ORG"] = ask("Azure DevOps organization: ")
            env["AZURE_DEVOPS_PAT"] = ask_secret("Azure DevOps Personal Access Token: ")


def run_questionnaire(ask, resolve_user_id=resolve_azure_devops_user_id, ask_secret=None) -> dict:
    # Tokens and webhook URLs are secrets: read them without echoing when a secret prompt is given.
    ask_secret = ask_secret or ask
    env: dict = {}

    ticket_choice = ask("Ticket source? [1] Linear  [2] Azure DevOps Boards: ")
    if ticket_choice == "2":
        env["TICKET_PROVIDER"] = "azure_devops_boards"
        _ask_azure_devops_credentials(ask, ask_secret, env)
    else:
        env["TICKET_PROVIDER"] = "linear"
        env["LINEAR_TOKEN"] = ask_secret("Linear API token: ")

    code_choice = ask("Code source? [1] GitHub  [2] Azure DevOps Repos: ")
    if code_choice == "2":
        env["CODE_PROVIDER"] = "azure_devops_repos"
        has_ado_creds = "AZURE_DEVOPS_ORG" in env
        reuse = ask("Reuse the Azure DevOps credentials entered above? [y/n]: ") if has_ado_creds else "n"
        if not has_ado_creds or reuse.strip().lower() != "y":
            _ask_azure_devops_credentials(ask, ask_secret, env)
        env["AZURE_DEVOPS_USER_ID"] = _resolve_user_id_with_retry(ask, ask_secret, resolve_user_id, env)
    else:
        env["CODE_PROVIDER"] = "github"
        env["GITHUB_TOKEN"] = ask_secret("GitHub token (repo scope): ")
        env["GITHUB_USERNAME"] = ask("GitHub username: ")

    notify_choice = ask("Notification channel? [1] Slack  [2] Teams  [3] None: ")
    if notify_choice == "2":
        env["NOTIFY_PROVIDER"] = "teams"
        env["TEAMS_WEBHOOK_URL"] = ask_secret("Teams webhook URL: ")
    elif notify_choice == "3":
        env["NOTIFY_PROVIDER"] = "none"
    else:
        env["NOTIFY_PROVIDER"] = "slack"
        env["SLACK_WEBHOOK_URL"] = ask_secret("Slack incoming webhook URL: ")

    return env


def write_env_file(env: dict, path: str = _ENV_PATH) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for key, value in env.items():
            f.write(f"{key}={value}\n")


def main() -> None:
    if os.path.exists(_ENV_PATH):
        answer = input(f"A .env already exists at {_ENV_PATH}. Overwrite it? [y/N]: ")
        if answer.strip().lower() != "y":
            print("Installation cancelled.")
            return

    env = run_questionnaire(ask=input, ask_secret=getpass.getpass)
    write_env_file(env)
    print(f"\nConfiguration written to {_ENV_PATH}. Run `python standup.py` to generate your standup.")


if __name__ == "__main__":
    main()
