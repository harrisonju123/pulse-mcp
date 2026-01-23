"""Unit tests for config loading and validation."""

import pytest

from ic_tracker.config import ConfigError, _validate_project_key, _parse_config


class TestProjectKeyValidation:
    """Test Jira project key validation."""

    def test_valid_project_keys(self):
        assert _validate_project_key("PROJ") is True
        assert _validate_project_key("AB") is True
        assert _validate_project_key("INFRA") is True
        assert _validate_project_key("TEST123") is True
        assert _validate_project_key("A1B2C3") is True

    def test_invalid_project_keys(self):
        assert _validate_project_key("proj") is False  # lowercase
        assert _validate_project_key("123") is False  # starts with number
        assert _validate_project_key("PROJ-123") is False  # contains hyphen
        assert _validate_project_key("") is False  # empty
        assert _validate_project_key("PROJ 123") is False  # contains space
        assert _validate_project_key('PROJ"') is False  # contains quote


class TestJiraConfigParsing:
    """Test Jira config parsing with validation."""

    def test_valid_jira_config(self):
        data = {
            "github": {"token": "gh-token", "org": "testorg"},
            "team_members": {
                "user1": {"atlassian_account_id": "acc-1", "name": "User One"},
            },
            "jira": {
                "base_url": "https://test.atlassian.net",
                "email": "test@example.com",
                "api_token": "jira-token",
                "project_keys": ["PROJ", "INFRA"],
                "story_point_field": "customfield_10016",
            },
        }

        config = _parse_config(data)

        assert config.jira is not None
        assert config.jira.project_keys == ["PROJ", "INFRA"]

    def test_invalid_project_key_rejected(self):
        data = {
            "github": {"token": "gh-token", "org": "testorg"},
            "team_members": {
                "user1": {"atlassian_account_id": "acc-1", "name": "User One"},
            },
            "jira": {
                "base_url": "https://test.atlassian.net",
                "email": "test@example.com",
                "api_token": "jira-token",
                "project_keys": ["PROJ", "invalid-key"],
                "story_point_field": "customfield_10016",
            },
        }

        with pytest.raises(ConfigError, match="Invalid Jira project key"):
            _parse_config(data)

    def test_injection_attempt_in_project_key_rejected(self):
        data = {
            "github": {"token": "gh-token", "org": "testorg"},
            "team_members": {
                "user1": {"atlassian_account_id": "acc-1", "name": "User One"},
            },
            "jira": {
                "base_url": "https://test.atlassian.net",
                "email": "test@example.com",
                "api_token": "jira-token",
                "project_keys": ['PROJ" OR 1=1 --'],
                "story_point_field": "customfield_10016",
            },
        }

        with pytest.raises(ConfigError, match="Invalid Jira project key"):
            _parse_config(data)
