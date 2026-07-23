"""Normalized data model shared by every ticket/code/notification provider."""

from dataclasses import dataclass


@dataclass
class Issue:
    identifier: str
    title: str
    url: str | None
    state_type: str  # "completed" | "cancelled" | "started" | "backlog" | ...


@dataclass
class PullRequest:
    number: int
    title: str
    url: str | None
    description: str | None = None


@dataclass
class Review:
    number: int
    title: str
    url: str | None
    author: str
