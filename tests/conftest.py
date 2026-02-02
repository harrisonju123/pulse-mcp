"""Shared test fixtures."""

import pytest

from work_tracker.models import Config, GitHubConfig, JiraConfig, Team, TeamMember


@pytest.fixture
def jira_config():
    return JiraConfig(
        base_url="https://test.atlassian.net",
        email="test@example.com",
        api_token="test-token",
        project_keys=["PROJ", "INFRA"],
        story_point_field="customfield_10016",
        epic_link_field="customfield_10014",
    )


@pytest.fixture
def team_members():
    """Legacy team_members fixture for backward compatibility in tests."""
    return {
        "testuser": TeamMember(
            github_username="testuser",
            atlassian_account_id="account-123",
            name="Test User",
        ),
        "otheruser": TeamMember(
            github_username="otheruser",
            atlassian_account_id="account-456",
            name="Other User",
        ),
    }


@pytest.fixture
def teams(team_members):
    """Teams fixture using the new multi-team format."""
    return {
        "default": Team(
            id="default",
            name="Default Team",
            members=team_members,
        )
    }


@pytest.fixture
def config(jira_config, teams):
    return Config(
        github=GitHubConfig(token="gh-token", org="testorg", repos=["repo1"]),
        teams=teams,
        jira=jira_config,
    )


@pytest.fixture
def sample_jira_issue():
    """Sample Jira API response for a single issue."""
    return {
        "key": "PROJ-123",
        "fields": {
            "summary": "Test Issue",
            "issuetype": {"name": "Story"},
            "status": {"name": "In Progress", "statusCategory": {"name": "In Progress"}},
            "assignee": {"accountId": "account-123", "displayName": "Test User"},
            "duedate": "2025-06-01",
            "parent": {"key": "PROJ-100"},
            "labels": ["backend"],
            "created": "2025-01-01T10:00:00.000+0000",
            "updated": "2025-01-15T14:30:00.000+0000",
            "customfield_10016": 5.0,
            "customfield_10014": None,  # Epic Link (legacy)
        },
    }


@pytest.fixture
def sample_epic():
    """Sample Jira API response for an epic."""
    return {
        "key": "PROJ-100",
        "fields": {
            "summary": "Test Epic",
            "issuetype": {"name": "Epic"},
            "status": {"name": "In Progress", "statusCategory": {"name": "In Progress"}},
            "assignee": {"accountId": "account-123", "displayName": "Test User"},
            "duedate": "2025-12-31",
            "parent": {"key": "PROJ-50"},
            "labels": ["q1-goal"],
            "created": "2025-01-01T09:00:00.000+0000",
            "updated": "2025-01-20T10:00:00.000+0000",
            "customfield_10016": None,
            "customfield_10014": None,
        },
    }


@pytest.fixture
def sample_initiative():
    """Sample Jira API response for an initiative."""
    return {
        "key": "PROJ-50",
        "fields": {
            "summary": "Test Initiative",
            "issuetype": {"name": "Initiative"},
            "status": {"name": "In Progress", "statusCategory": {"name": "In Progress"}},
            "assignee": None,
            "duedate": "2025-12-31",
            "parent": None,
            "labels": ["roadmap"],
            "created": "2025-01-01T08:00:00.000+0000",
            "updated": "2025-01-20T10:00:00.000+0000",
            "customfield_10016": None,
            "customfield_10014": None,
        },
    }
