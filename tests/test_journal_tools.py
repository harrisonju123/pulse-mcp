"""Tests for journal/reflection tools."""

import pytest
from datetime import datetime, timedelta
from pathlib import Path

from work_tracker.models import Config, GitHubConfig, Team, TeamMember
from work_tracker.tools.journal_tools import (
    handle_add_journal_entry,
    handle_get_journal_entries,
    handle_search_journal,
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
def clean_journal_dir(tmp_path, monkeypatch):
    """Use a temporary directory for journal files."""
    journal_dir = tmp_path / "reflections"
    journal_dir.mkdir()
    monkeypatch.setattr("work_tracker.tools.journal_tools.JOURNAL_DIR", str(journal_dir))
    return journal_dir


@pytest.mark.asyncio
class TestJournalBasics:
    """Test basic journal operations."""

    async def test_add_entry_basic(self, test_config, clean_journal_dir):
        result = await handle_add_journal_entry(
            test_config,
            content="Today was a great day! Shipped the migration feature.",
        )

        assert result["success"] is True
        assert result["github_username"] == "alice"
        assert "date" in result
        assert "time" in result

    async def test_add_entry_with_title(self, test_config, clean_journal_dir):
        result = await handle_add_journal_entry(
            test_config,
            content="Completed the design doc and got approval from the team.",
            title="Weekly Wins",
        )

        assert result["success"] is True

    async def test_add_entry_with_tags(self, test_config, clean_journal_dir):
        result = await handle_add_journal_entry(
            test_config,
            content="Struggled with the API integration today.",
            tags=["blockers", "api"],
        )

        assert result["success"] is True

    async def test_get_entries_empty(self, test_config, clean_journal_dir):
        result = await handle_get_journal_entries(test_config)

        assert result["github_username"] == "alice"
        assert result["count"] == 0
        assert result["entries_by_date"] == []

    async def test_get_entries_after_add(self, test_config, clean_journal_dir):
        await handle_add_journal_entry(
            test_config,
            content="First entry",
        )
        await handle_add_journal_entry(
            test_config,
            content="Second entry",
            title="Daily Reflection",
        )

        result = await handle_get_journal_entries(test_config, days=1)

        assert result["count"] == 2
        assert len(result["entries_by_date"]) == 1
        assert len(result["entries_by_date"][0]["entries"]) == 2


@pytest.mark.asyncio
class TestJournalSearch:
    """Test journal search functionality."""

    async def test_search_no_matches(self, test_config, clean_journal_dir):
        await handle_add_journal_entry(
            test_config,
            content="Working on the migration project",
        )

        result = await handle_search_journal(
            test_config,
            query="authentication",
        )

        assert result["query"] == "authentication"
        assert result["count"] == 0

    async def test_search_content_match(self, test_config, clean_journal_dir):
        await handle_add_journal_entry(
            test_config,
            content="Finished implementing the authentication flow",
        )
        await handle_add_journal_entry(
            test_config,
            content="Working on database migrations",
        )

        result = await handle_search_journal(
            test_config,
            query="authentication",
        )

        assert result["count"] == 1
        assert "authentication" in result["matches"][0]["content_preview"].lower()

    async def test_search_title_match(self, test_config, clean_journal_dir):
        await handle_add_journal_entry(
            test_config,
            content="Details about the feature",
            title="Auth Feature Complete",
        )

        result = await handle_search_journal(
            test_config,
            query="auth",
        )

        assert result["count"] == 1
        assert result["matches"][0]["title"] == "Auth Feature Complete"

    async def test_search_case_insensitive(self, test_config, clean_journal_dir):
        await handle_add_journal_entry(
            test_config,
            content="Working on the MIGRATION project",
        )

        result = await handle_search_journal(
            test_config,
            query="migration",
        )

        assert result["count"] == 1


@pytest.mark.asyncio
class TestJournalTagFiltering:
    """Test filtering by tags."""

    async def test_filter_by_single_tag(self, test_config, clean_journal_dir):
        await handle_add_journal_entry(
            test_config,
            content="Great progress today #wins #productivity",
        )
        await handle_add_journal_entry(
            test_config,
            content="Ran into some issues #blockers",
        )

        result = await handle_get_journal_entries(
            test_config,
            days=1,
            tags=["wins"],
        )

        assert result["count"] == 1

    async def test_filter_by_multiple_tags_any_match(self, test_config, clean_journal_dir):
        await handle_add_journal_entry(
            test_config,
            content="Good progress #wins",
        )
        await handle_add_journal_entry(
            test_config,
            content="Learning new things #learning",
        )
        await handle_add_journal_entry(
            test_config,
            content="Blocked on reviews #blockers",
        )

        result = await handle_get_journal_entries(
            test_config,
            days=1,
            tags=["wins", "learning"],
        )

        assert result["count"] == 2


@pytest.mark.asyncio
class TestSelfResolution:
    """Test self username resolution."""

    async def test_uses_self_when_no_username(self, test_config, clean_journal_dir):
        result = await handle_add_journal_entry(
            test_config,
            content="My reflection",
        )

        assert result["github_username"] == "alice"

    async def test_explicit_username_overrides_self(self, test_config, clean_journal_dir):
        # Add another member
        bob = TeamMember(
            github_username="bob",
            atlassian_account_id="acc-2",
            name="Bob Jones",
        )
        test_config.teams["platform"].members["bob"] = bob

        result = await handle_add_journal_entry(
            test_config,
            content="Bob's reflection",
            github_username="bob",
        )

        assert result["github_username"] == "bob"

    async def test_error_when_no_self_and_no_username(self, test_config, clean_journal_dir):
        test_config.self_username = None

        result = await handle_add_journal_entry(
            test_config,
            content="Entry",
        )

        assert "error" in result
        assert "self' not configured" in result["error"]


@pytest.mark.asyncio
class TestDateRangeQueries:
    """Test date range querying."""

    async def test_custom_date_range(self, test_config, clean_journal_dir):
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)

        # We can't easily control the date in entries, but we can test the parameters
        result = await handle_get_journal_entries(
            test_config,
            start_date=yesterday.isoformat(),
            end_date=today.isoformat(),
        )

        assert result["start_date"] == yesterday.isoformat()
        assert result["end_date"] == today.isoformat()

    async def test_days_parameter(self, test_config, clean_journal_dir):
        result = await handle_get_journal_entries(
            test_config,
            days=7,
        )

        # Check that date range is approximately 7 days
        start = datetime.fromisoformat(result["start_date"])
        end = datetime.fromisoformat(result["end_date"])
        delta = (end - start).days

        assert 6 <= delta <= 7  # Allow for timezone differences


@pytest.mark.asyncio
class TestMultipleEntriesPerDay:
    """Test handling multiple entries on same day."""

    async def test_multiple_entries_same_day(self, test_config, clean_journal_dir):
        await handle_add_journal_entry(
            test_config,
            content="Morning reflection",
            title="Morning",
        )
        await handle_add_journal_entry(
            test_config,
            content="Afternoon update",
            title="Afternoon",
        )
        await handle_add_journal_entry(
            test_config,
            content="End of day thoughts",
            title="Evening",
        )

        result = await handle_get_journal_entries(test_config, days=1)

        assert result["count"] == 3
        # All should be on same date
        assert len(result["entries_by_date"]) == 1
        assert len(result["entries_by_date"][0]["entries"]) == 3
