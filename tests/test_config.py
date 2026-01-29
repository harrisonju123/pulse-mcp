"""Unit tests for config loading and validation."""

import pytest

from ic_tracker.config import ConfigError, _validate_project_key, _validate_team_id, _parse_config


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


class TestTeamIdValidation:
    """Test team ID validation."""

    def test_valid_team_ids(self):
        assert _validate_team_id("platform") is True
        assert _validate_team_id("product-team") is True
        assert _validate_team_id("team_alpha") is True
        assert _validate_team_id("team1") is True
        assert _validate_team_id("a") is True

    def test_invalid_team_ids(self):
        assert _validate_team_id("Platform") is False  # uppercase
        assert _validate_team_id("123team") is False  # starts with number
        assert _validate_team_id("-team") is False  # starts with hyphen
        assert _validate_team_id("_team") is False  # starts with underscore
        assert _validate_team_id("") is False  # empty
        assert _validate_team_id("team name") is False  # contains space


class TestMultiTeamConfig:
    """Test multi-team configuration parsing."""

    def test_parse_new_teams_format(self):
        data = {
            "github": {"token": "gh-token", "org": "testorg"},
            "teams": {
                "platform": {
                    "name": "Platform Team",
                    "members": {
                        "alice": {"atlassian_account_id": "acc-1", "name": "Alice Smith"},
                        "bob": {"atlassian_account_id": "acc-2", "name": "Bob Jones"},
                    },
                },
                "product": {
                    "name": "Product Team",
                    "members": {
                        "carol": {"atlassian_account_id": "acc-3", "name": "Carol Williams"},
                    },
                },
            },
        }

        config = _parse_config(data)

        assert len(config.teams) == 2
        assert "platform" in config.teams
        assert "product" in config.teams
        assert config.teams["platform"].name == "Platform Team"
        assert len(config.teams["platform"].members) == 2
        assert config.teams["product"].name == "Product Team"
        assert len(config.teams["product"].members) == 1

    def test_parse_legacy_team_members_format(self):
        data = {
            "github": {"token": "gh-token", "org": "testorg"},
            "team_members": {
                "user1": {"atlassian_account_id": "acc-1", "name": "User One"},
                "user2": {"atlassian_account_id": "acc-2", "name": "User Two"},
            },
        }

        config = _parse_config(data)

        # Legacy format should be converted to single "default" team
        assert len(config.teams) == 1
        assert "default" in config.teams
        assert config.teams["default"].name == "Default Team"
        assert len(config.teams["default"].members) == 2

    def test_team_members_computed_property(self):
        data = {
            "github": {"token": "gh-token", "org": "testorg"},
            "teams": {
                "platform": {
                    "name": "Platform Team",
                    "members": {
                        "alice": {"atlassian_account_id": "acc-1", "name": "Alice Smith"},
                    },
                },
                "product": {
                    "name": "Product Team",
                    "members": {
                        "bob": {"atlassian_account_id": "acc-2", "name": "Bob Jones"},
                    },
                },
            },
        }

        config = _parse_config(data)

        # team_members property should flatten all teams
        assert len(config.team_members) == 2
        assert "alice" in config.team_members
        assert "bob" in config.team_members

    def test_cannot_have_both_teams_and_team_members(self):
        data = {
            "github": {"token": "gh-token", "org": "testorg"},
            "teams": {
                "platform": {
                    "name": "Platform Team",
                    "members": {"alice": {"atlassian_account_id": "acc-1", "name": "Alice"}},
                },
            },
            "team_members": {
                "bob": {"atlassian_account_id": "acc-2", "name": "Bob"},
            },
        }

        with pytest.raises(ConfigError, match="Cannot have both 'teams' and 'team_members'"):
            _parse_config(data)

    def test_must_have_teams_or_team_members(self):
        data = {
            "github": {"token": "gh-token", "org": "testorg"},
        }

        with pytest.raises(ConfigError, match="must have either 'teams' or 'team_members'"):
            _parse_config(data)

    def test_empty_teams_rejected(self):
        data = {
            "github": {"token": "gh-token", "org": "testorg"},
            "teams": {},
        }

        with pytest.raises(ConfigError, match="teams cannot be empty"):
            _parse_config(data)

    def test_empty_team_members_in_team_rejected(self):
        data = {
            "github": {"token": "gh-token", "org": "testorg"},
            "teams": {
                "platform": {
                    "name": "Platform Team",
                    "members": {},
                },
            },
        }

        with pytest.raises(ConfigError, match="members cannot be empty"):
            _parse_config(data)

    def test_invalid_team_id_rejected(self):
        data = {
            "github": {"token": "gh-token", "org": "testorg"},
            "teams": {
                "Platform-Team": {  # Invalid: uppercase
                    "name": "Platform Team",
                    "members": {"alice": {"atlassian_account_id": "acc-1", "name": "Alice"}},
                },
            },
        }

        with pytest.raises(ConfigError, match="Invalid team ID"):
            _parse_config(data)

    def test_duplicate_username_across_teams_rejected(self):
        data = {
            "github": {"token": "gh-token", "org": "testorg"},
            "teams": {
                "platform": {
                    "name": "Platform Team",
                    "members": {"alice": {"atlassian_account_id": "acc-1", "name": "Alice Smith"}},
                },
                "product": {
                    "name": "Product Team",
                    "members": {"alice": {"atlassian_account_id": "acc-2", "name": "Alice Jones"}},
                },
            },
        }

        with pytest.raises(ConfigError, match="Duplicate GitHub username 'alice'"):
            _parse_config(data)

    def test_team_missing_name_rejected(self):
        data = {
            "github": {"token": "gh-token", "org": "testorg"},
            "teams": {
                "platform": {
                    "members": {"alice": {"atlassian_account_id": "acc-1", "name": "Alice"}},
                },
            },
        }

        with pytest.raises(ConfigError, match="Missing required keys"):
            _parse_config(data)

    def test_team_missing_members_rejected(self):
        data = {
            "github": {"token": "gh-token", "org": "testorg"},
            "teams": {
                "platform": {
                    "name": "Platform Team",
                },
            },
        }

        with pytest.raises(ConfigError, match="Missing required keys"):
            _parse_config(data)
