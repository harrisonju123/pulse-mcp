#!/usr/bin/env python3
"""Work Tracker MCP Server - Fetch GitHub/Confluence contribution data."""

import argparse
import asyncio
import json
import logging
import sys

import requests
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent

from work_tracker.config import ConfigError, load_config
from work_tracker.tools.confluence_tools import (
    get_confluence_tools,
    handle_get_confluence_contributions,
)
from work_tracker.tools.feedback_tools import (
    get_feedback_tools,
    handle_get_peer_feedback,
)
from work_tracker.tools.github_tools import (
    get_github_tools,
    handle_get_competency_analysis,
    handle_get_contribution_distribution,
    handle_get_contribution_trends,
    handle_get_github_contributions,
    handle_get_self,
    handle_get_team_members,
    handle_get_teams,
)
from work_tracker.tools.goal_tools import (
    get_goal_tools,
    handle_add_goal,
    handle_get_goal_progress,
    handle_get_goals,
    handle_update_goal_progress,
)
from work_tracker.tools.journal_tools import (
    get_journal_tools,
    handle_add_journal_entry,
    handle_get_journal_entries,
    handle_search_journal,
)
from work_tracker.tools.jira_tools import (
    get_jira_tools,
    handle_get_initiative_roadmap,
    handle_get_team_bandwidth,
    handle_search_jira_issues,
    handle_update_jira_issue,
)
from work_tracker.tools.pulse_tools import (
    get_pulse_tools,
    handle_get_member_pulse,
    handle_get_pr_details,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

server = Server("work-tracker")
config = None


@server.list_tools()
async def list_tools():
    """List available MCP tools."""
    tools = get_github_tools()
    tools += get_feedback_tools()
    tools += get_pulse_tools()
    tools += get_goal_tools()
    tools += get_journal_tools()
    if config and config.confluence:
        tools += get_confluence_tools()
    if config and config.jira:
        tools += get_jira_tools()
    return tools


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Handle tool calls."""
    global config

    if config is None:
        return [TextContent(
            type="text",
            text=json.dumps({"error": "Configuration not loaded"})
        )]

    # Validate required parameters for tools that need github_username
    tools_requiring_username = (
        "get_github_contributions",
        "get_confluence_contributions",
        "get_contribution_trends",
        "get_contribution_distribution",
        "get_competency_analysis",
        "get_peer_feedback",
        "get_member_pulse",
    )
    if name in tools_requiring_username:
        if not arguments.get("github_username"):
            return [TextContent(
                type="text",
                text=json.dumps({"error": "github_username is required"})
            )]

    # Validate days parameter if provided
    if "days" in arguments:
        days = arguments["days"]
        if not isinstance(days, int) or days < 1 or days > 365:
            return [TextContent(
                type="text",
                text=json.dumps({"error": "days must be an integer between 1 and 365"})
            )]

    # Validate required parameters for Jira tools
    if name == "get_initiative_roadmap" and not arguments.get("initiative_key"):
        return [TextContent(
            type="text",
            text=json.dumps({"error": "initiative_key is required"})
        )]

    if name == "search_jira_issues" and not arguments.get("jql"):
        return [TextContent(
            type="text",
            text=json.dumps({"error": "jql is required"})
        )]

    if name == "update_jira_issue" and not arguments.get("issue_key"):
        return [TextContent(
            type="text",
            text=json.dumps({"error": "issue_key is required"})
        )]

    if name == "get_pr_details":
        if not arguments.get("repo"):
            return [TextContent(
                type="text",
                text=json.dumps({"error": "repo is required"})
            )]
        if not arguments.get("pr_number"):
            return [TextContent(
                type="text",
                text=json.dumps({"error": "pr_number is required"})
            )]

    try:
        if name == "get_github_contributions":
            result = await handle_get_github_contributions(
                config,
                github_username=arguments.get("github_username"),
                days=arguments.get("days", 14),
                start_date=arguments.get("start_date"),
                end_date=arguments.get("end_date"),
            )
        elif name == "get_teams":
            result = await handle_get_teams(config)
        elif name == "get_team_members":
            result = await handle_get_team_members(config, team=arguments.get("team"))
        elif name == "get_self":
            result = await handle_get_self(config)
        elif name == "get_confluence_contributions":
            result = await handle_get_confluence_contributions(
                config,
                github_username=arguments.get("github_username"),
                days=arguments.get("days", 14),
                start_date=arguments.get("start_date"),
                end_date=arguments.get("end_date"),
            )
        elif name == "get_initiative_roadmap":
            result = await handle_get_initiative_roadmap(
                config,
                initiative_key=arguments.get("initiative_key"),
            )
        elif name == "get_team_bandwidth":
            result = await handle_get_team_bandwidth(
                config,
                github_username=arguments.get("github_username"),
                initiative_key=arguments.get("initiative_key"),
            )
        elif name == "search_jira_issues":
            result = await handle_search_jira_issues(
                config,
                jql=arguments.get("jql"),
                max_results=arguments.get("max_results", 50),
            )
        elif name == "update_jira_issue":
            result = await handle_update_jira_issue(
                config,
                issue_key=arguments.get("issue_key"),
                summary=arguments.get("summary"),
                description=arguments.get("description"),
            )
        elif name == "get_contribution_trends":
            result = await handle_get_contribution_trends(
                config,
                github_username=arguments.get("github_username"),
                period_type=arguments.get("period_type", "biweekly"),
                num_periods=arguments.get("num_periods", 4),
            )
        elif name == "get_contribution_distribution":
            result = await handle_get_contribution_distribution(
                config,
                github_username=arguments.get("github_username"),
                days=arguments.get("days", 90),
                start_date=arguments.get("start_date"),
                end_date=arguments.get("end_date"),
                max_prs=arguments.get("max_prs", 25),
            )
        elif name == "get_competency_analysis":
            result = await handle_get_competency_analysis(
                config,
                github_username=arguments.get("github_username"),
                days=arguments.get("days", 90),
                start_date=arguments.get("start_date"),
                end_date=arguments.get("end_date"),
            )
        elif name == "get_peer_feedback":
            result = await handle_get_peer_feedback(
                config,
                github_username=arguments.get("github_username"),
                period=arguments.get("period"),
            )
        elif name == "get_member_pulse":
            result = await handle_get_member_pulse(
                config,
                github_username=arguments.get("github_username"),
                days=arguments.get("days", 14),
            )
        elif name == "get_pr_details":
            result = await handle_get_pr_details(
                config,
                repo=arguments.get("repo"),
                pr_number=arguments.get("pr_number"),
                include_diff=arguments.get("include_diff", False),
            )
        elif name == "get_goals":
            result = await handle_get_goals(
                config,
                github_username=arguments.get("github_username"),
                status=arguments.get("status", "active"),
            )
        elif name == "add_goal":
            result = await handle_add_goal(
                config,
                title=arguments.get("title"),
                description=arguments.get("description"),
                category=arguments.get("category", "general"),
                target_date=arguments.get("target_date"),
                key_results=arguments.get("key_results"),
                github_username=arguments.get("github_username"),
            )
        elif name == "update_goal_progress":
            result = await handle_update_goal_progress(
                config,
                goal_id=arguments.get("goal_id"),
                status=arguments.get("status"),
                progress_note=arguments.get("progress_note"),
                key_result_updates=arguments.get("key_result_updates"),
                github_username=arguments.get("github_username"),
            )
        elif name == "get_goal_progress":
            result = await handle_get_goal_progress(
                config,
                goal_id=arguments.get("goal_id"),
                github_username=arguments.get("github_username"),
            )
        elif name == "add_journal_entry":
            result = await handle_add_journal_entry(
                config,
                content=arguments.get("content"),
                title=arguments.get("title"),
                tags=arguments.get("tags"),
                github_username=arguments.get("github_username"),
            )
        elif name == "get_journal_entries":
            result = await handle_get_journal_entries(
                config,
                days=arguments.get("days", 30),
                start_date=arguments.get("start_date"),
                end_date=arguments.get("end_date"),
                tags=arguments.get("tags"),
                github_username=arguments.get("github_username"),
            )
        elif name == "search_journal":
            result = await handle_search_journal(
                config,
                query=arguments.get("query"),
                days=arguments.get("days", 90),
                github_username=arguments.get("github_username"),
            )
        else:
            result = {"error": f"Unknown tool: {name}"}

    except Exception as e:
        logger.exception(f"Tool {name} failed")
        result = {"error": str(e)}

    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]


def validate_config() -> int:
    """Validate configuration and test API connections.

    Returns:
        Exit code: 0 if all validations pass, 1 if any fail.
    """
    print("Validating config...")
    errors = []

    # Load config
    try:
        cfg = load_config()
        print("✓ Config file loaded")
    except ConfigError as e:
        print(f"✗ Config file: {e}")
        return 1

    # Test GitHub token
    try:
        resp = requests.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {cfg.github.token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=10,
        )
        if resp.status_code == 200:
            username = resp.json().get("login", "unknown")
            print(f"✓ GitHub: authenticated as {username}")
        elif resp.status_code == 401:
            print("✗ GitHub: token is invalid or expired")
            print("  Fix: https://github.com/settings/tokens")
            errors.append("GitHub authentication failed")
        else:
            print(f"✗ GitHub: unexpected status {resp.status_code}")
            errors.append(f"GitHub returned status {resp.status_code}")
    except requests.RequestException as e:
        print(f"✗ GitHub: connection error - {e}")
        errors.append("GitHub connection failed")

    # Test Confluence token if configured
    if cfg.confluence:
        try:
            resp = requests.get(
                f"{cfg.confluence.base_url}/rest/api/user/current",
                auth=(cfg.confluence.email, cfg.confluence.api_token),
                headers={"Accept": "application/json"},
                timeout=10,
            )
            if resp.status_code == 200:
                email = resp.json().get("email", "unknown")
                print(f"✓ Confluence: authenticated as {email}")
            elif resp.status_code == 401:
                print("✗ Confluence: token is invalid or expired")
                print("  Fix: https://id.atlassian.com/manage-profile/security/api-tokens")
                errors.append("Confluence authentication failed")
            else:
                print(f"✗ Confluence: unexpected status {resp.status_code}")
                errors.append(f"Confluence returned status {resp.status_code}")
        except requests.RequestException as e:
            print(f"✗ Confluence: connection error - {e}")
            errors.append("Confluence connection failed")

    # Test Jira token if configured
    if cfg.jira:
        try:
            resp = requests.get(
                f"{cfg.jira.base_url}/rest/api/3/myself",
                auth=(cfg.jira.email, cfg.jira.api_token),
                headers={"Accept": "application/json"},
                timeout=10,
            )
            if resp.status_code == 200:
                email = resp.json().get("emailAddress", "unknown")
                print(f"✓ Jira: authenticated as {email}")
            elif resp.status_code == 401:
                print("✗ Jira: token is invalid or expired")
                print("  Fix: https://id.atlassian.com/manage-profile/security/api-tokens")
                errors.append("Jira authentication failed")
            else:
                print(f"✗ Jira: unexpected status {resp.status_code}")
                errors.append(f"Jira returned status {resp.status_code}")
        except requests.RequestException as e:
            print(f"✗ Jira: connection error - {e}")
            errors.append("Jira connection failed")

    # List teams and members
    total_members = len(cfg.team_members)
    if total_members == 0:
        print("✗ No team members configured")
        print("  Fix: Add entries to 'teams' or 'team_members' in config.json")
        errors.append("No team members configured")
    else:
        team_count = len(cfg.teams)
        if team_count == 1 and "default" in cfg.teams:
            # Legacy single-team format
            print(f"✓ {total_members} team member(s) configured")
        else:
            # Multi-team format
            print(f"✓ {team_count} team(s) with {total_members} total member(s) configured:")
            for team_id, team in cfg.teams.items():
                print(f"    - {team.name} ({team_id}): {len(team.members)} member(s)")

    # Summary
    print()
    if errors:
        print(f"{len(errors)} error(s) found. Fix and re-run validation.")
        return 1
    else:
        print("All checks passed!")
        return 0


async def run_server():
    """Run the MCP server."""
    global config

    try:
        config = load_config()
        logger.info(f"Loaded config with {len(config.team_members)} team members")
    except ConfigError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main():
    """Entry point with argument parsing."""
    parser = argparse.ArgumentParser(description="IC Tracker MCP Server")
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate config and test API connections, then exit",
    )
    args = parser.parse_args()

    if args.validate:
        sys.exit(validate_config())
    else:
        asyncio.run(run_server())


if __name__ == "__main__":
    main()
