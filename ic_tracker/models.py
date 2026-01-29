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
class Team:
    id: str
    name: str
    members: dict[str, "TeamMember"]


@dataclass
class ConfluenceConfig:
    base_url: str  # e.g. https://yourcompany.atlassian.net/wiki
    email: str
    api_token: str
    space_keys: list[str]  # e.g. ["ENGG"]


@dataclass
class JiraConfig:
    base_url: str  # e.g. https://yourcompany.atlassian.net
    email: str
    api_token: str
    project_keys: list[str]  # e.g. ["PROJ", "INFRA"]
    story_point_field: str  # Custom field ID, e.g. "customfield_10016"
    epic_link_field: str = "customfield_10014"  # Legacy Epic Link field, varies by instance


@dataclass
class Config:
    github: GitHubConfig
    teams: dict[str, Team]
    confluence: Optional[ConfluenceConfig] = None
    jira: Optional[JiraConfig] = None

    @property
    def team_members(self) -> dict[str, TeamMember]:
        """Flatten all teams into a single dict of members for backward compatibility."""
        members = {}
        for team in self.teams.values():
            members.update(team.members)
        return members


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


@dataclass
class JiraIssue:
    key: str
    summary: str
    issue_type: str
    status: str
    status_category: str  # "To Do", "In Progress", "Done"
    assignee_account_id: Optional[str]
    assignee_name: Optional[str]
    story_points: Optional[float]
    due_date: Optional[datetime]
    parent_key: Optional[str]
    epic_link: Optional[str]  # Legacy Epic Link field for older Jira setups
    labels: list[str]
    url: str
    created: Optional[datetime]
    updated: Optional[datetime]


@dataclass
class EpicProgress:
    epic: JiraIssue
    total_story_points: float
    completed_story_points: float
    total_issues: int
    completed_issues: int
    in_progress_issues: int
    assignees: list[dict]  # [{"account_id": ..., "name": ..., "story_points": ...}]


@dataclass
class TeamMemberAllocation:
    account_id: str
    name: str
    github_username: str
    total_open_story_points: float
    total_open_issues: int
    allocation_by_epic: list[dict]  # [{"epic_key": ..., "summary": ..., "points": ..., "issue_count": ...}]
    allocation_by_initiative: list[dict]  # [{"initiative_key": ..., "summary": ..., "points": ...}]


@dataclass
class ReviewTurnaround:
    """Metrics for how quickly an engineer responds to review requests."""
    pr_number: int
    pr_title: str
    repo: str
    pr_url: str
    requested_at: Optional[datetime]
    reviewed_at: Optional[datetime]
    turnaround_hours: Optional[float]


@dataclass
class PeriodContribution:
    """Contribution counts for a specific time period."""
    period_label: str  # e.g., "2025-W03", "2025-01", "2025-Q1"
    start_date: datetime
    end_date: datetime
    prs_merged: int
    reviews_given: int
    lines_added: int
    lines_removed: int
    docs_created: int
    docs_updated: int


@dataclass
class ContributionTrend:
    """Trend analysis comparing multiple periods."""
    periods: list[PeriodContribution]
    pr_trend_pct: Optional[float]  # % change from first to last period
    review_trend_pct: Optional[float]
    lines_trend_pct: Optional[float]


@dataclass
class ContributionDistribution:
    """Categorization of contributions by repository and inferred area."""
    by_repo: dict[str, int]  # repo_name -> pr_count
    by_area: dict[str, int]  # area (frontend/backend/infra/etc) -> pr_count
    by_file_type: dict[str, int]  # file extension -> file_count
    files_touched: list[dict]  # [{"path": str, "repo": str, "area": str}]
