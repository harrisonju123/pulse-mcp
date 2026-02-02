"""Tests for goal tracking tools."""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock

from work_tracker.models import Config, GitHubConfig, Team, TeamMember
from work_tracker.tools.goal_tools import (
    handle_add_goal,
    handle_get_goals,
    handle_update_goal_progress,
    handle_get_goal_progress,
    _get_goals_file_path,
)


@pytest.fixture
def test_config():
    """Create a test config."""
    member = TeamMember(
        github_username="alice",
        atlassian_account_id="acc-1",
        name="Alice Smith",
    )
    team = Team(
        id="platform",
        name="Platform Team",
        members={"alice": member},
    )
    return Config(
        github=GitHubConfig(token="test-token", org="testorg", repos=[]),
        teams={"platform": team},
        self_username="alice",
    )


@pytest.fixture
def clean_goals_dir(tmp_path, monkeypatch):
    """Use a temporary directory for goal files."""
    goals_dir = tmp_path / "goals"
    goals_dir.mkdir()
    monkeypatch.setattr("work_tracker.tools.goal_tools.GOALS_DIR", str(goals_dir))
    return goals_dir


@pytest.mark.asyncio
class TestGoalCRUD:
    """Test goal CRUD operations."""

    async def test_add_goal_basic(self, test_config, clean_goals_dir):
        result = await handle_add_goal(
            test_config,
            title="Learn Rust",
            description="Become proficient in Rust programming",
            category="learning",
        )

        assert result["success"] is True
        assert result["goal"]["title"] == "Learn Rust"
        assert result["goal"]["id"] == "learn-rust"
        assert result["goal"]["category"] == "learning"

    async def test_add_goal_with_key_results(self, test_config, clean_goals_dir):
        result = await handle_add_goal(
            test_config,
            title="Ship Migration",
            key_results=[
                {"description": "Complete design doc", "target": "Week 1"},
                {"description": "Migrate 10 services", "target": "Q2"},
            ],
        )

        assert result["success"] is True
        assert result["goal"]["key_results_count"] == 2

    async def test_get_goals_empty(self, test_config, clean_goals_dir):
        result = await handle_get_goals(test_config)

        assert result["github_username"] == "alice"
        assert result["count"] == 0
        assert result["goals"] == []

    async def test_get_goals_after_add(self, test_config, clean_goals_dir):
        await handle_add_goal(test_config, title="Goal 1")
        await handle_add_goal(test_config, title="Goal 2", category="career")

        result = await handle_get_goals(test_config)

        assert result["count"] == 2
        assert len(result["goals"]) == 2
        assert result["goals"][0]["title"] == "Goal 1"
        assert result["goals"][1]["title"] == "Goal 2"

    async def test_update_goal_status(self, test_config, clean_goals_dir):
        add_result = await handle_add_goal(test_config, title="Complete Project")
        goal_id = add_result["goal"]["id"]

        update_result = await handle_update_goal_progress(
            test_config,
            goal_id=goal_id,
            status="completed",
        )

        assert update_result["success"] is True
        assert any("Status updated" in change and "completed" in change for change in update_result["changes"])

        # Verify the status was updated
        goals_result = await handle_get_goals(test_config, status="completed")
        assert goals_result["count"] == 1

    async def test_add_progress_note(self, test_config, clean_goals_dir):
        add_result = await handle_add_goal(test_config, title="Write Blog Post")
        goal_id = add_result["goal"]["id"]

        update_result = await handle_update_goal_progress(
            test_config,
            goal_id=goal_id,
            progress_note="Completed first draft",
        )

        assert update_result["success"] is True
        assert "Progress note added" in update_result["changes"]

    async def test_update_key_result_progress(self, test_config, clean_goals_dir):
        add_result = await handle_add_goal(
            test_config,
            title="Launch Feature",
            key_results=[
                {"description": "Write tests", "target": "100% coverage"},
                {"description": "Deploy to prod", "target": "Week 2"},
            ],
        )
        goal_id = add_result["goal"]["id"]

        update_result = await handle_update_goal_progress(
            test_config,
            goal_id=goal_id,
            key_result_updates=[
                {"index": 0, "current": "85%", "status": "in_progress"},
            ],
        )

        assert update_result["success"] is True
        assert "Key result #0 updated" in update_result["changes"]

    async def test_get_goal_progress_single(self, test_config, clean_goals_dir):
        add_result = await handle_add_goal(
            test_config,
            title="Q1 Goals",
            key_results=[
                {"description": "Ship 5 PRs"},
                {"description": "Write 2 docs"},
            ],
        )
        goal_id = add_result["goal"]["id"]

        # Update one key result
        await handle_update_goal_progress(
            test_config,
            goal_id=goal_id,
            key_result_updates=[
                {"index": 0, "status": "completed"},
            ],
        )

        progress = await handle_get_goal_progress(
            test_config,
            goal_id=goal_id,
        )

        assert len(progress["goals"]) == 1
        assert progress["goals"][0]["key_results_progress"] == "1/2"

    async def test_get_goal_progress_all_active(self, test_config, clean_goals_dir):
        await handle_add_goal(test_config, title="Goal 1")
        await handle_add_goal(test_config, title="Goal 2")
        add_result = await handle_add_goal(test_config, title="Goal 3")

        # Archive one goal
        await handle_update_goal_progress(
            test_config,
            goal_id=add_result["goal"]["id"],
            status="archived",
        )

        progress = await handle_get_goal_progress(test_config)

        assert len(progress["goals"]) == 2  # Only active goals
        assert progress["summary"]["active_goals"] == 2


@pytest.mark.asyncio
class TestSelfResolution:
    """Test self username resolution."""

    async def test_uses_self_when_no_username(self, test_config, clean_goals_dir):
        result = await handle_add_goal(
            test_config,
            title="My Goal",
        )

        assert result["github_username"] == "alice"

    async def test_explicit_username_overrides_self(self, test_config, clean_goals_dir):
        # Add another member to config
        bob = TeamMember(
            github_username="bob",
            atlassian_account_id="acc-2",
            name="Bob Jones",
        )
        test_config.teams["platform"].members["bob"] = bob

        result = await handle_add_goal(
            test_config,
            title="Bob's Goal",
            github_username="bob",
        )

        assert result["github_username"] == "bob"

    async def test_error_when_no_self_and_no_username(self, test_config, clean_goals_dir):
        test_config.self_username = None

        result = await handle_get_goals(test_config)

        assert "error" in result
        assert "self' not configured" in result["error"]

    async def test_error_for_unknown_username(self, test_config, clean_goals_dir):
        result = await handle_get_goals(
            test_config,
            github_username="unknown",
        )

        assert "error" in result
        assert "Unknown user" in result["error"]


@pytest.mark.asyncio
class TestGoalFilters:
    """Test goal filtering and status."""

    async def test_filter_by_status_active(self, test_config, clean_goals_dir):
        await handle_add_goal(test_config, title="Active Goal 1")
        add_result = await handle_add_goal(test_config, title="To Complete")
        await handle_update_goal_progress(
            test_config,
            goal_id=add_result["goal"]["id"],
            status="completed",
        )

        result = await handle_get_goals(test_config, status="active")

        assert result["count"] == 1
        assert result["goals"][0]["title"] == "Active Goal 1"

    async def test_filter_by_status_completed(self, test_config, clean_goals_dir):
        await handle_add_goal(test_config, title="Active Goal")
        add_result = await handle_add_goal(test_config, title="Completed Goal")
        await handle_update_goal_progress(
            test_config,
            goal_id=add_result["goal"]["id"],
            status="completed",
        )

        result = await handle_get_goals(test_config, status="completed")

        assert result["count"] == 1
        assert result["goals"][0]["title"] == "Completed Goal"

    async def test_filter_all_status(self, test_config, clean_goals_dir):
        await handle_add_goal(test_config, title="Goal 1")
        await handle_add_goal(test_config, title="Goal 2")

        result = await handle_get_goals(test_config, status="all")

        assert result["count"] == 2


@pytest.mark.asyncio
class TestUniqueGoalIds:
    """Test goal ID uniqueness."""

    async def test_duplicate_titles_get_unique_ids(self, test_config, clean_goals_dir):
        result1 = await handle_add_goal(test_config, title="Learn Python")
        result2 = await handle_add_goal(test_config, title="Learn Python")

        assert result1["goal"]["id"] == "learn-python"
        assert result2["goal"]["id"] == "learn-python-1"

    async def test_goal_id_slugification(self, test_config, clean_goals_dir):
        result = await handle_add_goal(
            test_config,
            title="Ship Feature #123 (High Priority!)",
        )

        assert result["goal"]["id"] == "ship-feature-123-high-priority"
