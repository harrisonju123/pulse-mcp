"""Data models for IC Tracker."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class GitHubConfig:
    token: str
    org: str
    repos: list[str]


@dataclass
class TeamMember:
    github_username: str
    atlassian_account_id: str
    name: str


@dataclass
class ConfluenceConfig:
    base_url: str  # e.g. https://justworks.atlassian.net/wiki
    email: str
    api_token: str
    space_keys: list[str]  # e.g. ["ENGG"]


@dataclass
class Config:
    github: GitHubConfig
    team_members: dict[str, TeamMember]
    confluence: Optional[ConfluenceConfig] = None


@dataclass
class PullRequest:
    number: int
    title: str
    repo: str
    state: str
    merged: bool
    additions: int = 0
    deletions: int = 0
    url: str = ""
    created_at: Optional[datetime] = None
    merged_at: Optional[datetime] = None


@dataclass
class CodeReview:
    pr_number: int
    pr_title: str
    repo: str
    state: str
    url: str
    submitted_at: Optional[datetime] = None


@dataclass
class CommitInfo:
    sha: str
    message: str
    repo: str
    url: str
    authored_at: Optional[datetime] = None


@dataclass
class GitHubContributions:
    """Aggregated GitHub contributions for a team member."""
    prs_merged: list[dict] = field(default_factory=list)
    reviews_given: list[dict] = field(default_factory=list)
    total_additions: int = 0
    total_deletions: int = 0


@dataclass
class ConfluencePage:
    id: str
    title: str
    space_key: str
    type: str  # "page" or "blogpost"
    url: str
    created: Optional[datetime]
    updated: Optional[datetime]


@dataclass
class ConfluenceContributions:
    """Aggregated Confluence contributions for a team member."""
    pages_created: list[dict] = field(default_factory=list)
    pages_updated: list[dict] = field(default_factory=list)
    comments_added: list[dict] = field(default_factory=list)
    blogposts: list[dict] = field(default_factory=list)
