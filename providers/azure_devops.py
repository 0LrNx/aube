"""Shared Azure DevOps auth — Boards, Repos, and the installer all authenticate with a PAT the same way."""

import base64
from urllib.parse import quote


def basic_auth_header(token: str) -> dict:
    credentials = base64.b64encode(f":{token}".encode()).decode()
    return {"Authorization": f"Basic {credentials}"}


def url_segment(value: str) -> str:
    """URL-encode an organization/project name for safe use as a URL path segment (e.g. spaces)."""
    return quote(value, safe="")
