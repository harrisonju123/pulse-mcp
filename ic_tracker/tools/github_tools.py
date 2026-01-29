"""MCP tools for GitHub data."""

import logging
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from dateutil.parser import parse as parse_date
from mcp.types import Tool

from ..clients.github_client import GitHubClient
from ..competency_mapper import analyze_contributions_for_competencies, get_competency_summary
from ..models import Config, GitHubContributions
from ..utils import get_file_extension, infer_area_from_path, parse_date_range

logger = logging.getLogger(__name__)


def _ensure_timezone_aware(dt: datetime | None) -> datetime | None:
    """Ensure datetime is timezone-aware (assumes UTC if naive)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


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


def _parse_and_validate_date_range(
    days: int,
    start_date: str | None,
    end_date: str | None,
) -> tuple[datetime, datetime] | dict:
    """Parse and validate date range parameters.

    Args:
        days: Number of days to look back.
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.

    Returns:
        Tuple of (since, until) datetimes, or error dict if validation fails.
    """
    return parse_date_range(days, start_date, end_date)


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
            name="get_teams",
            description=(
                "Get list of configured teams with their names and member counts."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="get_team_members",
            description=(
                "Get list of configured team members with their names and usernames."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "team": {
                        "type": "string",
                        "description": "Optional team ID to filter members by. If not provided, returns all members across all teams.",
                    },
                },
            },
        ),
        Tool(
            name="get_contribution_trends",
            description=(
                "Compare contributions across time periods (week-over-week, biweekly, or monthly). "
                "Returns contribution counts per period and trend percentages."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "github_username": {
                        "type": "string",
                        "description": "GitHub username of the team member",
                    },
                    "period_type": {
                        "type": "string",
                        "enum": ["weekly", "biweekly", "monthly"],
                        "description": "Type of period to analyze (weekly, biweekly, or monthly)",
                        "default": "biweekly",
                    },
                    "num_periods": {
                        "type": "integer",
                        "description": "Number of periods to analyze (default: 4)",
                        "default": 4,
                        "minimum": 2,
                        "maximum": 12,
                    },
                },
                "required": ["github_username"],
            },
        ),
        Tool(
            name="get_contribution_distribution",
            description=(
                "Get distribution of contributions by repository, file type, and inferred work area "
                "(frontend, backend, infrastructure, etc.)."
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
                        "description": "Number of days to look back (default: 90). Must be 1-365.",
                        "default": 90,
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
                    "max_prs": {
                        "type": "integer",
                        "description": "Maximum number of PRs to analyze for file distribution (default: 25). Limits API calls.",
                        "default": 25,
                        "minimum": 1,
                        "maximum": 100,
                    },
                },
                "required": ["github_username"],
            },
        ),
        Tool(
            name="get_competency_analysis",
            description=(
                "Analyze contributions to map to EGF competencies (Execution & Delivery, Skills & Knowledge, "
                "Teamwork & Communication, Influence & Leadership). Returns evidence mapped to competencies "
                "with strength levels and reasoning."
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
                        "description": "Number of days to look back (default: 90). Must be 1-365.",
                        "default": 90,
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
    if error := _validate_team_member(config, github_username):
        return error

    member = config.team_members[github_username]

    date_range = _parse_and_validate_date_range(days, start_date, end_date)
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

        # Filter to merged PRs and fetch stats in parallel
        merged_prs = [pr for pr in prs if pr.merged]
        stats_map = client.get_pr_stats_batch(merged_prs)

        for pr in merged_prs:
            pr_data = {
                "number": pr.number,
                "title": pr.title,
                "repo": pr.repo,
                "url": pr.url,
            }

            stats = stats_map.get((pr.repo, pr.number), {"additions": 0, "deletions": 0})
            pr_data["additions"] = stats["additions"]
            pr_data["deletions"] = stats["deletions"]
            contributions.total_additions += stats["additions"]
            contributions.total_deletions += stats["deletions"]

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

        # Calculate review turnaround times for reviews given by this user
        review_turnarounds = []
        try:
            review_turnarounds = _calculate_review_turnarounds(
                client, config.github.org, github_username, since, until
            )
        except Exception as e:
            logger.warning(f"Failed to calculate review turnarounds: {e}")
            warnings.append(f"Failed to calculate review turnarounds: {str(e)}")

    # Build review turnaround summary
    turnaround_summary = None
    if review_turnarounds:
        valid_hours = [r["turnaround_hours"] for r in review_turnarounds if r.get("turnaround_hours") is not None]
        if valid_hours:
            turnaround_summary = {
                "avg_hours": round(statistics.mean(valid_hours), 1),
                "median_hours": round(statistics.median(valid_hours), 1),
                "min_hours": round(min(valid_hours), 1),
                "max_hours": round(max(valid_hours), 1),
                "review_count": len(valid_hours),
                "reviews": review_turnarounds[:10],  # Limit to 10 most recent
            }

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
    if turnaround_summary:
        result["review_turnaround"] = turnaround_summary
    if warnings:
        result["warnings"] = warnings
    return result


async def handle_get_teams(config: Config) -> dict:
    """Get list of configured teams.

    Args:
        config: Application configuration.

    Returns:
        Dict containing list of teams with names, member counts, and members.
    """
    teams_list = []
    total_members = 0

    for team_id, team in config.teams.items():
        members = [
            {
                "github_username": username,
                "atlassian_account_id": member.atlassian_account_id,
                "name": member.name,
            }
            for username, member in team.members.items()
        ]
        teams_list.append({
            "id": team_id,
            "name": team.name,
            "member_count": len(team.members),
            "members": members,
        })
        total_members += len(team.members)

    return {
        "teams": teams_list,
        "total_teams": len(teams_list),
        "total_members": total_members,
    }


async def handle_get_team_members(config: Config, team: str | None = None) -> dict:
    """Get list of configured team members.

    Args:
        config: Application configuration.
        team: Optional team ID to filter by.

    Returns:
        Dict containing list of team members with their details.
    """
    if team is not None:
        # Filter by specific team
        if team not in config.teams:
            return {
                "error": f"Unknown team: {team}. Available teams: {', '.join(config.teams.keys())}"
            }
        team_obj = config.teams[team]
        members = [
            {
                "github_username": username,
                "atlassian_account_id": member.atlassian_account_id,
                "name": member.name,
                "team": team,
            }
            for username, member in team_obj.members.items()
        ]
        return {
            "team_members": members,
            "count": len(members),
            "team": {"id": team, "name": team_obj.name},
        }
    else:
        # Return all members across all teams
        members = []
        for team_id, team_obj in config.teams.items():
            for username, member in team_obj.members.items():
                members.append({
                    "github_username": username,
                    "atlassian_account_id": member.atlassian_account_id,
                    "name": member.name,
                    "team": team_id,
                })

        return {
            "team_members": members,
            "count": len(members),
        }


MAX_TURNAROUND_SAMPLES = 5  # Limit API calls for turnaround calculation


def _calculate_review_turnarounds(
    client: GitHubClient,
    org: str,
    reviewer_username: str,
    since: datetime,
    until: datetime,
    max_samples: int = MAX_TURNAROUND_SAMPLES,
) -> list[dict]:
    """Calculate review turnaround times for reviews given by a user.

    Turnaround is measured from when the reviewer was requested to when they
    submitted their first review.

    Args:
        client: GitHub API client.
        org: GitHub organization.
        reviewer_username: Username of the reviewer.
        since: Start of date range.
        until: End of date range.
        max_samples: Maximum number of reviews to analyze (limits API calls).

    Returns:
        List of dicts with turnaround details for each review.
    """
    turnarounds = []

    # Get PRs reviewed by this user
    reviews = client.get_reviews_by_user(reviewer_username, since, until)

    # Limit to max_samples and fetch all turnaround data in parallel
    reviews_to_analyze = reviews[:max_samples]
    turnaround_data_map = client.get_turnaround_data_batch(reviews_to_analyze)

    for review in reviews_to_analyze:
        data = turnaround_data_map.get((review.repo, review.pr_number))
        if not data:
            continue

        try:
            timeline = data.get("timeline", [])
            pr_reviews = data.get("reviews", [])

            # Find when this reviewer was requested
            requested_at = None
            for event in timeline:
                if event.get("event") == "review_requested":
                    requested_reviewer = event.get("requested_reviewer", {})
                    if requested_reviewer.get("login", "").lower() == reviewer_username.lower():
                        if event.get("created_at"):
                            requested_at = parse_date(event["created_at"])
                            break

            # Get actual review submission time from reviews endpoint
            reviewed_at = None
            for pr_review in pr_reviews:
                reviewer = pr_review.get("user", {})
                if reviewer.get("login", "").lower() == reviewer_username.lower():
                    if pr_review.get("submitted_at"):
                        reviewed_at = parse_date(pr_review["submitted_at"])
                        break

            turnaround_hours = None
            if requested_at and reviewed_at and reviewed_at > requested_at:
                delta = reviewed_at - requested_at
                turnaround_hours = delta.total_seconds() / 3600

            turnarounds.append({
                "pr_number": review.pr_number,
                "pr_title": review.pr_title,
                "repo": review.repo,
                "pr_url": review.url,
                "requested_at": requested_at.isoformat() if requested_at else None,
                "reviewed_at": reviewed_at.isoformat() if reviewed_at else None,
                "turnaround_hours": round(turnaround_hours, 1) if turnaround_hours is not None else None,
            })

        except Exception as e:
            logger.warning(f"Failed to process turnaround for PR #{review.pr_number}: {e}")
            continue

    return turnarounds


async def handle_get_contribution_trends(
    config: Config,
    github_username: str,
    period_type: str = "biweekly",
    num_periods: int = 4,
) -> dict:
    """Get contribution trends across multiple time periods.

    Args:
        config: Application configuration.
        github_username: GitHub username.
        period_type: Type of period (weekly, biweekly, monthly).
        num_periods: Number of periods to analyze.

    Returns:
        Dict containing contribution counts per period and trends.
    """
    if error := _validate_team_member(config, github_username):
        return error

    # Validate period_type
    valid_period_types = {"weekly": 7, "biweekly": 14, "monthly": 30}
    if period_type not in valid_period_types:
        return {
            "error": f"Invalid period_type: {period_type}. "
            f"Must be one of: {', '.join(valid_period_types.keys())}"
        }

    member = config.team_members[github_username]

    # Calculate period length in days
    period_days = valid_period_types[period_type]

    # Generate date ranges for each period (most recent first)
    periods = []
    now = datetime.now(timezone.utc)

    for i in range(num_periods):
        end_date = now - timedelta(days=i * period_days)
        start_date = end_date - timedelta(days=period_days)
        periods.append((start_date, end_date, i))

    # Reverse to chronological order
    periods.reverse()

    period_contributions = []
    warnings = []

    with GitHubClient(config.github) as client:
        # Fetch all PRs and reviews for the entire date range at once
        overall_start = periods[0][0]
        overall_end = periods[-1][1]

        try:
            all_prs = client.search_prs(github_username, overall_start, overall_end)
            all_reviews = client.get_reviews_by_user(github_username, overall_start, overall_end)
        except Exception as e:
            logger.error(f"GitHub search failed: {e}")
            return {"error": f"Failed to fetch GitHub data: {str(e)}"}

        # Fetch stats for all merged PRs in parallel
        merged_prs = [pr for pr in all_prs if pr.merged]
        stats_map = client.get_pr_stats_batch(merged_prs)

        # Group PRs and reviews by period
        for start_date, end_date, period_idx in periods:
            # Generate period label
            if period_type == "weekly":
                label = f"{start_date.strftime('%Y-W%W')}"
            elif period_type == "monthly":
                label = f"{start_date.strftime('%Y-%m')}"
            else:
                label = f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"

            period_data = {
                "period_label": label,
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "prs_merged": 0,
                "reviews_given": 0,
                "lines_added": 0,
                "lines_removed": 0,
            }

            # Filter PRs for this period
            for pr in merged_prs:
                pr_created = _ensure_timezone_aware(pr.created_at)
                if pr_created and start_date <= pr_created <= end_date:
                    period_data["prs_merged"] += 1
                    stats = stats_map.get((pr.repo, pr.number), {"additions": 0, "deletions": 0})
                    period_data["lines_added"] += stats.get("additions", 0)
                    period_data["lines_removed"] += stats.get("deletions", 0)

            # Filter reviews for this period (based on PR creation date)
            for review in all_reviews:
                review_submitted = _ensure_timezone_aware(review.submitted_at)
                if review_submitted and start_date <= review_submitted <= end_date:
                    period_data["reviews_given"] += 1

            period_contributions.append(period_data)

    # Calculate trends (percent change from first to last period)
    def calc_trend(values: list[int]) -> float | None:
        if len(values) < 2 or values[0] == 0:
            return None
        return round(((values[-1] - values[0]) / values[0]) * 100, 1)

    pr_values = [p["prs_merged"] for p in period_contributions]
    review_values = [p["reviews_given"] for p in period_contributions]
    lines_values = [p["lines_added"] + p["lines_removed"] for p in period_contributions]

    result = {
        "member_name": member.name,
        "github_username": github_username,
        "period_type": period_type,
        "num_periods": num_periods,
        "periods": period_contributions,
        "trends": {
            "pr_trend_pct": calc_trend(pr_values),
            "review_trend_pct": calc_trend(review_values),
            "lines_trend_pct": calc_trend(lines_values),
        },
        "averages": {
            "avg_prs_per_period": round(statistics.mean(pr_values), 1) if pr_values else 0,
            "avg_reviews_per_period": round(statistics.mean(review_values), 1) if review_values else 0,
        },
    }

    if warnings:
        result["warnings"] = warnings

    return result


async def handle_get_contribution_distribution(
    config: Config,
    github_username: str,
    days: int = 90,
    start_date: str | None = None,
    end_date: str | None = None,
    max_prs: int = 25,
) -> dict:
    """Get distribution of contributions by repo, file type, and work area.

    Args:
        config: Application configuration.
        github_username: GitHub username.
        days: Number of days to look back.
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.
        max_prs: Maximum number of PRs to analyze for file distribution.

    Returns:
        Dict containing contribution distribution data.
    """
    if error := _validate_team_member(config, github_username):
        return error

    member = config.team_members[github_username]

    date_range = _parse_and_validate_date_range(days, start_date, end_date)
    if isinstance(date_range, dict):
        return date_range
    since, until = date_range

    by_repo: dict[str, int] = defaultdict(int)
    by_area: dict[str, int] = defaultdict(int)
    by_file_type: dict[str, int] = defaultdict(int)
    files_touched: list[dict] = []
    warnings = []

    with GitHubClient(config.github) as client:
        try:
            prs = client.search_prs(github_username, since, until)
        except Exception as e:
            logger.error(f"GitHub PR search failed: {e}")
            return {"error": f"Failed to fetch GitHub PRs: {str(e)}"}

        # Filter to merged PRs
        merged_prs = [pr for pr in prs if pr.merged]
        total_merged = len(merged_prs)

        # Count by repo for all merged PRs
        for pr in merged_prs:
            by_repo[pr.repo] += 1

        # Limit file analysis to max_prs and fetch in parallel
        prs_to_analyze = merged_prs[:max_prs]
        files_map = client.get_pr_files_batch(prs_to_analyze)
        prs_analyzed_for_files = len(files_map)

        for pr in prs_to_analyze:
            files = files_map.get((pr.repo, pr.number), [])
            for file_info in files:
                filename = file_info.get("filename", "")
                if not filename:
                    continue

                area = infer_area_from_path(filename)
                ext = get_file_extension(filename)

                by_area[area] += 1
                if ext:
                    by_file_type[ext] += 1

                files_touched.append({
                    "path": filename,
                    "repo": pr.repo,
                    "area": area,
                    "pr_number": pr.number,
                })

    # Sort distributions by count descending
    sorted_by_repo = dict(sorted(by_repo.items(), key=lambda x: x[1], reverse=True))
    sorted_by_area = dict(sorted(by_area.items(), key=lambda x: x[1], reverse=True))
    sorted_by_file_type = dict(sorted(by_file_type.items(), key=lambda x: x[1], reverse=True)[:15])

    result = {
        "member_name": member.name,
        "github_username": github_username,
        "start_date": since.strftime("%Y-%m-%d"),
        "end_date": until.strftime("%Y-%m-%d"),
        "total_prs_merged": total_merged,
        "prs_analyzed_for_files": prs_analyzed_for_files,
        "distribution": {
            "by_repo": sorted_by_repo,
            "by_area": sorted_by_area,
            "by_file_type": sorted_by_file_type,
        },
        "summary": {
            "repos_touched": len(by_repo),
            "areas_touched": len(by_area),
            "primary_area": max(by_area.items(), key=lambda x: x[1])[0] if by_area else None,
            "primary_repo": max(by_repo.items(), key=lambda x: x[1])[0] if by_repo else None,
        },
        "files_touched_sample": files_touched[:50],  # Limit sample size
    }

    if total_merged > max_prs:
        result["note"] = f"File distribution based on {prs_analyzed_for_files} of {total_merged} PRs (limited by max_prs)"

    if warnings:
        result["warnings"] = warnings

    return result


async def handle_get_competency_analysis(
    config: Config,
    github_username: str,
    days: int = 90,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """Analyze contributions to map to EGF competencies.

    Args:
        config: Application configuration.
        github_username: GitHub username.
        days: Number of days to look back.
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.

    Returns:
        Dict containing competency analysis with evidence and scores.
    """
    if error := _validate_team_member(config, github_username):
        return error

    member = config.team_members[github_username]

    date_range = _parse_and_validate_date_range(days, start_date, end_date)
    if isinstance(date_range, dict):
        return date_range
    since, until = date_range

    # Gather contribution data
    prs_merged = []
    reviews_given = []
    distribution = {"by_repo": {}, "by_area": {}}
    review_turnaround = None
    warnings = []

    with GitHubClient(config.github) as client:
        try:
            prs = client.search_prs(github_username, since, until)
            by_repo: dict[str, int] = defaultdict(int)
            by_area: dict[str, int] = defaultdict(int)

            # Filter to merged PRs and fetch stats/files in parallel
            merged_prs = [pr for pr in prs if pr.merged]
            stats_map = client.get_pr_stats_batch(merged_prs)
            files_map = client.get_pr_files_batch(merged_prs)

            for pr in merged_prs:
                stats = stats_map.get((pr.repo, pr.number), {"additions": 0, "deletions": 0})
                pr_data = {
                    "number": pr.number,
                    "title": pr.title,
                    "repo": pr.repo,
                    "url": pr.url,
                    "additions": stats.get("additions", 0),
                    "deletions": stats.get("deletions", 0),
                }

                prs_merged.append(pr_data)
                by_repo[pr.repo] += 1

                # Process files for area distribution
                files = files_map.get((pr.repo, pr.number), [])
                for file_info in files:
                    filename = file_info.get("filename", "")
                    if filename:
                        area = infer_area_from_path(filename)
                        by_area[area] += 1

            distribution = {"by_repo": dict(by_repo), "by_area": dict(by_area)}

        except Exception as e:
            logger.error(f"GitHub PR search failed: {e}")
            return {"error": f"Failed to fetch GitHub PRs: {str(e)}"}

        try:
            reviews = client.get_reviews_by_user(github_username, since, until)
            for review in reviews:
                reviews_given.append({
                    "pr_title": review.pr_title,
                    "repo": review.repo,
                    "state": review.state,
                    "url": review.url,
                })
        except Exception as e:
            logger.warning(f"Failed to fetch reviews: {e}")
            warnings.append(f"Failed to fetch reviews: {str(e)}")

        # Get review turnaround data
        try:
            turnarounds = _calculate_review_turnarounds(
                client, config.github.org, github_username, since, until
            )
            if turnarounds:
                valid_hours = [r["turnaround_hours"] for r in turnarounds if r.get("turnaround_hours") is not None]
                if valid_hours:
                    review_turnaround = {
                        "avg_hours": statistics.mean(valid_hours),
                        "median_hours": statistics.median(valid_hours),
                    }
        except Exception as e:
            logger.warning(f"Failed to calculate review turnarounds: {e}")

    # Run competency analysis
    analysis = analyze_contributions_for_competencies(
        prs_merged=prs_merged,
        reviews_given=reviews_given,
        distribution=distribution,
        review_turnaround=review_turnaround,
    )

    summary = get_competency_summary(analysis)

    result = {
        "member_name": member.name,
        "github_username": github_username,
        "start_date": since.strftime("%Y-%m-%d"),
        "end_date": until.strftime("%Y-%m-%d"),
        "contribution_summary": {
            "prs_merged": len(prs_merged),
            "reviews_given": len(reviews_given),
        },
        "competency_analysis": analysis,
        "summary": summary,
    }

    if warnings:
        result["warnings"] = warnings

    return result
