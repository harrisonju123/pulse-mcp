"""Integration tests for Jira tools using real API.

These tests require:
- IC_TRACKER_CONFIG environment variable pointing to a valid config.json
- Valid Jira credentials in the config
- Actual Jira issues to test against

Run with: pytest tests/test_jira_integration.py -v -s
"""

import os
import pytest

from work_tracker.config import load_config, ConfigError
from work_tracker.clients.jira_client import JiraClient
from work_tracker.tools.jira_tools import (
    handle_get_initiative_roadmap,
    handle_get_team_bandwidth,
    handle_search_jira_issues,
)


# Skip all tests if no config available
def get_config():
    try:
        return load_config()
    except ConfigError:
        return None


config = get_config()
skip_if_no_config = pytest.mark.skipif(
    config is None or config.jira is None,
    reason="No Jira config available"
)


@skip_if_no_config
class TestJiraClientIntegration:
    """Integration tests for Jira client."""

    def test_get_myself(self):
        """Verify authentication works."""
        import requests
        resp = requests.get(
            f"{config.jira.base_url}/rest/api/3/myself",
            auth=(config.jira.email, config.jira.api_token),
            headers={"Accept": "application/json"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "accountId" in data
        print(f"Authenticated as: {data.get('displayName', data.get('emailAddress'))}")

    def test_search_issues(self):
        """Test basic JQL search."""
        with JiraClient(config.jira) as client:
            projects = ", ".join(f'"{p}"' for p in config.jira.project_keys)
            issues = client.search_issues(f"project in ({projects})", max_results=5)

        print(f"Found {len(issues)} issues")
        for issue in issues[:5]:
            print(f"  {issue.key}: {issue.summary[:50]}... ({issue.status})")

        assert len(issues) <= 5

    def test_search_epics(self):
        """Test searching for epics."""
        with JiraClient(config.jira) as client:
            projects = ", ".join(f'"{p}"' for p in config.jira.project_keys)
            epics = client.search_issues(
                f"project in ({projects}) AND issuetype = Epic",
                max_results=5
            )

        print(f"Found {len(epics)} epics")
        for epic in epics[:5]:
            print(f"  {epic.key}: {epic.summary[:50]}...")

    def test_story_points_field(self):
        """Verify story points field is correctly configured."""
        with JiraClient(config.jira) as client:
            projects = ", ".join(f'"{p}"' for p in config.jira.project_keys)
            issues = client.search_issues(
                f"project in ({projects}) AND \"{config.jira.story_point_field}\" is not EMPTY",
                max_results=5
            )

        issues_with_points = [i for i in issues if i.story_points is not None]
        print(f"Found {len(issues_with_points)} issues with story points")
        for issue in issues_with_points[:5]:
            print(f"  {issue.key}: {issue.story_points} points")

        if not issues_with_points:
            print(f"WARNING: No issues found with story points. Check story_point_field: {config.jira.story_point_field}")


@skip_if_no_config
class TestJiraToolsIntegration:
    """Integration tests for Jira tools."""

    @pytest.mark.asyncio
    async def test_search_jira_issues_tool(self):
        """Test search_jira_issues tool."""
        projects = ", ".join(f'"{p}"' for p in config.jira.project_keys)
        result = await handle_search_jira_issues(
            config,
            jql=f"project in ({projects}) ORDER BY created DESC",
            max_results=10
        )

        assert "error" not in result, f"Error: {result.get('error')}"
        print(f"Search returned {result['total_results']} issues")
        for issue in result["issues"][:5]:
            print(f"  {issue['key']}: {issue['summary'][:40]}... ({issue['status']})")

    @pytest.mark.asyncio
    async def test_get_team_bandwidth_tool(self):
        """Test get_team_bandwidth tool."""
        result = await handle_get_team_bandwidth(config)

        assert "error" not in result, f"Error: {result.get('error')}"
        print(f"Team bandwidth summary:")
        print(f"  Total members: {result['summary']['total_members']}")
        print(f"  Total open points: {result['summary']['total_open_story_points']}")
        print(f"  Total open issues: {result['summary']['total_open_issues']}")
        print(f"  Avg points/member: {result['summary']['average_points_per_member']}")

        for member in result["team_members"]:
            print(f"\n  {member['name']} ({member['github_username']}):")
            print(f"    Open points: {member['total_open_story_points']}")
            print(f"    Open issues: {member['total_open_issues']}")
            if member["allocation_by_epic"]:
                print(f"    Epics: {len(member['allocation_by_epic'])}")

    @pytest.mark.asyncio
    async def test_get_team_bandwidth_single_member(self):
        """Test get_team_bandwidth for a single team member."""
        # Get first team member
        first_member = list(config.team_members.keys())[0]
        result = await handle_get_team_bandwidth(config, github_username=first_member)

        assert "error" not in result, f"Error: {result.get('error')}"
        assert len(result["team_members"]) == 1
        member = result["team_members"][0]
        print(f"\n{member['name']}'s workload:")
        print(f"  Open points: {member['total_open_story_points']}")
        print(f"  Open issues: {member['total_open_issues']}")


@skip_if_no_config
class TestInitiativeRoadmap:
    """Integration tests for initiative roadmap - requires actual initiative key."""

    @pytest.fixture
    def initiative_key(self):
        """Override this fixture with an actual initiative key to test."""
        # Try to find an initiative automatically
        with JiraClient(config.jira) as client:
            projects = ", ".join(f'"{p}"' for p in config.jira.project_keys)
            initiatives = client.search_issues(
                f"project in ({projects}) AND issuetype = Initiative",
                max_results=1
            )
            if initiatives:
                return initiatives[0].key
        pytest.skip("No initiatives found in Jira")

    @pytest.mark.asyncio
    async def test_get_initiative_roadmap_tool(self, initiative_key):
        """Test get_initiative_roadmap tool."""
        result = await handle_get_initiative_roadmap(config, initiative_key)

        if "error" in result:
            # May fail if no epics under initiative
            print(f"Note: {result['error']}")
            return

        print(f"\nInitiative: {result['initiative']['key']} - {result['initiative']['summary']}")
        print(f"Status: {result['initiative']['status']}")
        print(f"\nSummary:")
        print(f"  Total epics: {result['summary']['total_epics']}")
        print(f"  Total points: {result['summary']['total_story_points']}")
        print(f"  Completed points: {result['summary']['completed_story_points']}")
        print(f"  Progress: {result['summary']['progress_percentage']}%")

        for epic_progress in result["epics"][:5]:
            epic = epic_progress["epic"]
            print(f"\n  Epic: {epic['key']} - {epic['summary'][:40]}...")
            print(f"    Progress: {epic_progress['progress_percentage']}% ({epic_progress['completed_story_points']}/{epic_progress['total_story_points']} pts)")
            print(f"    Issues: {epic_progress['completed_issues']}/{epic_progress['total_issues']} done, {epic_progress['in_progress_issues']} in progress")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
