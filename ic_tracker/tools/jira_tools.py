"""MCP tools for Jira planning features."""

import logging

from mcp.types import Tool

from ..clients.jira_client import JiraClient
from ..models import Config, JiraIssue

logger = logging.getLogger(__name__)


def get_jira_tools() -> list[Tool]:
    """Return list of Jira-related MCP tools."""
    return [
        Tool(
            name="get_initiative_roadmap",
            description=(
                "Get a roadmap view of an initiative including all epics with progress, "
                "status, assignees, and deadlines. Shows story points completed/total "
                "and issue counts for each epic."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "initiative_key": {
                        "type": "string",
                        "description": "Jira issue key of the initiative (e.g., 'PROJ-100')",
                    },
                },
                "required": ["initiative_key"],
            },
        ),
        Tool(
            name="get_team_bandwidth",
            description=(
                "Show how team members' work is distributed across epics and initiatives. "
                "Returns open story points and issues per team member, with breakdown by epic."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "github_username": {
                        "type": "string",
                        "description": "Optional: Filter to a specific team member by GitHub username",
                    },
                    "initiative_key": {
                        "type": "string",
                        "description": "Optional: Filter to issues under a specific initiative",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="search_jira_issues",
            description=(
                "Flexible JQL search for queries not covered by other tools. "
                "Returns matching issues with key fields."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "jql": {
                        "type": "string",
                        "description": "JQL query string (e.g., 'project = PROJ AND status = \"In Progress\"')",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 50, max: 100)",
                        "default": 50,
                        "minimum": 1,
                        "maximum": 100,
                    },
                },
                "required": ["jql"],
            },
        ),
        Tool(
            name="update_jira_issue",
            description=(
                "Update a Jira issue's summary (title) and/or description. "
                "Supports basic markdown formatting in description: headings (##), "
                "bullet lists (-), checkboxes (- [ ]), code blocks (```), "
                "bold (**text**), and inline code (`code`)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {
                        "type": "string",
                        "description": "Jira issue key (e.g., 'PROJ-123')",
                    },
                    "summary": {
                        "type": "string",
                        "description": "New summary/title for the issue (optional)",
                    },
                    "description": {
                        "type": "string",
                        "description": "New description for the issue in markdown format (optional)",
                    },
                },
                "required": ["issue_key"],
            },
        ),
    ]


async def handle_get_initiative_roadmap(config: Config, initiative_key: str) -> dict:
    """Fetch initiative roadmap with epic progress."""
    if config.jira is None:
        return {"error": "Jira is not configured. Add a 'jira' section to your config file."}

    with JiraClient(config.jira) as client:
        try:
            initiative = client.get_issue(initiative_key)
        except ValueError as e:
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Failed to fetch initiative {initiative_key}: {e}")
            return {"error": f"Failed to fetch initiative: {e}"}

        try:
            epics = client.get_initiative_epics(initiative_key)
        except Exception as e:
            logger.error(f"Failed to fetch epics for {initiative_key}: {e}")
            return {"error": f"Failed to fetch epics: {e}"}

        # Batch fetch all children in a single query to avoid N+1
        children_fetch_failed = False
        try:
            epic_keys = [e.key for e in epics]
            children_by_epic = client.get_children_for_epics(epic_keys)
        except Exception as e:
            logger.warning(f"Failed to batch fetch children: {e}")
            children_by_epic = {k: [] for k in epic_keys}
            children_fetch_failed = True

        epic_progress_list = []
        total_points = 0.0
        total_completed_points = 0.0
        total_issues = 0
        total_completed_issues = 0

        for epic in epics:
            children = children_by_epic.get(epic.key, [])
            progress = _calculate_epic_progress(epic, children)
            epic_progress_list.append(progress)

            total_points += progress["total_story_points"]
            total_completed_points += progress["completed_story_points"]
            total_issues += progress["total_issues"]
            total_completed_issues += progress["completed_issues"]

        overall_progress_pct = (
            round(total_completed_points / total_points * 100, 1) if total_points > 0 else 0
        )

        result = {
            "initiative": _issue_to_dict(initiative),
            "epics": epic_progress_list,
            "summary": {
                "total_epics": len(epics),
                "total_story_points": total_points,
                "completed_story_points": total_completed_points,
                "progress_percentage": overall_progress_pct,
                "total_issues": total_issues,
                "completed_issues": total_completed_issues,
            },
        }

        if children_fetch_failed:
            result["warning"] = "Failed to fetch epic children; progress data may be incomplete"

        return result


async def handle_get_team_bandwidth(
    config: Config,
    github_username: str | None = None,
    initiative_key: str | None = None,
) -> dict:
    """Fetch team bandwidth allocation."""
    if config.jira is None:
        return {"error": "Jira is not configured. Add a 'jira' section to your config file."}

    # Determine which team members to include
    if github_username:
        if github_username not in config.team_members:
            return {
                "error": f"Unknown team member: {github_username}. "
                f"Available: {', '.join(config.team_members.keys())}"
            }
        members_to_check = {github_username: config.team_members[github_username]}
    else:
        members_to_check = config.team_members

    with JiraClient(config.jira) as client:
        # If filtering by initiative, get all issues under it first
        initiative_issues: list[JiraIssue] | None = None

        if initiative_key:
            try:
                epics = client.get_initiative_epics(initiative_key)
                epic_keys = [e.key for e in epics]
                # Batch fetch all children
                children_by_epic = client.get_children_for_epics(epic_keys)
                all_children = [
                    issue for children in children_by_epic.values() for issue in children
                ]
                initiative_issues = epics + all_children
            except ValueError as e:
                return {"error": str(e)}
            except Exception as e:
                logger.error(f"Failed to fetch initiative {initiative_key}: {e}")
                return {"error": f"Failed to fetch initiative: {e}"}

        team_allocations = []
        total_team_points = 0.0
        total_team_issues = 0

        for gh_username, member in members_to_check.items():
            account_id = member.atlassian_account_id

            if initiative_issues is not None:
                # Filter to issues assigned to this user
                user_issues = [
                    i for i in initiative_issues
                    if i.assignee_account_id == account_id and i.status_category != "Done"
                ]
            else:
                try:
                    user_issues = client.get_user_open_issues(account_id)
                except Exception as e:
                    logger.error(f"Failed to fetch issues for {gh_username}: {e}")
                    continue

            allocation = _calculate_allocation(user_issues, gh_username, member.name, account_id)
            team_allocations.append(allocation)
            total_team_points += allocation["total_open_story_points"]
            total_team_issues += allocation["total_open_issues"]

    avg_points = round(total_team_points / len(team_allocations), 1) if team_allocations else 0

    return {
        "team_members": team_allocations,
        "summary": {
            "total_members": len(team_allocations),
            "total_open_story_points": total_team_points,
            "total_open_issues": total_team_issues,
            "average_points_per_member": avg_points,
        },
    }


async def handle_search_jira_issues(
    config: Config,
    jql: str,
    max_results: int = 50,
) -> dict:
    """Execute a JQL search."""
    if config.jira is None:
        return {"error": "Jira is not configured. Add a 'jira' section to your config file."}

    max_results = min(max_results, 100)

    with JiraClient(config.jira) as client:
        try:
            issues = client.search_issues(jql, max_results=max_results)
        except Exception as e:
            logger.error(f"JQL search failed: {e}")
            return {"error": f"JQL search failed: {e}"}

    return {
        "jql": jql,
        "total_results": len(issues),
        "issues": [_issue_to_dict(i) for i in issues],
    }


async def handle_update_jira_issue(
    config: Config,
    issue_key: str,
    summary: str | None = None,
    description: str | None = None,
) -> dict:
    """Update a Jira issue's summary and/or description."""
    if config.jira is None:
        return {"error": "Jira is not configured. Add a 'jira' section to your config file."}

    if summary is None and description is None:
        return {"error": "At least one of 'summary' or 'description' must be provided"}

    with JiraClient(config.jira) as client:
        try:
            client.update_issue(issue_key, summary=summary, description=description)
        except ValueError as e:
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Failed to update issue {issue_key}: {e}")
            return {"error": f"Failed to update issue: {e}"}

    # Fetch the updated issue to return current state
    try:
        updated_issue = client.get_issue(issue_key)
        return {
            "success": True,
            "message": f"Successfully updated {issue_key}",
            "issue": _issue_to_dict(updated_issue),
        }
    except Exception:
        # Update succeeded but fetch failed - still report success
        return {
            "success": True,
            "message": f"Successfully updated {issue_key}",
            "issue_key": issue_key,
        }


def _calculate_epic_progress(epic: JiraIssue, children: list[JiraIssue]) -> dict:
    """Calculate progress metrics for an epic."""
    total_points = 0.0
    completed_points = 0.0
    total_issues = len(children)
    completed_issues = 0
    in_progress_issues = 0
    assignee_points: dict[str, dict] = {}  # account_id -> {name, points}

    for issue in children:
        points = issue.story_points or 0
        total_points += points

        if issue.status_category == "Done":
            completed_points += points
            completed_issues += 1
        elif issue.status_category == "In Progress":
            in_progress_issues += 1

        # Track assignee allocation (only for non-done issues)
        if issue.assignee_account_id and issue.status_category != "Done":
            if issue.assignee_account_id not in assignee_points:
                assignee_points[issue.assignee_account_id] = {
                    "account_id": issue.assignee_account_id,
                    "name": issue.assignee_name or "Unknown",
                    "story_points": 0,
                    "issue_count": 0,
                }
            assignee_points[issue.assignee_account_id]["story_points"] += points
            assignee_points[issue.assignee_account_id]["issue_count"] += 1

    progress_pct = round(completed_points / total_points * 100, 1) if total_points > 0 else 0

    return {
        "epic": _issue_to_dict(epic),
        "total_story_points": total_points,
        "completed_story_points": completed_points,
        "progress_percentage": progress_pct,
        "total_issues": total_issues,
        "completed_issues": completed_issues,
        "in_progress_issues": in_progress_issues,
        "assignees": list(assignee_points.values()),
    }


def _calculate_allocation(
    issues: list[JiraIssue],
    github_username: str,
    name: str,
    account_id: str,
) -> dict:
    """Calculate allocation for a team member."""
    total_points = 0.0
    epic_allocation: dict[str, dict] = {}

    for issue in issues:
        points = issue.story_points or 0
        total_points += points

        # Group by epic (parent_key or epic_link for stories, or issue itself if it's an epic)
        epic_key = issue.parent_key or issue.epic_link or issue.key
        if epic_key not in epic_allocation:
            epic_allocation[epic_key] = {
                "epic_key": epic_key,
                "story_points": 0,
                "issue_count": 0,
            }
        epic_allocation[epic_key]["story_points"] += points
        epic_allocation[epic_key]["issue_count"] += 1

    return {
        "github_username": github_username,
        "name": name,
        "account_id": account_id,
        "total_open_story_points": total_points,
        "total_open_issues": len(issues),
        "allocation_by_epic": list(epic_allocation.values()),
    }


def _issue_to_dict(issue: JiraIssue) -> dict:
    """Convert JiraIssue to dictionary for JSON serialization."""
    return {
        "key": issue.key,
        "summary": issue.summary,
        "issue_type": issue.issue_type,
        "status": issue.status,
        "status_category": issue.status_category,
        "assignee": issue.assignee_name,
        "story_points": issue.story_points,
        "due_date": issue.due_date.isoformat() if issue.due_date else None,
        "url": issue.url,
    }
