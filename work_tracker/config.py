"""Configuration loading for Work Tracker."""

import json
import os
import re
from pathlib import Path

from .models import Config, ConfluenceConfig, GitHubConfig, JiraConfig, Team, TeamMember

# Pattern for valid Jira project keys
PROJECT_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9]*$")

# Pattern for valid team IDs (lowercase alphanumeric with hyphens/underscores)
TEAM_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")


class ConfigError(Exception):
    pass


def _validate_project_key(key: str) -> bool:
    return bool(PROJECT_KEY_PATTERN.match(key))


def load_config(config_path: str | None = None) -> Config:
    if config_path is None:
        # Check new env var first, fall back to old one for backward compatibility
        config_path = os.environ.get("WORK_TRACKER_CONFIG") or os.environ.get("IC_TRACKER_CONFIG")

    if not config_path:
        raise ConfigError(
            "No config path provided. Set WORK_TRACKER_CONFIG environment variable "
            "or pass config_path argument."
        )

    path = Path(config_path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in config file: {e}")

    return _parse_config(data)


def _validate_team_id(team_id: str) -> bool:
    return bool(TEAM_ID_PATTERN.match(team_id))


def _parse_team_members(members_data: dict, section_name: str) -> dict[str, TeamMember]:
    members = {}
    for github_username, member_data in members_data.items():
        _validate_required_keys(
            member_data,
            ["atlassian_account_id", "name"],
            f"{section_name}.{github_username}"
        )
        members[github_username] = TeamMember(
            github_username=github_username,
            atlassian_account_id=member_data["atlassian_account_id"],
            name=member_data["name"],
        )
    return members


def _parse_teams(data: dict) -> dict[str, Team]:
    """Parse teams from config data.

    Handles both new teams format and legacy team_members format.

    Args:
        data: Full config data dict.

    Returns:
        Dict of team_id -> Team.

    Raises:
        ConfigError: If config is invalid.
    """
    has_teams = "teams" in data
    has_team_members = "team_members" in data

    # Validate mutually exclusive
    if has_teams and has_team_members:
        raise ConfigError(
            "Cannot have both 'teams' and 'team_members' in config. "
            "Use 'teams' for multi-team setup or 'team_members' for single team."
        )

    if not has_teams and not has_team_members:
        raise ConfigError("Config must have either 'teams' or 'team_members'")

    teams = {}

    if has_teams:
        # New multi-team format
        teams_data = data["teams"]
        if not teams_data:
            raise ConfigError("teams cannot be empty")

        all_usernames = set()
        for team_id, team_data in teams_data.items():
            # Validate team ID format
            if not _validate_team_id(team_id):
                raise ConfigError(
                    f"Invalid team ID: '{team_id}'. "
                    "Team IDs must be lowercase, start with a letter, and contain only letters, numbers, hyphens, and underscores."
                )

            _validate_required_keys(team_data, ["name", "members"], f"teams.{team_id}")

            if not team_data["members"]:
                raise ConfigError(f"teams.{team_id}.members cannot be empty")

            # Check for duplicate usernames across teams
            for username in team_data["members"].keys():
                if username in all_usernames:
                    raise ConfigError(
                        f"Duplicate GitHub username '{username}' found across teams. "
                        "Each username can only appear in one team."
                    )
                all_usernames.add(username)

            members = _parse_team_members(
                team_data["members"],
                f"teams.{team_id}.members"
            )

            teams[team_id] = Team(
                id=team_id,
                name=team_data["name"],
                members=members,
            )
    else:
        # Legacy team_members format - convert to single "default" team
        if not data["team_members"]:
            raise ConfigError("team_members cannot be empty")

        members = _parse_team_members(data["team_members"], "team_members")

        teams["default"] = Team(
            id="default",
            name="Default Team",
            members=members,
        )

    return teams


def _parse_config(data: dict) -> Config:
    _validate_required_keys(data, ["github"], "config")

    github_data = data["github"]
    _validate_required_keys(github_data, ["token", "org"], "github")
    # repos is optional - currently searches all repos in the org via search API
    repos = github_data.get("repos", [])

    github_config = GitHubConfig(
        token=github_data["token"],
        org=github_data["org"],
        repos=repos,
    )

    confluence_config = None
    if "confluence" in data:
        confluence_data = data["confluence"]
        _validate_required_keys(
            confluence_data,
            ["base_url", "email", "api_token", "space_keys"],
            "confluence"
        )
        if not confluence_data["space_keys"]:
            raise ConfigError("confluence.space_keys cannot be empty")

        confluence_config = ConfluenceConfig(
            base_url=confluence_data["base_url"].strip().rstrip("/"),
            email=confluence_data["email"],
            api_token=confluence_data["api_token"],
            space_keys=confluence_data["space_keys"],
        )

    # Parse teams (handles both new and legacy formats)
    teams = _parse_teams(data)

    jira_config = None
    if "jira" in data:
        jira_data = data["jira"]
        _validate_required_keys(
            jira_data,
            ["base_url", "email", "api_token", "project_keys", "story_point_field"],
            "jira"
        )
        if not jira_data["project_keys"]:
            raise ConfigError("jira.project_keys cannot be empty")

        # Validate project keys to prevent JQL injection
        invalid_keys = [k for k in jira_data["project_keys"] if not _validate_project_key(k)]
        if invalid_keys:
            raise ConfigError(
                f"Invalid Jira project key(s): {', '.join(invalid_keys)}. "
                "Project keys must be uppercase letters and numbers, starting with a letter."
            )

        jira_config = JiraConfig(
            base_url=jira_data["base_url"].strip().rstrip("/"),
            email=jira_data["email"],
            api_token=jira_data["api_token"],
            project_keys=jira_data["project_keys"],
            story_point_field=jira_data["story_point_field"],
            epic_link_field=jira_data.get("epic_link_field", "customfield_10014"),
        )

    # Parse self username (optional)
    self_username = data.get("self")
    if self_username:
        # Get all usernames from all teams
        all_usernames = set()
        for team in teams.values():
            all_usernames.update(team.members.keys())

        if self_username not in all_usernames:
            raise ConfigError(
                f"'self' username '{self_username}' is not a configured team member. "
                f"Available: {', '.join(sorted(all_usernames))}"
            )

    return Config(
        github=github_config,
        teams=teams,
        confluence=confluence_config,
        jira=jira_config,
        self_username=self_username,
    )


def _validate_required_keys(data: dict, keys: list[str], section: str) -> None:
    missing = [k for k in keys if k not in data]
    if missing:
        raise ConfigError(
            f"Missing required keys in {section}: {', '.join(missing)}"
        )
