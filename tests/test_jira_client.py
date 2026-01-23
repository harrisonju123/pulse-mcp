"""Unit tests for Jira client."""

import pytest
import responses
from responses import matchers

from ic_tracker.clients.jira_client import JiraClient


class TestJiraClientValidation:
    """Test input validation for JQL injection prevention."""

    def test_valid_issue_key(self, jira_config):
        from ic_tracker.clients.jira_client import _validate_issue_key
        # These should not raise
        _validate_issue_key("PROJ-123")
        _validate_issue_key("AB-1")
        _validate_issue_key("TEST123-99999")

    def test_invalid_issue_key_injection_attempt(self, jira_config):
        from ic_tracker.clients.jira_client import _validate_issue_key
        import pytest

        # These should raise ValueError
        with pytest.raises(ValueError, match="Invalid Jira issue key"):
            _validate_issue_key('PROJ-1" OR 1=1 --')

        with pytest.raises(ValueError, match="Invalid Jira issue key"):
            _validate_issue_key("PROJ-1; DROP TABLE issues")

        with pytest.raises(ValueError, match="Invalid Jira issue key"):
            _validate_issue_key("")

        with pytest.raises(ValueError, match="Invalid Jira issue key"):
            _validate_issue_key("invalid")

        with pytest.raises(ValueError, match="Invalid Jira issue key"):
            _validate_issue_key("123-ABC")

    def test_escape_jql_string(self, jira_config):
        from ic_tracker.clients.jira_client import _escape_jql_string

        assert _escape_jql_string('normal') == 'normal'
        assert _escape_jql_string('with"quote') == 'with\\"quote'
        assert _escape_jql_string('with\\backslash') == 'with\\\\backslash'
        assert _escape_jql_string('both"and\\') == 'both\\"and\\\\'


class TestJiraClientParsing:
    """Test issue parsing logic."""

    def test_parse_issue_basic(self, jira_config, sample_jira_issue):
        client = JiraClient(jira_config)
        issue = client._parse_issue(sample_jira_issue)

        assert issue.key == "PROJ-123"
        assert issue.summary == "Test Issue"
        assert issue.issue_type == "Story"
        assert issue.status == "In Progress"
        assert issue.status_category == "In Progress"
        assert issue.assignee_account_id == "account-123"
        assert issue.assignee_name == "Test User"
        assert issue.story_points == 5.0
        assert issue.parent_key == "PROJ-100"
        assert issue.labels == ["backend"]
        assert issue.url == "https://test.atlassian.net/browse/PROJ-123"

    def test_parse_issue_no_assignee(self, jira_config, sample_jira_issue):
        sample_jira_issue["fields"]["assignee"] = None
        client = JiraClient(jira_config)
        issue = client._parse_issue(sample_jira_issue)

        assert issue.assignee_account_id is None
        assert issue.assignee_name is None

    def test_parse_issue_no_story_points(self, jira_config, sample_jira_issue):
        sample_jira_issue["fields"]["customfield_10016"] = None
        client = JiraClient(jira_config)
        issue = client._parse_issue(sample_jira_issue)

        assert issue.story_points is None

    def test_parse_issue_no_parent(self, jira_config, sample_jira_issue):
        sample_jira_issue["fields"]["parent"] = None
        client = JiraClient(jira_config)
        issue = client._parse_issue(sample_jira_issue)

        assert issue.parent_key is None

    def test_parse_issue_missing_key_raises(self, jira_config):
        client = JiraClient(jira_config)
        with pytest.raises(ValueError, match="missing required 'key' field"):
            client._parse_issue({"fields": {}})


class TestJiraClientAPI:
    """Test API calls with mocked responses."""

    @responses.activate
    def test_get_issue(self, jira_config, sample_jira_issue):
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/issue/PROJ-123",
            json=sample_jira_issue,
            status=200,
        )

        with JiraClient(jira_config) as client:
            issue = client.get_issue("PROJ-123")

        assert issue.key == "PROJ-123"
        assert issue.summary == "Test Issue"

    @responses.activate
    def test_search_issues(self, jira_config, sample_jira_issue):
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/search/jql",
            json={"issues": [sample_jira_issue], "isLast": True},
            status=200,
        )

        with JiraClient(jira_config) as client:
            issues = client.search_issues("project = PROJ")

        assert len(issues) == 1
        assert issues[0].key == "PROJ-123"

    @responses.activate
    def test_search_issues_pagination(self, jira_config, sample_jira_issue):
        # First page - 50 results with nextPageToken
        page1_issues = [
            {**sample_jira_issue, "key": f"PROJ-{i}"}
            for i in range(50)
        ]
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/search/jql",
            json={"issues": page1_issues, "isLast": False, "nextPageToken": "token123"},
            status=200,
        )

        # Second page - 25 results, last page
        page2_issues = [
            {**sample_jira_issue, "key": f"PROJ-{i}"}
            for i in range(50, 75)
        ]
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/search/jql",
            json={"issues": page2_issues, "isLast": True},
            status=200,
        )

        with JiraClient(jira_config) as client:
            issues = client.search_issues("project = PROJ")

        assert len(issues) == 75

    @responses.activate
    def test_search_issues_max_results(self, jira_config, sample_jira_issue):
        page1_issues = [
            {**sample_jira_issue, "key": f"PROJ-{i}"}
            for i in range(50)
        ]
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/search/jql",
            json={"issues": page1_issues, "isLast": False, "nextPageToken": "token123"},
            status=200,
        )

        with JiraClient(jira_config) as client:
            issues = client.search_issues("project = PROJ", max_results=10)

        assert len(issues) == 10

    @responses.activate
    def test_get_initiative_epics(self, jira_config, sample_epic):
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/search/jql",
            json={"issues": [sample_epic], "isLast": True},
            status=200,
        )

        with JiraClient(jira_config) as client:
            epics = client.get_initiative_epics("PROJ-50")

        assert len(epics) == 1
        assert epics[0].key == "PROJ-100"
        assert epics[0].issue_type == "Epic"

    @responses.activate
    def test_get_epic_children(self, jira_config, sample_jira_issue):
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/search/jql",
            json={"issues": [sample_jira_issue], "isLast": True},
            status=200,
        )

        with JiraClient(jira_config) as client:
            children = client.get_epic_children("PROJ-100")

        assert len(children) == 1
        assert children[0].parent_key == "PROJ-100"

    @responses.activate
    def test_get_user_open_issues(self, jira_config, sample_jira_issue):
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/search/jql",
            json={"issues": [sample_jira_issue], "isLast": True},
            status=200,
        )

        with JiraClient(jira_config) as client:
            issues = client.get_user_open_issues("account-123")

        assert len(issues) == 1

    @responses.activate
    def test_retry_on_rate_limit(self, jira_config, sample_jira_issue):
        # First request - rate limited
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/issue/PROJ-123",
            status=429,
            headers={"Retry-After": "0"},
        )
        # Second request - success
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/issue/PROJ-123",
            json=sample_jira_issue,
            status=200,
        )

        with JiraClient(jira_config) as client:
            issue = client.get_issue("PROJ-123")

        assert issue.key == "PROJ-123"
        assert len(responses.calls) == 2

    @responses.activate
    def test_retry_on_server_error(self, jira_config, sample_jira_issue):
        # First request - server error
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/issue/PROJ-123",
            status=500,
        )
        # Second request - success
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/issue/PROJ-123",
            json=sample_jira_issue,
            status=200,
        )

        with JiraClient(jira_config) as client:
            issue = client.get_issue("PROJ-123")

        assert issue.key == "PROJ-123"

    @responses.activate
    def test_http_error_raises(self, jira_config):
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/issue/PROJ-123",
            status=404,
            body="Not found",
        )

        with JiraClient(jira_config) as client:
            with pytest.raises(Exception, match="404"):
                client.get_issue("PROJ-123")

    def test_get_issue_validates_key(self, jira_config):
        with JiraClient(jira_config) as client:
            with pytest.raises(ValueError, match="Invalid Jira issue key"):
                client.get_issue('PROJ-1" OR 1=1')

    def test_get_initiative_epics_validates_key(self, jira_config):
        with JiraClient(jira_config) as client:
            with pytest.raises(ValueError, match="Invalid Jira issue key"):
                client.get_initiative_epics("malicious; DROP TABLE")

    @responses.activate
    def test_get_children_for_epics_batch(self, jira_config, sample_jira_issue):
        # Single API call should fetch children for multiple epics
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/search/jql",
            json={
                "issues": [
                    {**sample_jira_issue, "key": "PROJ-201", "fields": {**sample_jira_issue["fields"], "parent": {"key": "PROJ-100"}}},
                    {**sample_jira_issue, "key": "PROJ-202", "fields": {**sample_jira_issue["fields"], "parent": {"key": "PROJ-100"}}},
                    {**sample_jira_issue, "key": "PROJ-301", "fields": {**sample_jira_issue["fields"], "parent": {"key": "PROJ-200"}}},
                ],
                "isLast": True
            },
            status=200,
        )

        with JiraClient(jira_config) as client:
            result = client.get_children_for_epics(["PROJ-100", "PROJ-200"])

        # Should have made exactly 1 API call
        assert len(responses.calls) == 1
        # Should have grouped correctly
        assert len(result["PROJ-100"]) == 2
        assert len(result["PROJ-200"]) == 1

    def test_get_children_for_epics_empty_list(self, jira_config):
        with JiraClient(jira_config) as client:
            result = client.get_children_for_epics([])
        assert result == {}

    @responses.activate
    def test_get_children_for_epics_with_epic_link(self, jira_config, sample_jira_issue):
        """Test that issues linked via legacy Epic Link field are grouped correctly."""
        # Issue with parent=None but epic_link set (legacy linking)
        legacy_issue = {
            **sample_jira_issue,
            "key": "PROJ-301",
            "fields": {
                **sample_jira_issue["fields"],
                "parent": None,
                "customfield_10014": "PROJ-100",  # Legacy Epic Link
            },
        }
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/search/jql",
            json={"issues": [legacy_issue], "isLast": True},
            status=200,
        )

        with JiraClient(jira_config) as client:
            result = client.get_children_for_epics(["PROJ-100"])

        assert len(result["PROJ-100"]) == 1
        assert result["PROJ-100"][0].key == "PROJ-301"

    def test_parse_issue_epic_link_string(self, jira_config, sample_jira_issue):
        """Test parsing Epic Link when it's a plain string."""
        sample_jira_issue["fields"]["customfield_10014"] = "PROJ-100"
        sample_jira_issue["fields"]["parent"] = None
        client = JiraClient(jira_config)
        issue = client._parse_issue(sample_jira_issue)
        assert issue.epic_link == "PROJ-100"

    def test_parse_issue_epic_link_object(self, jira_config, sample_jira_issue):
        """Test parsing Epic Link when it's an object with key."""
        sample_jira_issue["fields"]["customfield_10014"] = {"key": "PROJ-100"}
        sample_jira_issue["fields"]["parent"] = None
        client = JiraClient(jira_config)
        issue = client._parse_issue(sample_jira_issue)
        assert issue.epic_link == "PROJ-100"
