"""Unit tests for pulse tools."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from work_tracker.models import CodeReview, Config, GitHubConfig, PullRequest, Team, TeamMember
from work_tracker.tools.pulse_tools import (
    _get_team_for_member,
    _validate_team_member,
    get_pulse_tools,
    handle_get_member_pulse,
    handle_get_pr_details,
)


@pytest.fixture
def team_members():
    return {
        "testuser": TeamMember(
            github_username="testuser",
            atlassian_account_id="account-123",
            name="Test User",
        ),
        "reviewer1": TeamMember(
            github_username="reviewer1",
            atlassian_account_id="account-456",
            name="Reviewer One",
        ),
    }


@pytest.fixture
def teams(team_members):
    return {
        "test-team": Team(
            id="test-team",
            name="Test Team",
            members=team_members,
        )
    }


@pytest.fixture
def config(teams):
    return Config(
        github=GitHubConfig(token="gh-token", org="testorg", repos=["repo1"]),
        teams=teams,
    )


@pytest.fixture
def sample_prs():
    """Sample merged PRs."""
    return [
        PullRequest(
            number=100,
            title="Add user migration workflow",
            repo="main-repo",
            state="closed",
            merged=True,
            url="https://github.com/testorg/main-repo/pull/100",
            created_at=datetime(2025, 1, 10, 10, 0, tzinfo=timezone.utc),
            merged_at=datetime(2025, 1, 12, 14, 0, tzinfo=timezone.utc),
        ),
        PullRequest(
            number=105,
            title="Fix migration edge case",
            repo="main-repo",
            state="closed",
            merged=True,
            url="https://github.com/testorg/main-repo/pull/105",
            created_at=datetime(2025, 1, 15, 10, 0, tzinfo=timezone.utc),
            merged_at=datetime(2025, 1, 16, 14, 0, tzinfo=timezone.utc),
        ),
    ]


@pytest.fixture
def sample_reviews():
    """Sample reviews given."""
    return [
        CodeReview(
            pr_number=200,
            pr_title="Add new feature",
            repo="main-repo",
            state="APPROVED",
            url="https://github.com/testorg/main-repo/pull/200",
            submitted_at=datetime(2025, 1, 14, 10, 0, tzinfo=timezone.utc),
        ),
    ]


@pytest.fixture
def sample_open_prs():
    """Sample open PRs."""
    return [
        PullRequest(
            number=110,
            title="WIP: Add validation",
            repo="main-repo",
            state="open",
            merged=False,
            url="https://github.com/testorg/main-repo/pull/110",
            created_at=datetime(2025, 1, 20, 10, 0, tzinfo=timezone.utc),
        ),
    ]


class TestPulseToolDefinition:
    """Test tool definition."""

    def test_get_pulse_tools_returns_tools(self):
        tools = get_pulse_tools()
        assert len(tools) == 2
        tool_names = [t.name for t in tools]
        assert "get_member_pulse" in tool_names
        assert "get_pr_details" in tool_names

    def test_member_pulse_tool_has_correct_schema(self):
        tools = get_pulse_tools()
        tool = next(t for t in tools if t.name == "get_member_pulse")

        assert tool.inputSchema["type"] == "object"
        assert "github_username" in tool.inputSchema["properties"]
        assert "days" in tool.inputSchema["properties"]
        assert tool.inputSchema["required"] == ["github_username"]

    def test_pr_details_tool_has_correct_schema(self):
        tools = get_pulse_tools()
        tool = next(t for t in tools if t.name == "get_pr_details")

        assert tool.inputSchema["type"] == "object"
        assert "repo" in tool.inputSchema["properties"]
        assert "pr_number" in tool.inputSchema["properties"]
        assert "include_diff" in tool.inputSchema["properties"]
        assert tool.inputSchema["required"] == ["repo", "pr_number"]


class TestValidation:
    """Test validation helpers."""

    def test_validate_team_member_valid(self, config):
        result = _validate_team_member(config, "testuser")
        assert result is None

    def test_validate_team_member_invalid(self, config):
        result = _validate_team_member(config, "nonexistent")
        assert result is not None
        assert "error" in result
        assert "Unknown team member" in result["error"]

    def test_get_team_for_member(self, config):
        result = _get_team_for_member(config, "testuser")
        assert result == "test-team"

    def test_get_team_for_member_not_found(self, config):
        result = _get_team_for_member(config, "nonexistent")
        assert result is None


class TestHandleGetMemberPulse:
    """Test the main handler."""

    @pytest.mark.asyncio
    async def test_invalid_username_returns_error(self, config):
        result = await handle_get_member_pulse(config, "nonexistent")

        assert "error" in result
        assert "Unknown team member" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_days_returns_error(self, config):
        result = await handle_get_member_pulse(config, "testuser", days=0)
        assert "error" in result
        assert "days must be between 1 and 365" in result["error"]

        result = await handle_get_member_pulse(config, "testuser", days=400)
        assert "error" in result
        assert "days must be between 1 and 365" in result["error"]

    @pytest.mark.asyncio
    async def test_successful_pulse(self, config, sample_prs, sample_reviews, sample_open_prs):
        with patch("work_tracker.tools.pulse_tools.GitHubClient") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)

            # Mock search_prs to return sample PRs
            mock_client.search_prs.return_value = sample_prs

            # Mock get_reviewers_for_pr_batch
            mock_client.get_reviewers_for_pr_batch.return_value = {
                ("main-repo", 100): ["reviewer1", "reviewer2"],
                ("main-repo", 105): ["reviewer1"],
            }

            # Mock get_reviews_by_user
            mock_client.get_reviews_by_user.return_value = sample_reviews

            # Mock _request for fetching PR author info
            mock_client._request.return_value = {
                "user": {"login": "otheruser"},
            }

            # Mock search_open_prs
            mock_client.search_open_prs.return_value = sample_open_prs

            result = await handle_get_member_pulse(config, "testuser", days=14)

            assert "error" not in result
            assert result["github_username"] == "testuser"
            assert result["name"] == "Test User"
            assert result["team"] == "test-team"
            assert "period" in result
            assert "prs_merged" in result
            assert len(result["prs_merged"]) == 2
            assert "reviews_given" in result
            assert len(result["reviews_given"]) == 1
            assert "collaboration" in result
            assert "reviewed_by" in result["collaboration"]
            assert "reviewed_for" in result["collaboration"]
            assert "open_prs" in result
            assert len(result["open_prs"]) == 1
            assert "summary" in result
            assert result["summary"]["prs_count"] == 2
            assert result["summary"]["reviews_count"] == 1

    @pytest.mark.asyncio
    async def test_pr_includes_reviewers(self, config, sample_prs):
        with patch("work_tracker.tools.pulse_tools.GitHubClient") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)

            mock_client.search_prs.return_value = sample_prs
            mock_client.get_reviewers_for_pr_batch.return_value = {
                ("main-repo", 100): ["reviewer1", "reviewer2"],
                ("main-repo", 105): ["reviewer1"],
            }
            mock_client.get_reviews_by_user.return_value = []
            mock_client.search_open_prs.return_value = []

            result = await handle_get_member_pulse(config, "testuser", days=14)

            assert result["prs_merged"][0]["reviewers"] == ["reviewer1", "reviewer2"]
            assert result["prs_merged"][1]["reviewers"] == ["reviewer1"]

    @pytest.mark.asyncio
    async def test_collaboration_tracking(self, config, sample_prs):
        with patch("work_tracker.tools.pulse_tools.GitHubClient") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)

            mock_client.search_prs.return_value = sample_prs
            mock_client.get_reviewers_for_pr_batch.return_value = {
                ("main-repo", 100): ["reviewer1"],
                ("main-repo", 105): ["reviewer1"],
            }
            mock_client.get_reviews_by_user.return_value = []
            mock_client.search_open_prs.return_value = []

            result = await handle_get_member_pulse(config, "testuser", days=14)

            # reviewer1 reviewed 2 PRs
            assert result["collaboration"]["reviewed_by"]["reviewer1"] == 2

    @pytest.mark.asyncio
    async def test_open_prs_includes_days_open(self, config, sample_open_prs):
        with patch("work_tracker.tools.pulse_tools.GitHubClient") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)

            mock_client.search_prs.return_value = []
            mock_client.get_reviewers_for_pr_batch.return_value = {}
            mock_client.get_reviews_by_user.return_value = []
            mock_client.search_open_prs.return_value = sample_open_prs

            result = await handle_get_member_pulse(config, "testuser", days=14)

            assert len(result["open_prs"]) == 1
            assert "days_open" in result["open_prs"][0]
            assert result["open_prs"][0]["title"] == "WIP: Add validation"

    @pytest.mark.asyncio
    async def test_handles_api_error_gracefully(self, config):
        with patch("work_tracker.tools.pulse_tools.GitHubClient") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)

            mock_client.search_prs.side_effect = Exception("API error")

            result = await handle_get_member_pulse(config, "testuser", days=14)

            assert "error" in result
            assert "Failed to fetch GitHub PRs" in result["error"]

    @pytest.mark.asyncio
    async def test_handles_partial_failures_with_warnings(self, config, sample_prs):
        with patch("work_tracker.tools.pulse_tools.GitHubClient") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)

            mock_client.search_prs.return_value = sample_prs
            mock_client.get_reviewers_for_pr_batch.return_value = {}
            mock_client.get_reviews_by_user.side_effect = Exception("Review API error")
            mock_client.search_open_prs.side_effect = Exception("Open PR API error")

            result = await handle_get_member_pulse(config, "testuser", days=14)

            # Should still return results for successful calls
            assert "error" not in result
            assert len(result["prs_merged"]) == 2
            # But should have warnings for failed calls
            assert "warnings" in result
            assert len(result["warnings"]) == 2


class TestHandleGetPrDetails:
    """Test the PR details handler."""

    @pytest.fixture
    def sample_files(self):
        """Sample PR files response."""
        return [
            {
                "filename": "internal/service/handler.go",
                "additions": 50,
                "deletions": 10,
                "status": "modified",
            },
            {
                "filename": "internal/service/handler_test.go",
                "additions": 30,
                "deletions": 5,
                "status": "modified",
            },
            {
                "filename": "go.sum",
                "additions": 100,
                "deletions": 50,
                "status": "modified",
            },
            {
                "filename": "internal/mocks/mock_service.go",
                "additions": 20,
                "deletions": 0,
                "status": "added",
            },
        ]

    @pytest.mark.asyncio
    async def test_categorizes_files_correctly(self, config, sample_files):
        with patch("work_tracker.tools.pulse_tools.GitHubClient") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)

            mock_client.get_pr_files.return_value = sample_files

            result = await handle_get_pr_details(config, "test-repo", 123)

            assert "error" not in result
            assert result["summary"]["total_files"] == 4
            assert result["summary"]["feature_files"] == 1  # handler.go
            assert result["summary"]["test_files"] == 1  # handler_test.go
            assert result["summary"]["generated_files"] == 1  # mock_service.go
            assert result["summary"]["deps_files"] == 1  # go.sum

    @pytest.mark.asyncio
    async def test_calculates_feature_percentage(self, config, sample_files):
        with patch("work_tracker.tools.pulse_tools.GitHubClient") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)

            mock_client.get_pr_files.return_value = sample_files

            result = await handle_get_pr_details(config, "test-repo", 123)

            # Feature file has 50 adds + 10 dels = 60
            # Total is 200 adds + 65 dels = 265
            # Feature pct = 60/265 * 100 = 22.6%
            assert result["summary"]["feature_additions"] == 50
            assert result["summary"]["feature_deletions"] == 10
            assert result["summary"]["feature_pct"] == 22.6

    @pytest.mark.asyncio
    async def test_includes_diff_when_requested(self, config, sample_files):
        with patch("work_tracker.tools.pulse_tools.GitHubClient") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)

            mock_client.get_pr_files.return_value = sample_files
            mock_client.get_pr_diff.return_value = """diff --git a/internal/service/handler.go b/internal/service/handler.go
index abc123..def456 100644
--- a/internal/service/handler.go
+++ b/internal/service/handler.go
@@ -10,6 +10,7 @@
+// New code here
"""

            result = await handle_get_pr_details(config, "test-repo", 123, include_diff=True)

            assert len(result["feature_files"]) == 1
            assert "diff" in result["feature_files"][0]
            assert "New code here" in result["feature_files"][0]["diff"]

    @pytest.mark.asyncio
    async def test_handles_api_error(self, config):
        with patch("work_tracker.tools.pulse_tools.GitHubClient") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)

            mock_client.get_pr_files.side_effect = Exception("API error")

            result = await handle_get_pr_details(config, "test-repo", 123)

            assert "error" in result
            assert "Failed to fetch PR files" in result["error"]

    @pytest.mark.asyncio
    async def test_provides_analysis_hint(self, config, sample_files):
        with patch("work_tracker.tools.pulse_tools.GitHubClient") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)

            mock_client.get_pr_files.return_value = sample_files

            result = await handle_get_pr_details(config, "test-repo", 123)

            assert "analysis_hint" in result
            assert "1 feature files" in result["analysis_hint"]
