#!/usr/bin/env python3
"""
install.py
Interactive questionnaire that picks your ticket / code / notification stack
and writes the resulting configuration to .env.

Usage:
    python install.py
"""

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


def _ask_azure_devops_credentials(ask, env: dict) -> None:
    env["AZURE_DEVOPS_ORG"] = ask("Organisation Azure DevOps : ")
    env["AZURE_DEVOPS_PROJECT"] = ask("Projet Azure DevOps : ")
    env["AZURE_DEVOPS_PAT"] = ask("Personal Access Token Azure DevOps : ")


def _resolve_user_id_with_retry(ask, resolve_user_id, env: dict) -> str:
    while True:
        try:
            return resolve_user_id(env["AZURE_DEVOPS_ORG"], env["AZURE_DEVOPS_PAT"])
        except Exception as e:
            print(f"Impossible de valider le Personal Access Token Azure DevOps ({e}).")
            env["AZURE_DEVOPS_PAT"] = ask("Personal Access Token Azure DevOps : ")


def run_questionnaire(ask, resolve_user_id=resolve_azure_devops_user_id) -> dict:
    env: dict = {}

    ticket_choice = ask("Outil de tickets ? [1] Linear  [2] Azure DevOps Boards : ")
    if ticket_choice == "2":
        env["TICKET_PROVIDER"] = "azure_devops_boards"
        _ask_azure_devops_credentials(ask, env)
    else:
        env["TICKET_PROVIDER"] = "linear"
        env["LINEAR_TOKEN"] = ask("Ton Linear API token : ")

    code_choice = ask("Outil de code ? [1] GitHub  [2] Azure DevOps Repos : ")
    if code_choice == "2":
        env["CODE_PROVIDER"] = "azure_devops_repos"
        has_ado_creds = "AZURE_DEVOPS_ORG" in env
        reuse = ask("Réutiliser les identifiants Azure DevOps déjà saisis ? [y/n] : ") if has_ado_creds else "n"
        if not has_ado_creds or reuse.strip().lower() != "y":
            _ask_azure_devops_credentials(ask, env)
        env["AZURE_DEVOPS_USER_ID"] = _resolve_user_id_with_retry(ask, resolve_user_id, env)
    else:
        env["CODE_PROVIDER"] = "github"
        env["GITHUB_TOKEN"] = ask("Ton GitHub token (scope repo) : ")
        env["GITHUB_USERNAME"] = ask("Ton nom d'utilisateur GitHub : ")

    notify_choice = ask("Canal de notification ? [1] Slack  [2] Teams  [3] Aucun : ")
    if notify_choice == "2":
        env["NOTIFY_PROVIDER"] = "teams"
        env["TEAMS_WEBHOOK_URL"] = ask("URL du webhook entrant Teams : ")
    elif notify_choice == "3":
        env["NOTIFY_PROVIDER"] = "none"
    else:
        env["NOTIFY_PROVIDER"] = "slack"
        env["SLACK_WEBHOOK_URL"] = ask("URL du webhook entrant Slack : ")

    return env


def write_env_file(env: dict, path: str = _ENV_PATH) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for key, value in env.items():
            f.write(f"{key}={value}\n")


def main() -> None:
    if os.path.exists(_ENV_PATH):
        answer = input(f"Un .env existe déjà à {_ENV_PATH}. L'écraser ? [y/N] : ")
        if answer.strip().lower() != "y":
            print("Installation annulée.")
            return

    env = run_questionnaire(ask=input)
    write_env_file(env)
    print(f"\nConfiguration écrite dans {_ENV_PATH}. Lance `python standup.py` pour générer ton standup.")


if __name__ == "__main__":
    main()
