"""Unit tests for GitHubClient.search_merged_prs."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from work_tracker.clients.github_client import GitHubClient
from work_tracker.models import GitHubConfig


@pytest.fixture
def github_config():
    return GitHubConfig(token="gh-token", org="testorg", repos=["repo1"])


@pytest.fixture
def client(github_config):
    c = GitHubClient(github_config, cache_ttl=0)
    yield c
    c.close()


class TestSearchMergedPrs:
    """Verify search_merged_prs builds the correct GitHub search query."""

    def test_query_uses_merged_qualifier_with_range(self, client):
        """When both since and until are provided, use merged:start..end."""
        since = datetime(2025, 1, 1, tzinfo=timezone.utc)
        until = datetime(2025, 1, 14, tzinfo=timezone.utc)

        with patch.object(client, "_paginate_search", return_value=iter([])) as mock_search:
            client.search_merged_prs("testuser", since, until)

            mock_search.assert_called_once()
            query = mock_search.call_args[0][1]
            assert "is:merged" in query
            assert "merged:2025-01-01..2025-01-14" in query
            assert "author:testuser" in query
            assert "org:testorg" in query
            # Should NOT use created: qualifier
            assert "created:" not in query

    def test_query_uses_merged_gte_without_until(self, client):
        """When only since is provided, use merged:>=start."""
        since = datetime(2025, 3, 1, tzinfo=timezone.utc)

        with patch.object(client, "_paginate_search", return_value=iter([])) as mock_search:
            client.search_merged_prs("testuser", since)

            query = mock_search.call_args[0][1]
            assert "merged:>=2025-03-01" in query
            assert "is:merged" in query

    def test_search_prs_still_uses_created_qualifier(self, client):
        """Existing search_prs should be unchanged — still uses created:."""
        since = datetime(2025, 1, 1, tzinfo=timezone.utc)
        until = datetime(2025, 1, 14, tzinfo=timezone.utc)

        with patch.object(client, "_paginate_search", return_value=iter([])) as mock_search:
            client.search_prs("testuser", since, until)

            query = mock_search.call_args[0][1]
            assert "created:2025-01-01..2025-01-14" in query
            assert "is:merged" not in query

    def test_returns_parsed_prs(self, client):
        """Results from the search API are parsed into PullRequest objects."""
        since = datetime(2025, 1, 1, tzinfo=timezone.utc)
        until = datetime(2025, 1, 14, tzinfo=timezone.utc)

        search_item = {
            "number": 42,
            "title": "Old PR merged recently",
            "state": "closed",
            "html_url": "https://github.com/testorg/repo1/pull/42",
            "repository_url": "https://api.github.com/repos/testorg/repo1",
            "created_at": "2024-11-01T10:00:00Z",
            "pull_request": {
                "merged_at": "2025-01-10T14:00:00Z",
            },
        }

        with patch.object(client, "_paginate_search", return_value=iter([search_item])):
            prs = client.search_merged_prs("testuser", since, until)

        assert len(prs) == 1
        pr = prs[0]
        assert pr.number == 42
        assert pr.title == "Old PR merged recently"
        assert pr.merged is True
        assert pr.repo == "repo1"
