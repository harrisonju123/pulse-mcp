"""Unit tests for team-related tools."""

import pytest

from work_tracker.tools.github_tools import handle_get_teams, handle_get_team_members
from work_tracker.models import Config, GitHubConfig, Team, TeamMember


@pytest.fixture
def multi_team_config():
    """Config with multiple teams."""
    return Config(
        github=GitHubConfig(token="gh-token", org="testorg", repos=["repo1"]),
        teams={
            "platform": Team(
                id="platform",
                name="Platform Team",
                members={
                    "alice": TeamMember(
                        github_username="alice",
                        atlassian_account_id="acc-1",
                        name="Alice Smith",
                    ),
                    "bob": TeamMember(
                        github_username="bob",
                        atlassian_account_id="acc-2",
                        name="Bob Jones",
                    ),
                },
            ),
            "product": Team(
                id="product",
                name="Product Team",
                members={
                    "carol": TeamMember(
                        github_username="carol",
                        atlassian_account_id="acc-3",
                        name="Carol Williams",
                    ),
                },
            ),
        },
    )


@pytest.fixture
def single_team_config():
    """Config with single default team (legacy format converted)."""
    return Config(
        github=GitHubConfig(token="gh-token", org="testorg", repos=["repo1"]),
        teams={
            "default": Team(
                id="default",
                name="Default Team",
                members={
                    "user1": TeamMember(
                        github_username="user1",
                        atlassian_account_id="acc-1",
                        name="User One",
                    ),
                    "user2": TeamMember(
                        github_username="user2",
                        atlassian_account_id="acc-2",
                        name="User Two",
                    ),
                },
            ),
        },
    )


class TestGetTeams:
    """Test get_teams tool handler."""

    @pytest.mark.asyncio
    async def test_get_teams_multi_team(self, multi_team_config):
        result = await handle_get_teams(multi_team_config)

        assert "error" not in result
        assert result["total_teams"] == 2
        assert result["total_members"] == 3

        teams = {t["id"]: t for t in result["teams"]}
        assert "platform" in teams
        assert "product" in teams
        assert teams["platform"]["name"] == "Platform Team"
        assert teams["platform"]["member_count"] == 2
        assert teams["product"]["name"] == "Product Team"
        assert teams["product"]["member_count"] == 1

    @pytest.mark.asyncio
    async def test_get_teams_single_team(self, single_team_config):
        result = await handle_get_teams(single_team_config)

        assert "error" not in result
        assert result["total_teams"] == 1
        assert result["total_members"] == 2

        team = result["teams"][0]
        assert team["id"] == "default"
        assert team["name"] == "Default Team"
        assert team["member_count"] == 2

    @pytest.mark.asyncio
    async def test_get_teams_includes_members(self, multi_team_config):
        result = await handle_get_teams(multi_team_config)

        platform_team = next(t for t in result["teams"] if t["id"] == "platform")
        members = platform_team["members"]

        assert len(members) == 2
        member_usernames = {m["github_username"] for m in members}
        assert member_usernames == {"alice", "bob"}


class TestGetTeamMembers:
    """Test get_team_members tool handler."""

    @pytest.mark.asyncio
    async def test_get_all_members_multi_team(self, multi_team_config):
        result = await handle_get_team_members(multi_team_config)

        assert "error" not in result
        assert result["count"] == 3

        usernames = {m["github_username"] for m in result["team_members"]}
        assert usernames == {"alice", "bob", "carol"}

        # Check that team info is included
        for member in result["team_members"]:
            assert "team" in member

    @pytest.mark.asyncio
    async def test_get_members_filtered_by_team(self, multi_team_config):
        result = await handle_get_team_members(multi_team_config, team="platform")

        assert "error" not in result
        assert result["count"] == 2
        assert result["team"]["id"] == "platform"
        assert result["team"]["name"] == "Platform Team"

        usernames = {m["github_username"] for m in result["team_members"]}
        assert usernames == {"alice", "bob"}

    @pytest.mark.asyncio
    async def test_get_members_unknown_team(self, multi_team_config):
        result = await handle_get_team_members(multi_team_config, team="nonexistent")

        assert "error" in result
        assert "Unknown team" in result["error"]
        assert "platform" in result["error"]  # Available teams listed

    @pytest.mark.asyncio
    async def test_get_all_members_single_team(self, single_team_config):
        result = await handle_get_team_members(single_team_config)

        assert "error" not in result
        assert result["count"] == 2

        usernames = {m["github_username"] for m in result["team_members"]}
        assert usernames == {"user1", "user2"}

    @pytest.mark.asyncio
    async def test_member_includes_team_association(self, multi_team_config):
        result = await handle_get_team_members(multi_team_config)

        alice = next(m for m in result["team_members"] if m["github_username"] == "alice")
        assert alice["team"] == "platform"

        carol = next(m for m in result["team_members"] if m["github_username"] == "carol")
        assert carol["team"] == "product"
