#!/usr/bin/env python3
"""IC Tracker MCP Server - Fetch GitHub/Confluence contribution data."""

import argparse
import asyncio
import json
import logging
import sys

import requests
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent

from ic_tracker.config import ConfigError, load_config
from ic_tracker.tools.confluence_tools import (
    get_confluence_tools,
    handle_get_confluence_contributions,
)
from ic_tracker.tools.github_tools import (
    get_github_tools,
    handle_get_github_contributions,
    handle_get_team_members,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

server = Server("ic-tracker")
config = None


@server.list_tools()
async def list_tools():
    """List available MCP tools."""
    tools = get_github_tools()
    if config and config.confluence:
        tools += get_confluence_tools()
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

    try:
        if name == "get_github_contributions":
            result = await handle_get_github_contributions(
                config,
                github_username=arguments.get("github_username"),
                days=arguments.get("days", 14),
                start_date=arguments.get("start_date"),
                end_date=arguments.get("end_date"),
            )
        elif name == "get_team_members":
            result = await handle_get_team_members(config)
        elif name == "get_confluence_contributions":
            result = await handle_get_confluence_contributions(
                config,
                github_username=arguments.get("github_username"),
                days=arguments.get("days", 14),
                start_date=arguments.get("start_date"),
                end_date=arguments.get("end_date"),
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

    # List team members
    if len(cfg.team_members) == 0:
        print("✗ No team members configured")
        print("  Fix: Add entries to team_members in config.json")
        errors.append("No team members configured")
    else:
        print(f"✓ {len(cfg.team_members)} team member(s) configured")

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
