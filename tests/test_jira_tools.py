"""Unit tests for Jira tools."""

import pytest
import responses

from ic_tracker.tools.jira_tools import (
    handle_get_initiative_roadmap,
    handle_get_team_bandwidth,
    handle_search_jira_issues,
    _calculate_epic_progress,
    _calculate_allocation,
    _issue_to_dict,
)
from ic_tracker.models import JiraIssue, Config, Team
from datetime import datetime, timezone


@pytest.fixture
def mock_jira_issue():
    return JiraIssue(
        key="PROJ-123",
        summary="Test Story",
        issue_type="Story",
        status="In Progress",
        status_category="In Progress",
        assignee_account_id="account-123",
        assignee_name="Test User",
        story_points=5.0,
        due_date=datetime(2025, 6, 1, tzinfo=timezone.utc),
        parent_key="PROJ-100",
        epic_link=None,
        labels=["backend"],
        url="https://test.atlassian.net/browse/PROJ-123",
        created=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updated=datetime(2025, 1, 15, tzinfo=timezone.utc),
    )


@pytest.fixture
def mock_epic():
    return JiraIssue(
        key="PROJ-100",
        summary="Test Epic",
        issue_type="Epic",
        status="In Progress",
        status_category="In Progress",
        assignee_account_id="account-123",
        assignee_name="Test User",
        story_points=None,
        due_date=datetime(2025, 12, 31, tzinfo=timezone.utc),
        parent_key="PROJ-50",
        epic_link=None,
        labels=["q1-goal"],
        url="https://test.atlassian.net/browse/PROJ-100",
        created=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updated=datetime(2025, 1, 20, tzinfo=timezone.utc),
    )


class TestHelperFunctions:
    """Test helper functions."""

    def test_issue_to_dict(self, mock_jira_issue):
        result = _issue_to_dict(mock_jira_issue)

        assert result["key"] == "PROJ-123"
        assert result["summary"] == "Test Story"
        assert result["issue_type"] == "Story"
        assert result["status"] == "In Progress"
        assert result["story_points"] == 5.0
        assert result["assignee"] == "Test User"
        assert result["due_date"] == "2025-06-01T00:00:00+00:00"

    def test_issue_to_dict_no_due_date(self, mock_jira_issue):
        mock_jira_issue.due_date = None
        result = _issue_to_dict(mock_jira_issue)

        assert result["due_date"] is None

    def test_calculate_epic_progress_basic(self, mock_epic):
        children = [
            JiraIssue(
                key=f"PROJ-{i}",
                summary=f"Story {i}",
                issue_type="Story",
                status="Done" if i < 2 else "In Progress",
                status_category="Done" if i < 2 else "In Progress",
                assignee_account_id="account-123",
                assignee_name="Test User",
                story_points=3.0,
                due_date=None,
                parent_key="PROJ-100",
                epic_link=None,
                labels=[],
                url=f"https://test.atlassian.net/browse/PROJ-{i}",
                created=datetime.now(timezone.utc),
                updated=datetime.now(timezone.utc),
            )
            for i in range(5)
        ]

        result = _calculate_epic_progress(mock_epic, children)

        assert result["total_story_points"] == 15.0  # 5 * 3
        assert result["completed_story_points"] == 6.0  # 2 * 3 (Done)
        assert result["progress_percentage"] == 40.0
        assert result["total_issues"] == 5
        assert result["completed_issues"] == 2
        assert result["in_progress_issues"] == 3

    def test_calculate_epic_progress_no_story_points(self, mock_epic):
        children = [
            JiraIssue(
                key="PROJ-1",
                summary="Story 1",
                issue_type="Story",
                status="Done",
                status_category="Done",
                assignee_account_id="account-123",
                assignee_name="Test User",
                story_points=None,  # No points
                due_date=None,
                parent_key="PROJ-100",
                epic_link=None,
                labels=[],
                url="https://test.atlassian.net/browse/PROJ-1",
                created=datetime.now(timezone.utc),
                updated=datetime.now(timezone.utc),
            )
        ]

        result = _calculate_epic_progress(mock_epic, children)

        assert result["total_story_points"] == 0
        assert result["progress_percentage"] == 0
        assert result["total_issues"] == 1
        assert result["completed_issues"] == 1

    def test_calculate_epic_progress_assignee_aggregation(self, mock_epic):
        children = [
            JiraIssue(
                key="PROJ-1",
                summary="Story 1",
                issue_type="Story",
                status="In Progress",
                status_category="In Progress",
                assignee_account_id="account-123",
                assignee_name="User A",
                story_points=3.0,
                due_date=None,
                parent_key="PROJ-100",
                epic_link=None,
                labels=[],
                url="https://test.atlassian.net/browse/PROJ-1",
                created=datetime.now(timezone.utc),
                updated=datetime.now(timezone.utc),
            ),
            JiraIssue(
                key="PROJ-2",
                summary="Story 2",
                issue_type="Story",
                status="To Do",
                status_category="To Do",
                assignee_account_id="account-123",
                assignee_name="User A",
                story_points=5.0,
                due_date=None,
                parent_key="PROJ-100",
                epic_link=None,
                labels=[],
                url="https://test.atlassian.net/browse/PROJ-2",
                created=datetime.now(timezone.utc),
                updated=datetime.now(timezone.utc),
            ),
            JiraIssue(
                key="PROJ-3",
                summary="Story 3",
                issue_type="Story",
                status="In Progress",
                status_category="In Progress",
                assignee_account_id="account-456",
                assignee_name="User B",
                story_points=2.0,
                due_date=None,
                parent_key="PROJ-100",
                epic_link=None,
                labels=[],
                url="https://test.atlassian.net/browse/PROJ-3",
                created=datetime.now(timezone.utc),
                updated=datetime.now(timezone.utc),
            ),
        ]

        result = _calculate_epic_progress(mock_epic, children)

        assert len(result["assignees"]) == 2
        # User A has 8 points (3+5)
        user_a = next(a for a in result["assignees"] if a["account_id"] == "account-123")
        assert user_a["story_points"] == 8.0
        assert user_a["issue_count"] == 2
        # User B has 2 points
        user_b = next(a for a in result["assignees"] if a["account_id"] == "account-456")
        assert user_b["story_points"] == 2.0
        assert user_b["issue_count"] == 1

    def test_calculate_allocation(self):
        issues = [
            JiraIssue(
                key="PROJ-1",
                summary="Story 1",
                issue_type="Story",
                status="In Progress",
                status_category="In Progress",
                assignee_account_id="account-123",
                assignee_name="Test User",
                story_points=3.0,
                due_date=None,
                parent_key="PROJ-100",
                epic_link=None,
                labels=[],
                url="https://test.atlassian.net/browse/PROJ-1",
                created=datetime.now(timezone.utc),
                updated=datetime.now(timezone.utc),
            ),
            JiraIssue(
                key="PROJ-2",
                summary="Story 2",
                issue_type="Story",
                status="To Do",
                status_category="To Do",
                assignee_account_id="account-123",
                assignee_name="Test User",
                story_points=5.0,
                due_date=None,
                parent_key="PROJ-100",
                epic_link=None,
                labels=[],
                url="https://test.atlassian.net/browse/PROJ-2",
                created=datetime.now(timezone.utc),
                updated=datetime.now(timezone.utc),
            ),
            JiraIssue(
                key="PROJ-3",
                summary="Story 3",
                issue_type="Story",
                status="In Progress",
                status_category="In Progress",
                assignee_account_id="account-123",
                assignee_name="Test User",
                story_points=2.0,
                due_date=None,
                parent_key="PROJ-200",  # Different epic
                epic_link=None,
                labels=[],
                url="https://test.atlassian.net/browse/PROJ-3",
                created=datetime.now(timezone.utc),
                updated=datetime.now(timezone.utc),
            ),
        ]

        result = _calculate_allocation(issues, "testuser", "Test User", "account-123")

        assert result["github_username"] == "testuser"
        assert result["total_open_story_points"] == 10.0
        assert result["total_open_issues"] == 3
        assert len(result["allocation_by_epic"]) == 2
        # PROJ-100 epic has 8 points (3+5)
        epic_100 = next(e for e in result["allocation_by_epic"] if e["epic_key"] == "PROJ-100")
        assert epic_100["story_points"] == 8.0
        assert epic_100["issue_count"] == 2


class TestToolHandlers:
    """Test tool handlers with mocked API."""

    @pytest.mark.asyncio
    @responses.activate
    async def test_handle_get_initiative_roadmap(self, config, sample_initiative, sample_epic, sample_jira_issue):
        # Mock get initiative
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/issue/PROJ-50",
            json=sample_initiative,
            status=200,
        )
        # Mock get epics
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/search/jql",
            json={"issues": [sample_epic], "isLast": True},
            status=200,
        )
        # Mock get epic children
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/search/jql",
            json={"issues": [sample_jira_issue], "isLast": True},
            status=200,
        )

        result = await handle_get_initiative_roadmap(config, "PROJ-50")

        assert "error" not in result
        assert result["initiative"]["key"] == "PROJ-50"
        assert len(result["epics"]) == 1
        assert result["epics"][0]["epic"]["key"] == "PROJ-100"
        assert result["summary"]["total_epics"] == 1

    @pytest.mark.asyncio
    async def test_handle_get_initiative_roadmap_no_jira_config(self, team_members):
        config = Config(
            github=None,
            teams={"default": Team(id="default", name="Default Team", members=team_members)},
            jira=None,  # No Jira configured
        )

        result = await handle_get_initiative_roadmap(config, "PROJ-50")

        assert "error" in result
        assert "not configured" in result["error"]

    @pytest.mark.asyncio
    @responses.activate
    async def test_handle_get_initiative_roadmap_children_fetch_warning(self, config, sample_initiative, sample_epic):
        """Test that warning is included when batch fetch of children fails."""
        # Mock get initiative
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/issue/PROJ-50",
            json=sample_initiative,
            status=200,
        )
        # Mock get epics
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/search/jql",
            json={"issues": [sample_epic], "isLast": True},
            status=200,
        )
        # Mock get epic children - fails with server error
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/search/jql",
            status=500,
        )

        result = await handle_get_initiative_roadmap(config, "PROJ-50")

        assert "error" not in result
        assert "warning" in result
        assert "incomplete" in result["warning"]
        # Should still return data, just with empty children
        assert result["summary"]["total_issues"] == 0

    @pytest.mark.asyncio
    @responses.activate
    async def test_handle_get_team_bandwidth(self, config, sample_jira_issue):
        # Mock get user open issues for testuser
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/search/jql",
            json={"issues": [sample_jira_issue], "isLast": True},
            status=200,
        )
        # Mock get user open issues for otheruser
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/search/jql",
            json={"issues": [], "isLast": True},
            status=200,
        )

        result = await handle_get_team_bandwidth(config)

        assert "error" not in result
        assert result["summary"]["total_members"] == 2
        assert result["summary"]["total_open_story_points"] == 5.0
        assert result["summary"]["total_open_issues"] == 1

    @pytest.mark.asyncio
    @responses.activate
    async def test_handle_get_team_bandwidth_single_user(self, config, sample_jira_issue):
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/search/jql",
            json={"issues": [sample_jira_issue], "isLast": True},
            status=200,
        )

        result = await handle_get_team_bandwidth(config, github_username="testuser")

        assert "error" not in result
        assert result["summary"]["total_members"] == 1
        assert result["team_members"][0]["github_username"] == "testuser"

    @pytest.mark.asyncio
    async def test_handle_get_team_bandwidth_unknown_user(self, config):
        result = await handle_get_team_bandwidth(config, github_username="unknownuser")

        assert "error" in result
        assert "Unknown team member" in result["error"]

    @pytest.mark.asyncio
    @responses.activate
    async def test_handle_search_jira_issues(self, config, sample_jira_issue):
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/search/jql",
            json={"issues": [sample_jira_issue], "isLast": True},
            status=200,
        )

        result = await handle_search_jira_issues(config, "project = PROJ")

        assert "error" not in result
        assert result["jql"] == "project = PROJ"
        assert result["total_results"] == 1
        assert result["issues"][0]["key"] == "PROJ-123"

    @pytest.mark.asyncio
    @responses.activate
    async def test_handle_search_jira_issues_respects_max_results(self, config, sample_jira_issue):
        # Return 50 issues
        issues = [{**sample_jira_issue, "key": f"PROJ-{i}"} for i in range(50)]
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/search/jql",
            json={"issues": issues, "isLast": False, "nextPageToken": "token123"},
            status=200,
        )

        result = await handle_search_jira_issues(config, "project = PROJ", max_results=10)

        assert result["total_results"] == 10

    @pytest.mark.asyncio
    async def test_handle_search_jira_issues_no_jira_config(self, team_members):
        config = Config(
            github=None,
            teams={"default": Team(id="default", name="Default Team", members=team_members)},
            jira=None,
        )

        result = await handle_search_jira_issues(config, "project = PROJ")

        assert "error" in result
        assert "not configured" in result["error"]
