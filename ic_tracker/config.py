"""Configuration loading for IC Tracker."""

import json
import os
import re
from pathlib import Path

from .models import Config, ConfluenceConfig, GitHubConfig, JiraConfig, TeamMember

# Pattern for valid Jira project keys
PROJECT_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9]*$")


class ConfigError(Exception):
    """Raised when configuration is invalid or missing."""
    pass


def _validate_project_key(key: str) -> bool:
    """Check if a string is a valid Jira project key."""
    return bool(PROJECT_KEY_PATTERN.match(key))


def load_config(config_path: str | None = None) -> Config:
    """Load configuration from JSON file.

    Args:
        config_path: Path to config file. If None, uses IC_TRACKER_CONFIG env var.

    Returns:
        Validated Config object.

    Raises:
        ConfigError: If config file is missing or invalid.
    """
    if config_path is None:
        config_path = os.environ.get("IC_TRACKER_CONFIG")

    if not config_path:
        raise ConfigError(
            "No config path provided. Set IC_TRACKER_CONFIG environment variable "
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


def _parse_config(data: dict) -> Config:
    """Parse and validate configuration data."""
    _validate_required_keys(data, ["github", "team_members"], "config")

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

    team_members = {}
    if not data["team_members"]:
        raise ConfigError("team_members cannot be empty")

    for github_username, member_data in data["team_members"].items():
        _validate_required_keys(
            member_data,
            ["atlassian_account_id", "name"],
            f"team_members.{github_username}"
        )
        team_members[github_username] = TeamMember(
            github_username=github_username,
            atlassian_account_id=member_data["atlassian_account_id"],
            name=member_data["name"],
        )

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

    return Config(
        github=github_config,
        team_members=team_members,
        confluence=confluence_config,
        jira=jira_config,
    )


def _validate_required_keys(data: dict, keys: list[str], section: str) -> None:
    """Validate that all required keys are present."""
    missing = [k for k in keys if k not in data]
    if missing:
        raise ConfigError(
            f"Missing required keys in {section}: {', '.join(missing)}"
        )
