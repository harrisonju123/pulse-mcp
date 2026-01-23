"""Jira REST API client."""

import json
import logging
import re
import time
from datetime import datetime
from typing import Any, Iterator

import requests
from dateutil.parser import parse as parse_date

from ..models import JiraConfig, JiraIssue

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 1.0
PAGE_SIZE = 50

# Pattern for valid Jira issue keys (e.g., PROJ-123)
ISSUE_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")


def _validate_issue_key(key: str) -> None:
    """Validate that a string is a valid Jira issue key to prevent JQL injection."""
    if not ISSUE_KEY_PATTERN.match(key):
        raise ValueError(f"Invalid Jira issue key format: {key}")


def _escape_jql_string(value: str) -> str:
    """Escape special characters in JQL string values."""
    # Escape backslashes first, then quotes
    return value.replace("\\", "\\\\").replace('"', '\\"')


class JiraClient:
    """Client for Jira REST API v3."""

    def __init__(self, config: JiraConfig):
        self.config = config
        self.session = requests.Session()
        self.session.auth = (config.email, config.api_token)
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def get_issue(self, issue_key: str) -> JiraIssue:
        """Fetch a single issue by key."""
        _validate_issue_key(issue_key)
        fields = self._standard_fields()
        data = self._request("GET", f"/rest/api/3/issue/{issue_key}", params={
            "fields": ",".join(fields),
        })
        return self._parse_issue(data)

    def search_issues(self, jql: str, max_results: int | None = None) -> list[JiraIssue]:
        """Search issues using JQL."""
        issues = []
        for issue in self._paginate_search(jql):
            issues.append(issue)
            if max_results and len(issues) >= max_results:
                break
        return issues

    def get_initiative_epics(self, initiative_key: str) -> list[JiraIssue]:
        """Get all epics under an initiative."""
        _validate_issue_key(initiative_key)
        jql = f'parent = "{initiative_key}" AND issuetype = Epic ORDER BY rank'
        return self.search_issues(jql)

    def get_epic_children(self, epic_key: str) -> list[JiraIssue]:
        """Get all issues under an epic."""
        _validate_issue_key(epic_key)
        jql = f'"Epic Link" = "{epic_key}" OR parent = "{epic_key}" ORDER BY rank'
        return self.search_issues(jql)

    def get_children_for_epics(self, epic_keys: list[str]) -> dict[str, list[JiraIssue]]:
        """Batch fetch children for multiple epics in a single query."""
        if not epic_keys:
            return {}

        for key in epic_keys:
            _validate_issue_key(key)

        # Build JQL to fetch all children at once
        keys_str = ", ".join(f'"{k}"' for k in epic_keys)
        jql = f'"Epic Link" in ({keys_str}) OR parent in ({keys_str}) ORDER BY rank'
        all_children = self.search_issues(jql)

        # Group by parent or epic link (prefer parent, fall back to epic_link)
        children_by_epic: dict[str, list[JiraIssue]] = {k: [] for k in epic_keys}
        for issue in all_children:
            epic_key = issue.parent_key or issue.epic_link
            if epic_key and epic_key in children_by_epic:
                children_by_epic[epic_key].append(issue)

        return children_by_epic

    def get_user_open_issues(self, account_id: str) -> list[JiraIssue]:
        """Get open issues assigned to a user across configured projects."""
        # Escape account_id to prevent injection
        escaped_account_id = _escape_jql_string(account_id)
        projects = ", ".join(f'"{p}"' for p in self.config.project_keys)
        jql = f'assignee = "{escaped_account_id}" AND statusCategory != Done AND project in ({projects}) ORDER BY rank'
        return self.search_issues(jql)

    def _paginate_search(self, jql: str) -> Iterator[JiraIssue]:
        """Search with pagination using the new /search/jql endpoint."""
        fields = self._standard_fields()
        next_page_token = None

        while True:
            # Use POST to /search/jql with token-based pagination
            payload = {
                "jql": jql,
                "maxResults": PAGE_SIZE,
                "fields": fields,
            }
            if next_page_token:
                payload["nextPageToken"] = next_page_token

            data = self._request("POST", "/rest/api/3/search/jql", json_data=payload)
            issues = data.get("issues", [])

            for raw in issues:
                try:
                    yield self._parse_issue(raw)
                except ValueError as e:
                    logger.warning(f"Skipping malformed issue: {e}")
                    continue

            # Check if there are more pages
            if data.get("isLast", True):
                break

            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break

    def _standard_fields(self) -> list[str]:
        return [
            "summary", "issuetype", "status", "assignee", "duedate",
            "parent", "labels", "created", "updated",
            self.config.story_point_field,
            self.config.epic_link_field,
        ]

    def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json_data: dict | None = None,
    ) -> dict[str, Any]:
        """Make an API request with retry logic."""
        url = f"{self.config.base_url}{path}"

        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.request(
                    method,
                    url,
                    params=params,
                    json=json_data,
                )

                if response.status_code == 429:
                    if attempt < MAX_RETRIES - 1:
                        try:
                            retry_after = int(response.headers.get("Retry-After", RETRY_DELAY))
                        except ValueError:
                            retry_after = int(RETRY_DELAY)
                        logger.warning(f"Rate limited, waiting {retry_after}s (attempt {attempt + 1}/{MAX_RETRIES})")
                        time.sleep(retry_after)
                        continue
                    # Fall through to 4xx error handling on final attempt

                if response.status_code >= 500:
                    if attempt < MAX_RETRIES - 1:
                        delay = RETRY_DELAY * (2 ** attempt)
                        logger.warning(f"Server error {response.status_code}, retrying in {delay}s")
                        time.sleep(delay)
                        continue

                if response.status_code >= 400:
                    error_body = response.text[:1000]
                    raise requests.exceptions.HTTPError(
                        f"{response.status_code} Error for {url}: {error_body}",
                        response=response,
                    )

                try:
                    return response.json()
                except json.JSONDecodeError as e:
                    raise requests.exceptions.RequestException(
                        f"Invalid JSON response from {url}: {response.text[:200]}"
                    ) from e

            except requests.exceptions.RequestException as e:
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAY * (2 ** attempt)
                    logger.warning(f"Request failed: {e}, retrying in {delay}s")
                    time.sleep(delay)
                    continue
                raise

        raise requests.exceptions.RequestException(f"Failed after {MAX_RETRIES} retries")

    def _parse_issue(self, raw: dict[str, Any]) -> JiraIssue:
        """Parse raw API response into JiraIssue."""
        fields = raw.get("fields", {})
        key = raw.get("key")
        if not key:
            raise ValueError("Issue missing required 'key' field")

        assignee = fields.get("assignee") or {}
        parent = fields.get("parent") or {}
        status = fields.get("status") or {}
        status_category = status.get("statusCategory", {})

        created = None
        if fields.get("created"):
            try:
                created = parse_date(fields["created"])
            except (ValueError, TypeError):
                pass

        updated = None
        if fields.get("updated"):
            try:
                updated = parse_date(fields["updated"])
            except (ValueError, TypeError):
                pass

        due_date = None
        if fields.get("duedate"):
            try:
                due_date = parse_date(fields["duedate"])
            except (ValueError, TypeError):
                pass

        story_points = fields.get(self.config.story_point_field)
        if story_points is not None:
            try:
                story_points = float(story_points)
            except (ValueError, TypeError):
                story_points = None

        # Legacy Epic Link field - can be a string key or an object with key
        epic_link_raw = fields.get(self.config.epic_link_field)
        epic_link = None
        if epic_link_raw:
            if isinstance(epic_link_raw, str):
                epic_link = epic_link_raw
            elif isinstance(epic_link_raw, dict):
                epic_link = epic_link_raw.get("key")

        return JiraIssue(
            key=key,
            summary=fields.get("summary", ""),
            issue_type=(fields.get("issuetype") or {}).get("name", ""),
            status=status.get("name", ""),
            status_category=status_category.get("name", ""),
            assignee_account_id=assignee.get("accountId"),
            assignee_name=assignee.get("displayName"),
            story_points=story_points,
            due_date=due_date,
            parent_key=parent.get("key"),
            epic_link=epic_link,
            labels=fields.get("labels", []),
            url=f"{self.config.base_url}/browse/{key}",
            created=created,
            updated=updated,
        )
