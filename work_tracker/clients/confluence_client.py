"""Confluence REST API client."""

import json
import logging
import time
from datetime import datetime
from typing import Any, Iterator

import requests
from dateutil.parser import parse as parse_date

from ..models import ConfluenceConfig, ConfluencePage

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 1.0
PAGE_SIZE = 25


class ConfluenceClient:
    """Client for Confluence REST API."""

    def __init__(self, config: ConfluenceConfig):
        self.config = config
        self.session = requests.Session()
        self.session.auth = (config.email, config.api_token)
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

    def close(self):
        """Close the session and release resources."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def get_user_contributions(
        self,
        account_id: str,
        since: datetime,
        space_keys: list[str],
        until: datetime | None = None,
    ) -> dict:
        """Get all contributions for a user in specified spaces.

        Args:
            account_id: Atlassian account ID of the contributor.
            since: Start date for contributions.
            space_keys: List of Confluence space keys to search.
            until: End date for contributions (optional).

        Returns:
            Dict with pages_created, pages_updated, comments, and blogposts.
        """
        if not space_keys:
            raise ValueError("space_keys cannot be empty")

        since_str = since.strftime("%Y-%m-%d")
        until_str = until.strftime("%Y-%m-%d") if until else None
        spaces_filter = " OR ".join(f'space = "{key}"' for key in space_keys)

        results = {
            "pages_created": [],
            "pages_updated": [],
            "comments": [],
            "blogposts": [],
        }
        # Track created page IDs for O(1) duplicate detection
        created_page_ids: set[str] = set()

        def date_filter(field: str) -> str:
            if until_str:
                return f'{field} >= "{since_str}" AND {field} <= "{until_str}"'
            return f'{field} >= "{since_str}"'

        cql_created = (
            f'({spaces_filter}) AND type = page AND creator = "{account_id}" '
            f'AND {date_filter("created")}'
        )
        for page in self._search_content(cql_created):
            page_dict = self._page_to_dict(page)
            results["pages_created"].append(page_dict)
            created_page_ids.add(page.id)

        # Search for pages updated by user (but not created by them)
        cql_updated = (
            f'({spaces_filter}) AND type = page AND contributor = "{account_id}" '
            f'AND {date_filter("lastmodified")}'
        )
        for page in self._search_content(cql_updated):
            page_dict = self._page_to_dict(page)
            # Avoid duplicates if user created and updated the same page
            if page_dict["id"] not in created_page_ids:
                results["pages_updated"].append(page_dict)

        cql_blog = (
            f'({spaces_filter}) AND type = blogpost AND creator = "{account_id}" '
            f'AND {date_filter("created")}'
        )
        for page in self._search_content(cql_blog):
            results["blogposts"].append(self._page_to_dict(page))

        cql_comments = (
            f'({spaces_filter}) AND type = comment AND creator = "{account_id}" '
            f'AND {date_filter("created")}'
        )
        for comment in self._search_content(cql_comments):
            results["comments"].append({
                "id": comment.id,
                "title": comment.title,
                "space_key": comment.space_key,
                "url": comment.url,
                "created": comment.created.isoformat() if comment.created else None,
            })

        return results

    def _search_content(self, cql: str) -> Iterator[ConfluencePage]:
        """Search for content using CQL with pagination.

        Args:
            cql: Confluence Query Language query string.

        Yields:
            ConfluencePage objects matching the query.
        """
        start = 0
        while True:
            params = {
                "cql": cql,
                "start": start,
                "limit": PAGE_SIZE,
                "expand": "space,history,version",
            }

            data = self._request("GET", "/rest/api/content/search", params=params)
            results = data.get("results", [])

            if not results:
                break

            for item in results:
                try:
                    yield self._parse_content(item)
                except ValueError as e:
                    logger.warning(f"Skipping malformed content: {e}")
                    continue

            if len(results) < PAGE_SIZE:
                break

            start += PAGE_SIZE

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
                    try:
                        retry_after = int(response.headers.get("Retry-After", RETRY_DELAY))
                    except ValueError:
                        retry_after = int(RETRY_DELAY)
                    logger.warning(f"Rate limited, waiting {retry_after}s")
                    time.sleep(retry_after)
                    continue

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

    def _parse_content(self, raw: dict[str, Any]) -> ConfluencePage:
        """Parse raw API response into ConfluencePage."""
        space = raw.get("space", {})
        history = raw.get("history", {})
        version = raw.get("version", {})

        created = None
        if history.get("createdDate"):
            try:
                created = parse_date(history["createdDate"])
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse created date: {e}")

        updated = None
        if version.get("when"):
            try:
                updated = parse_date(version["when"])
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse updated date: {e}")

        page_id = raw.get("id")
        if not page_id:
            logger.warning(f"Confluence content missing id field, keys present: {list(raw.keys())}")
            raise ValueError("Confluence content missing required 'id' field")
        content_type = raw.get("type", "page")

        base_url = self.config.base_url.replace("/wiki", "")
        space_key = space.get("key", "")
        url = f"{base_url}/wiki/spaces/{space_key}/{content_type}s/{page_id}"

        return ConfluencePage(
            id=page_id,
            title=raw.get("title", ""),
            space_key=space_key,
            type=content_type,
            url=url,
            created=created,
            updated=updated,
        )

    def _page_to_dict(self, page: ConfluencePage) -> dict:
        """Convert ConfluencePage to dictionary for JSON serialization."""
        return {
            "id": page.id,
            "title": page.title,
            "space_key": page.space_key,
            "type": page.type,
            "url": page.url,
            "created": page.created.isoformat() if page.created else None,
            "updated": page.updated.isoformat() if page.updated else None,
        }
