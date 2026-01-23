"""MCP tools for GitHub data."""

import logging

from mcp.types import Tool

from ..clients.github_client import GitHubClient
from ..models import Config, GitHubContributions
from ..utils import parse_date_range

logger = logging.getLogger(__name__)


def get_github_tools() -> list[Tool]:
    """Return list of GitHub-related MCP tools."""
    return [
        Tool(
            name="get_github_contributions",
            description=(
                "Get GitHub contributions for a team member. Returns PRs merged "
                "(excludes open/unmerged PRs), code reviews given (filtered by PR creation date, "
                "not review date), and total lines changed."
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
        Tool(
            name="get_team_members",
            description=(
                "Get list of configured team members with their names and usernames."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


async def handle_get_github_contributions(
    config: Config,
    github_username: str,
    days: int = 14,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """Fetch GitHub contributions for a team member.

    Args:
        config: Application configuration.
        github_username: GitHub username.
        days: Number of days to look back. Ignored if start_date is provided.
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.

    Returns:
        Dict containing PRs merged, reviews given, and line counts.
    """
    if github_username not in config.team_members:
        return {
            "error": f"Unknown team member: {github_username}. "
            f"Available: {', '.join(config.team_members.keys())}"
        }

    member = config.team_members[github_username]

    date_range = parse_date_range(days, start_date, end_date)
    if isinstance(date_range, dict):
        return date_range
    since, until = date_range

    contributions = GitHubContributions()
    warnings = []

    with GitHubClient(config.github) as client:
        try:
            prs = client.search_prs(github_username, since, until)
        except Exception as e:
            logger.error(f"GitHub PR search failed: {e}")
            return {"error": f"Failed to fetch GitHub PRs: {str(e)}"}

        for pr in prs:
            if not pr.merged:
                continue

            pr_data = {
                "number": pr.number,
                "title": pr.title,
                "repo": pr.repo,
                "url": pr.url,
            }

            try:
                stats = client.get_pr_stats(config.github.org, pr.repo, pr.number)
                pr_data["additions"] = stats["additions"]
                pr_data["deletions"] = stats["deletions"]
                contributions.total_additions += stats["additions"]
                contributions.total_deletions += stats["deletions"]
            except Exception as e:
                logger.warning(f"Failed to get stats for PR #{pr.number}: {e}")
                pr_data["additions"] = 0
                pr_data["deletions"] = 0

            contributions.prs_merged.append(pr_data)

        try:
            reviews = client.get_reviews_by_user(github_username, since, until)
            for review in reviews:
                contributions.reviews_given.append({
                    "pr_title": review.pr_title,
                    "repo": review.repo,
                    "state": review.state,
                    "url": review.url,
                })
        except Exception as e:
            logger.warning(f"Failed to fetch reviews: {e}")
            warnings.append(f"Failed to fetch reviews: {str(e)}")

    result = {
        "member_name": member.name,
        "github_username": github_username,
        "start_date": since.strftime("%Y-%m-%d"),
        "end_date": until.strftime("%Y-%m-%d"),
        "prs_merged": contributions.prs_merged,
        "reviews_given": contributions.reviews_given,
        "total_additions": contributions.total_additions,
        "total_deletions": contributions.total_deletions,
        "summary": {
            "merged_count": len(contributions.prs_merged),
            "reviews_count": len(contributions.reviews_given),
            "net_lines": contributions.total_additions - contributions.total_deletions,
        },
    }
    if warnings:
        result["warnings"] = warnings
    return result


async def handle_get_team_members(config: Config) -> dict:
    """Get list of configured team members.

    Args:
        config: Application configuration.

    Returns:
        Dict containing list of team members with their details.
    """
    members = []
    for github_username, member in config.team_members.items():
        members.append({
            "github_username": github_username,
            "jira_account_id": member.jira_account_id,
            "name": member.name,
        })

    return {
        "team_members": members,
        "count": len(members),
    }
