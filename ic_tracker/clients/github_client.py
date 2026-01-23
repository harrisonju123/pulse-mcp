"""GitHub REST API client."""

import json
import logging
import re
import time
from datetime import datetime
from typing import Any, Iterator

import requests
from dateutil.parser import parse as parse_date

from ..models import CodeReview, GitHubConfig, PullRequest

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 1.0
PAGE_SIZE = 100


class GitHubClient:
    """Client for GitHub REST API."""

    def __init__(self, config: GitHubConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {config.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        })

    def close(self):
        """Close the session and release resources."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def search_prs(
        self,
        author: str,
        since: datetime,
        until: datetime | None = None,
    ) -> list[PullRequest]:
        """Search for PRs authored by a user.

        Args:
            author: GitHub username.
            since: Start date for search.
            until: End date for search (optional).

        Returns:
            List of PullRequest objects.
        """
        date_filter = f"created:>={since.strftime('%Y-%m-%d')}"
        if until:
            date_filter = f"created:{since.strftime('%Y-%m-%d')}..{until.strftime('%Y-%m-%d')}"

        query = f"type:pr author:{author} org:{self.config.org} {date_filter}"

        prs = []
        for item in self._paginate_search("issues", query):
            pr = self._parse_pr_from_search(item)
            prs.append(pr)

        return prs

    def get_pr_stats(self, owner: str, repo: str, number: int) -> dict[str, int]:
        """Get additions/deletions for a PR.

        Args:
            owner: Repository owner.
            repo: Repository name.
            number: PR number.

        Returns:
            Dict with 'additions' and 'deletions' keys.
        """
        data = self._request("GET", f"/repos/{owner}/{repo}/pulls/{number}")
        return {
            "additions": data.get("additions", 0),
            "deletions": data.get("deletions", 0),
        }

    def get_reviews_by_user(
        self,
        reviewer: str,
        since: datetime,
        until: datetime | None = None,
    ) -> list[CodeReview]:
        """Get reviews given by a user.

        Note: GitHub's search API filters by PR creation date, not review date.
        This means reviews on PRs created before the `since` date won't appear,
        even if the review itself was submitted within the date range.

        Args:
            reviewer: GitHub username.
            since: Start date for search (filters by PR creation date).
            until: End date for search (optional, filters by PR creation date).

        Returns:
            List of CodeReview objects.
        """
        date_filter = f"created:>={since.strftime('%Y-%m-%d')}"
        if until:
            date_filter = f"created:{since.strftime('%Y-%m-%d')}..{until.strftime('%Y-%m-%d')}"

        query = f"type:pr reviewed-by:{reviewer} org:{self.config.org} {date_filter}"

        reviews = []
        seen_prs = set()

        for item in self._paginate_search("issues", query):
            pr_url = item.get("pull_request", {}).get("url", "")
            if not pr_url or pr_url in seen_prs:
                continue
            seen_prs.add(pr_url)

            submitted_at = None
            if item.get("created_at"):
                try:
                    submitted_at = parse_date(item["created_at"])
                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to parse review created_at: {e}")

            review = CodeReview(
                pr_number=item.get("number", 0),
                pr_title=item.get("title", ""),
                repo=self._extract_repo_from_url(item.get("repository_url", "")),
                state="REVIEWED",
                url=item.get("html_url", ""),
                submitted_at=submitted_at,
            )
            reviews.append(review)

        return reviews

    def _paginate_search(self, endpoint: str, query: str) -> Iterator[dict[str, Any]]:
        """Paginate through search results."""
        page = 1

        while True:
            params = {
                "q": query,
                "per_page": PAGE_SIZE,
                "page": page,
            }

            data = self._request("GET", f"/search/{endpoint}", params=params)

            for item in data.get("items", []):
                yield item

            total = data.get("total_count", 0)
            if page * PAGE_SIZE >= total:
                break

            page += 1

    def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> dict[str, Any]:
        """Make an API request with retry logic."""
        url = f"https://api.github.com{path}"

        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.request(method, url, params=params, headers=headers, timeout=30)

                if response.status_code == 403:
                    remaining = response.headers.get("X-RateLimit-Remaining", "0")
                    if remaining == "0":
                        # Rate limit - wait and retry
                        try:
                            reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
                        except ValueError:
                            reset_time = 0
                        wait_time = max(reset_time - time.time(), 1)
                        logger.warning(f"Rate limited, waiting {wait_time:.0f}s")
                        time.sleep(min(wait_time, 60))
                        continue
                    # Not a rate limit (e.g., bad token, no access) - fall through to error handling

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

    def _parse_pr_from_search(self, item: dict[str, Any]) -> PullRequest:
        """Parse PR from search result."""
        repo = self._extract_repo_from_url(item.get("repository_url", ""))

        created_at = None
        if item.get("created_at"):
            try:
                created_at = parse_date(item["created_at"])
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse PR created_at: {e}")

        merged_at = None
        state = item.get("state", "open")
        merged = False

        pr_data = item.get("pull_request", {})
        if pr_data.get("merged_at"):
            try:
                merged_at = parse_date(pr_data["merged_at"])
                merged = True
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse PR merged_at: {e}")

        return PullRequest(
            number=item.get("number", 0),
            title=item.get("title", ""),
            repo=repo,
            state=state,
            merged=merged,
            url=item.get("html_url", ""),
            created_at=created_at,
            merged_at=merged_at,
        )

    def _extract_repo_from_url(self, url: str) -> str:
        """Extract repo name from GitHub API URL."""
        match = re.search(r"/repos/[^/]+/([^/]+)", url)
        return match.group(1) if match else ""

    def get_pr_timeline(self, owner: str, repo: str, number: int) -> list[dict[str, Any]]:
        """Get timeline events for a PR.

        Returns events including review_requested and reviewed events,
        which can be used to calculate review turnaround time.

        Args:
            owner: Repository owner.
            repo: Repository name.
            number: PR number.

        Returns:
            List of timeline event dicts.
        """
        events = []
        page = 1
        # Timeline API requires special Accept header for full event details
        timeline_headers = {"Accept": "application/vnd.github.mockingbird-preview+json"}

        while True:
            params = {"per_page": PAGE_SIZE, "page": page}
            data = self._request(
                "GET",
                f"/repos/{owner}/{repo}/issues/{number}/timeline",
                params=params,
                headers=timeline_headers,
            )

            if not data:
                break

            events.extend(data)

            if len(data) < PAGE_SIZE:
                break
            page += 1

        return events

    def get_pr_files(self, owner: str, repo: str, number: int) -> list[dict[str, Any]]:
        """Get files changed in a PR.

        Args:
            owner: Repository owner.
            repo: Repository name.
            number: PR number.

        Returns:
            List of file dicts with filename, status, additions, deletions.
        """
        files = []
        page = 1

        while True:
            params = {"per_page": PAGE_SIZE, "page": page}
            data = self._request(
                "GET",
                f"/repos/{owner}/{repo}/pulls/{number}/files",
                params=params,
            )

            if not data:
                break

            files.extend(data)

            if len(data) < PAGE_SIZE:
                break
            page += 1

        return files

    def get_reviews_for_pr(
        self,
        owner: str,
        repo: str,
        number: int,
    ) -> list[dict[str, Any]]:
        """Get all reviews submitted on a PR.

        Args:
            owner: Repository owner.
            repo: Repository name.
            number: PR number.

        Returns:
            List of review dicts with user, state, submitted_at.
        """
        reviews = []
        page = 1

        while True:
            params = {"per_page": PAGE_SIZE, "page": page}
            data = self._request(
                "GET",
                f"/repos/{owner}/{repo}/pulls/{number}/reviews",
                params=params,
            )

            if not data:
                break

            reviews.extend(data)

            if len(data) < PAGE_SIZE:
                break
            page += 1

        return reviews
