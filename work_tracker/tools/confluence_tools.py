"""MCP tools for Confluence data."""

import logging

from mcp.types import Tool

from ..clients.confluence_client import ConfluenceClient
from ..models import Config
from ..utils import parse_date_range

logger = logging.getLogger(__name__)


def get_confluence_tools() -> list[Tool]:
    """Return list of Confluence-related MCP tools."""
    return [
        Tool(
            name="get_confluence_contributions",
            description=(
                "Get Confluence contributions for a team member. Returns pages created, "
                "pages updated, comments added, and blog posts within the specified time range."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "github_username": {
                        "type": "string",
                        "description": "GitHub username of the team member",
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of days to look back (default: 14). Must be 1-365. Ignored if start_date is provided.",
                        "default": 14,
                        "minimum": 1,
                        "maximum": 365,
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format. If provided, overrides 'days'.",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format. Defaults to today if not provided.",
                    },
                },
                "required": ["github_username"],
            },
        ),
    ]


async def handle_get_confluence_contributions(
    config: Config,
    github_username: str,
    days: int = 14,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """Fetch Confluence contributions for a team member.

    Args:
        config: Application configuration.
        github_username: GitHub username to look up.
        days: Number of days to look back. Ignored if start_date is provided.
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.

    Returns:
        Dict containing pages_created, pages_updated, comments_added, and blogposts.
    """
    if config.confluence is None:
        return {
            "error": "Confluence is not configured. Add a 'confluence' section to your config file."
        }

    if github_username not in config.team_members:
        return {
            "error": f"Unknown team member: {github_username}. "
            f"Available: {', '.join(config.team_members.keys())}"
        }

    member = config.team_members[github_username]
    account_id = member.atlassian_account_id

    date_range = parse_date_range(days, start_date, end_date)
    if isinstance(date_range, dict):
        return date_range
    since, until = date_range

    with ConfluenceClient(config.confluence) as client:
        try:
            contributions_data = client.get_user_contributions(
                account_id=account_id,
                since=since,
                until=until,
                space_keys=config.confluence.space_keys,
            )
        except Exception as e:
            logger.error(f"Confluence search failed: {e}")
            return {"error": f"Failed to fetch Confluence data: {str(e)}"}

    return {
        "member_name": member.name,
        "github_username": github_username,
        "start_date": since.strftime("%Y-%m-%d"),
        "end_date": until.strftime("%Y-%m-%d"),
        "space_keys": config.confluence.space_keys,
        "pages_created": contributions_data["pages_created"],
        "pages_updated": contributions_data["pages_updated"],
        "comments_added": contributions_data["comments"],
        "blogposts": contributions_data["blogposts"],
        "summary": {
            "pages_created_count": len(contributions_data["pages_created"]),
            "pages_updated_count": len(contributions_data["pages_updated"]),
            "comments_count": len(contributions_data["comments"]),
            "blogposts_count": len(contributions_data["blogposts"]),
        },
    }
