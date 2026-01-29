"""MCP tools for qualitative team pulse analysis."""

import logging
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from mcp.types import Tool

from ..clients.github_client import GitHubClient
from ..models import Config
from ..utils import categorize_file

logger = logging.getLogger(__name__)


def _validate_team_member(config: Config, github_username: str) -> dict | None:
    """Validate that github_username is a configured team member.

    Args:
        config: Application configuration.
        github_username: GitHub username to validate.

    Returns:
        Error dict if invalid, None if valid.
    """
    if github_username not in config.team_members:
        return {
            "error": f"Unknown team member: {github_username}. "
            f"Available: {', '.join(config.team_members.keys())}"
        }
    return None


def _get_team_for_member(config: Config, github_username: str) -> str | None:
    """Get the team ID for a team member.

    Args:
        config: Application configuration.
        github_username: GitHub username.

    Returns:
        Team ID or None if not found.
    """
    for team_id, team in config.teams.items():
        if github_username in team.members:
            return team_id
    return None


def get_pulse_tools() -> list[Tool]:
    """Return list of pulse-related MCP tools."""
    return [
        Tool(
            name="get_member_pulse",
            description=(
                "Get qualitative work summary for a team member. Returns PR titles, "
                "reviewers, collaboration patterns, and open PRs - structured for "
                "narrative analysis rather than just counts."
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
                        "description": "Number of days to look back (default: 14). Must be 1-365.",
                        "default": 14,
                        "minimum": 1,
                        "maximum": 365,
                    },
                },
                "required": ["github_username"],
            },
        ),
        Tool(
            name="get_pr_details",
            description=(
                "Get detailed information about a specific PR including files changed, "
                "categorized as feature work vs generated/deps/tests. Optionally includes "
                "the actual diff content for deeper analysis of what was built."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "description": "Repository name (e.g., 'mauvelous-hippo')",
                    },
                    "pr_number": {
                        "type": "integer",
                        "description": "Pull request number",
                    },
                    "include_diff": {
                        "type": "boolean",
                        "description": "Include the actual diff content (default: false). Set to true for deeper analysis.",
                        "default": False,
                    },
                },
                "required": ["repo", "pr_number"],
            },
        ),
    ]


async def handle_get_member_pulse(
    config: Config,
    github_username: str,
    days: int = 14,
) -> dict:
    """Fetch qualitative work summary for a team member.

    Gathers rich PR data including titles, reviewers, and collaboration
    patterns for narrative analysis.

    Args:
        config: Application configuration.
        github_username: GitHub username.
        days: Number of days to look back.

    Returns:
        Dict with PR details, reviews given, collaboration data, and open PRs.
    """
    if error := _validate_team_member(config, github_username):
        return error

    if days < 1 or days > 365:
        return {"error": "days must be between 1 and 365"}

    member = config.team_members[github_username]
    team_id = _get_team_for_member(config, github_username)

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    until = now

    prs_merged = []
    reviews_given = []
    open_prs = []
    reviewed_by: Counter[str] = Counter()
    reviewed_for: Counter[str] = Counter()
    warnings = []

    with GitHubClient(config.github) as client:
        # Fetch merged PRs
        try:
            prs = client.search_prs(github_username, since, until)
            merged_prs = [pr for pr in prs if pr.merged]

            # Fetch reviewers for each merged PR in batch
            reviewers_map = client.get_reviewers_for_pr_batch(merged_prs)

            for pr in merged_prs:
                reviewers = reviewers_map.get((pr.repo, pr.number), [])

                pr_data = {
                    "number": pr.number,
                    "title": pr.title,
                    "repo": pr.repo,
                    "url": pr.url,
                    "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
                    "reviewers": reviewers,
                }
                prs_merged.append(pr_data)

                # Track who reviewed this person's PRs
                for reviewer in reviewers:
                    reviewed_by[reviewer] += 1

        except Exception as e:
            logger.error(f"GitHub PR search failed: {e}")
            return {"error": f"Failed to fetch GitHub PRs: {str(e)}"}

        # Fetch reviews given by this person
        try:
            reviews = client.get_reviews_by_user(github_username, since, until)
            for review in reviews:
                review_data = {
                    "pr_number": review.pr_number,
                    "pr_title": review.pr_title,
                    "repo": review.repo,
                    "url": review.url,
                }
                reviews_given.append(review_data)

                # Parse PR author from the URL or title to track reviewed_for
                # The CodeReview model doesn't have author, so we'd need to fetch it
                # For now, we'll leave reviewed_for empty and fill it from PR data if available

        except Exception as e:
            logger.warning(f"Failed to fetch reviews: {e}")
            warnings.append(f"Failed to fetch reviews: {str(e)}")

        # Fetch PR author info for reviews to populate reviewed_for
        # This requires additional API calls, but is important for collaboration data
        try:
            if reviews_given:
                # Get unique PR info for reviews
                pr_keys = list({(r["repo"], r["pr_number"]) for r in reviews_given})
                for repo, pr_number in pr_keys[:20]:  # Limit to 20 to avoid too many API calls
                    try:
                        pr_info = client._request(
                            "GET",
                            f"/repos/{config.github.org}/{repo}/pulls/{pr_number}",
                        )
                        author = pr_info.get("user", {}).get("login", "")
                        if author and author != github_username:
                            reviewed_for[author] += 1
                    except Exception as e:
                        logger.debug(f"Failed to get PR info for {repo}#{pr_number}: {e}")
        except Exception as e:
            logger.warning(f"Failed to fetch PR author info: {e}")

        # Fetch open PRs
        try:
            open_pr_list = client.search_open_prs(github_username)
            for pr in open_pr_list:
                days_open = (now - pr.created_at).days if pr.created_at else 0
                open_prs.append({
                    "number": pr.number,
                    "title": pr.title,
                    "repo": pr.repo,
                    "url": pr.url,
                    "days_open": days_open,
                })
        except Exception as e:
            logger.warning(f"Failed to fetch open PRs: {e}")
            warnings.append(f"Failed to fetch open PRs: {str(e)}")

    # Build collaboration data
    all_collaborators = set(reviewed_by.keys()) | set(reviewed_for.keys())
    # Find frequent collaborators (appear in both reviewed_by and reviewed_for)
    frequent_collaborators = [
        user for user in all_collaborators
        if reviewed_by.get(user, 0) > 0 and reviewed_for.get(user, 0) > 0
    ]

    # Sort by total interaction count
    frequent_collaborators.sort(
        key=lambda u: reviewed_by.get(u, 0) + reviewed_for.get(u, 0),
        reverse=True,
    )

    collaboration = {
        "reviewed_by": dict(reviewed_by.most_common(10)),
        "reviewed_for": dict(reviewed_for.most_common(10)),
        "frequent_collaborators": frequent_collaborators[:5],
    }

    result = {
        "github_username": github_username,
        "name": member.name,
        "team": team_id,
        "period": {
            "start": since.strftime("%Y-%m-%d"),
            "end": until.strftime("%Y-%m-%d"),
        },
        "prs_merged": prs_merged,
        "reviews_given": reviews_given,
        "collaboration": collaboration,
        "open_prs": open_prs,
        "summary": {
            "prs_count": len(prs_merged),
            "reviews_count": len(reviews_given),
            "unique_collaborators": len(all_collaborators),
            "open_pr_count": len(open_prs),
        },
    }

    if warnings:
        result["warnings"] = warnings

    return result


def _parse_diff_for_file(diff_content: str, filename: str) -> str | None:
    """Extract the diff for a specific file from the full diff content.

    Args:
        diff_content: Full diff content from the PR.
        filename: The file to extract diff for.

    Returns:
        The diff section for that file, or None if not found.
    """
    # Escape special regex characters in filename
    escaped_filename = re.escape(filename)

    # Match the diff section for this file
    # Format: diff --git a/path b/path ... until next diff --git or end
    pattern = rf"(diff --git a/{escaped_filename} b/{escaped_filename}.*?)(?=diff --git a/|$)"
    match = re.search(pattern, diff_content, re.DOTALL)

    if match:
        return match.group(1).strip()
    return None


async def handle_get_pr_details(
    config: Config,
    repo: str,
    pr_number: int,
    include_diff: bool = False,
) -> dict:
    """Get detailed information about a specific PR.

    Fetches files changed, categorizes them as feature work vs generated/deps/tests,
    and optionally includes the actual diff content.

    Args:
        config: Application configuration.
        repo: Repository name.
        pr_number: Pull request number.
        include_diff: Whether to include diff content.

    Returns:
        Dict with PR details, categorized files, and optionally diff content.
    """
    files_by_category: dict[str, list[dict]] = {
        "feature": [],
        "test": [],
        "generated": [],
        "deps": [],
        "vendor": [],
        "build": [],
        "snapshot": [],
        "ide": [],
    }

    total_additions = 0
    total_deletions = 0
    feature_additions = 0
    feature_deletions = 0

    diff_content = None

    with GitHubClient(config.github) as client:
        # Fetch files changed
        try:
            files = client.get_pr_files(config.github.org, repo, pr_number)
        except Exception as e:
            logger.error(f"Failed to fetch PR files: {e}")
            return {"error": f"Failed to fetch PR files: {str(e)}"}

        # Optionally fetch diff
        if include_diff:
            try:
                diff_content = client.get_pr_diff(config.github.org, repo, pr_number)
            except Exception as e:
                logger.warning(f"Failed to fetch diff: {e}")

        # Categorize each file
        for file_info in files:
            filename = file_info.get("filename", "")
            if not filename:
                continue

            category = categorize_file(filename)
            additions = file_info.get("additions", 0)
            deletions = file_info.get("deletions", 0)

            total_additions += additions
            total_deletions += deletions

            file_data = {
                "path": filename,
                "additions": additions,
                "deletions": deletions,
                "status": file_info.get("status", "modified"),
            }

            # For feature files, optionally include the diff
            if category == "feature":
                feature_additions += additions
                feature_deletions += deletions

                if include_diff and diff_content:
                    file_diff = _parse_diff_for_file(diff_content, filename)
                    if file_diff:
                        # Truncate very large diffs
                        if len(file_diff) > 5000:
                            file_data["diff"] = file_diff[:5000] + "\n... (truncated)"
                        else:
                            file_data["diff"] = file_diff

            files_by_category[category].append(file_data)

    # Build summary
    summary = {
        "total_files": len(files),
        "feature_files": len(files_by_category["feature"]),
        "test_files": len(files_by_category["test"]),
        "generated_files": len(files_by_category["generated"]),
        "deps_files": len(files_by_category["deps"]),
        "total_additions": total_additions,
        "total_deletions": total_deletions,
        "feature_additions": feature_additions,
        "feature_deletions": feature_deletions,
        "feature_pct": round(
            (feature_additions + feature_deletions) / max(total_additions + total_deletions, 1) * 100,
            1
        ),
    }

    result = {
        "repo": repo,
        "pr_number": pr_number,
        "summary": summary,
        "feature_files": files_by_category["feature"],
        "test_files": files_by_category["test"],
        "other_files": {
            "generated": files_by_category["generated"],
            "deps": files_by_category["deps"],
            "vendor": files_by_category["vendor"],
            "build": files_by_category["build"],
            "snapshot": files_by_category["snapshot"],
        },
    }

    # Add guidance for analysis
    if files_by_category["feature"]:
        result["analysis_hint"] = (
            f"Focus on the {len(files_by_category['feature'])} feature files. "
            f"They represent {summary['feature_pct']}% of the changes."
        )
    else:
        result["analysis_hint"] = (
            "No feature files detected - this PR may be primarily tests, "
            "dependency updates, or generated code."
        )

    return result
