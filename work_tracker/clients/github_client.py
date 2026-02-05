"""GitHub REST API client."""

import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Iterator

import requests
from dateutil.parser import parse as parse_date

from ..models import CodeReview, GitHubConfig, PullRequest

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 1.0
PAGE_SIZE = 100
DEFAULT_CACHE_TTL = 300  # 5 minutes
CACHE_CLEANUP_INTERVAL = 100  # Cleanup every N writes


class TTLCache:
    """Thread-safe in-memory cache with TTL expiration."""

    def __init__(self, ttl_seconds: int = DEFAULT_CACHE_TTL):
        self._cache: dict[str, tuple[float, Any]] = {}
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._write_count = 0
        # Metrics for observability
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Any | None:
        """Get value from cache if not expired (thread-safe)."""
        with self._lock:
            if key in self._cache:
                timestamp, value = self._cache[key]
                if time.time() - timestamp < self._ttl:
                    self.hits += 1
                    return value
                del self._cache[key]
            self.misses += 1
            return None

    def set(self, key: str, value: Any) -> None:
        """Store value in cache with current timestamp (thread-safe)."""
        with self._lock:
            self._cache[key] = (time.time(), value)
            self._write_count += 1
            # Periodic cleanup to prevent unbounded growth
            if self._write_count >= CACHE_CLEANUP_INTERVAL:
                self._cleanup_expired_unlocked()
                self._write_count = 0

    def _cleanup_expired_unlocked(self) -> None:
        """Remove expired entries. Must be called with lock held."""
        now = time.time()
        expired = [k for k, (ts, _) in self._cache.items() if now - ts >= self._ttl]
        for k in expired:
            del self._cache[k]

    def clear(self) -> None:
        """Clear all cached entries (thread-safe)."""
        with self._lock:
            self._cache.clear()
            self.hits = 0
            self.misses = 0

    def invalidate_prefix(self, prefix: str) -> None:
        """Invalidate all keys starting with prefix (thread-safe)."""
        with self._lock:
            keys_to_delete = [k for k in self._cache if k.startswith(prefix)]
            for key in keys_to_delete:
                del self._cache[key]

    def get_stats(self) -> dict[str, int]:
        """Get cache statistics."""
        with self._lock:
            return {
                "size": len(self._cache),
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": round(self.hits / (self.hits + self.misses) * 100, 1) if (self.hits + self.misses) > 0 else 0,
            }


class GitHubClient:
    """Client for GitHub REST API."""

    def __init__(self, config: GitHubConfig, cache_ttl: int = DEFAULT_CACHE_TTL):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {config.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        self._cache = TTLCache(ttl_seconds=cache_ttl)
        self._executor = ThreadPoolExecutor(max_workers=10)
        self._session_lock = threading.Lock()

    def close(self):
        """Close the session and release resources."""
        self._executor.shutdown(wait=True)  # Wait for in-flight work to complete
        self.session.close()
        self._cache.clear()

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

    def search_merged_prs(
        self,
        author: str,
        since: datetime,
        until: datetime | None = None,
    ) -> list[PullRequest]:
        """Search for merged PRs by merge date.

        Uses `is:merged merged:` qualifiers so PRs created before `since`
        but merged within the window are included.

        Args:
            author: GitHub username.
            since: Start date for merge date filter.
            until: End date for merge date filter (optional).

        Returns:
            List of PullRequest objects (all guaranteed merged).
        """
        date_filter = f"merged:>={since.strftime('%Y-%m-%d')}"
        if until:
            date_filter = f"merged:{since.strftime('%Y-%m-%d')}..{until.strftime('%Y-%m-%d')}"

        query = f"type:pr is:merged author:{author} org:{self.config.org} {date_filter}"

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
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Make an API request with retry logic and caching.

        Args:
            method: HTTP method.
            path: API path.
            params: Query parameters.
            headers: Additional headers.
            use_cache: Whether to use cache for GET requests (default True).

        Returns:
            Response data as dict.
        """
        url = f"https://api.github.com{path}"

        # Check cache for GET requests
        cache_key = None
        if method == "GET" and use_cache:
            cache_key = f"{path}:{json.dumps(params, sort_keys=True) if params else ''}"
            cached = self._cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for {path}")
                return cached

        for attempt in range(MAX_RETRIES):
            try:
                # Use lock for thread-safe session access
                with self._session_lock:
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
                    data = response.json()
                    # Cache successful GET responses
                    if cache_key is not None:
                        self._cache.set(cache_key, data)
                    return data
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

    # Batch methods for parallel fetching

    def get_pr_stats_batch(
        self,
        prs: list[PullRequest],
    ) -> dict[tuple[str, int], dict[str, int]]:
        """Fetch stats for multiple PRs in parallel.

        Args:
            prs: List of PullRequest objects to fetch stats for.

        Returns:
            Dict mapping (repo, pr_number) to stats dict with 'additions' and 'deletions'.
        """
        if not prs:
            return {}

        def fetch_stats(pr: PullRequest) -> tuple[tuple[str, int], dict[str, int] | None]:
            try:
                stats = self.get_pr_stats(self.config.org, pr.repo, pr.number)
                return ((pr.repo, pr.number), stats)
            except Exception as e:
                logger.warning(f"Failed to get stats for PR {pr.repo}#{pr.number}: {e}")
                return ((pr.repo, pr.number), None)

        results = {}
        futures = [self._executor.submit(fetch_stats, pr) for pr in prs]

        for future in as_completed(futures):
            try:
                key, stats = future.result(timeout=60)
                if stats is not None:
                    results[key] = stats
            except Exception as e:
                logger.warning(f"Batch stats fetch failed: {e}")

        return results

    def get_pr_files_batch(
        self,
        prs: list[PullRequest],
    ) -> dict[tuple[str, int], list[dict[str, Any]]]:
        """Fetch files for multiple PRs in parallel.

        Args:
            prs: List of PullRequest objects to fetch files for.

        Returns:
            Dict mapping (repo, pr_number) to list of file dicts.
        """
        if not prs:
            return {}

        def fetch_files(pr: PullRequest) -> tuple[tuple[str, int], list[dict[str, Any]] | None]:
            try:
                files = self.get_pr_files(self.config.org, pr.repo, pr.number)
                return ((pr.repo, pr.number), files)
            except Exception as e:
                logger.warning(f"Failed to get files for PR {pr.repo}#{pr.number}: {e}")
                return ((pr.repo, pr.number), None)

        results = {}
        futures = [self._executor.submit(fetch_files, pr) for pr in prs]

        for future in as_completed(futures):
            try:
                key, files = future.result(timeout=60)
                if files is not None:
                    results[key] = files
            except Exception as e:
                logger.warning(f"Batch files fetch failed: {e}")

        return results

    def get_turnaround_data_batch(
        self,
        reviews: list[CodeReview],
    ) -> dict[tuple[str, int], dict[str, Any]]:
        """Fetch timeline and review data for multiple reviews in parallel.

        Args:
            reviews: List of CodeReview objects.

        Returns:
            Dict mapping (repo, pr_number) to dict with 'timeline' and 'reviews' keys.
        """
        if not reviews:
            return {}

        def fetch_turnaround_data(review: CodeReview) -> tuple[tuple[str, int], dict[str, Any] | None]:
            try:
                timeline = self.get_pr_timeline(self.config.org, review.repo, review.pr_number)
                pr_reviews = self.get_reviews_for_pr(self.config.org, review.repo, review.pr_number)
                return ((review.repo, review.pr_number), {"timeline": timeline, "reviews": pr_reviews})
            except Exception as e:
                logger.warning(f"Failed to get turnaround data for PR {review.repo}#{review.pr_number}: {e}")
                return ((review.repo, review.pr_number), None)

        results = {}
        futures = [self._executor.submit(fetch_turnaround_data, review) for review in reviews]

        for future in as_completed(futures):
            try:
                key, data = future.result(timeout=60)
                if data is not None:
                    results[key] = data
            except Exception as e:
                logger.warning(f"Batch turnaround data fetch failed: {e}")

        return results

    def get_pr_diff(self, owner: str, repo: str, number: int) -> str:
        """Get the diff content for a PR.

        Args:
            owner: Repository owner.
            repo: Repository name.
            number: PR number.

        Returns:
            Diff content as a string.
        """
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}"
        headers = {"Accept": "application/vnd.github.v3.diff"}

        for attempt in range(MAX_RETRIES):
            try:
                with self._session_lock:
                    response = self.session.get(url, headers=headers, timeout=30)

                if response.status_code == 403:
                    remaining = response.headers.get("X-RateLimit-Remaining", "0")
                    if remaining == "0":
                        import time
                        reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
                        wait_time = max(reset_time - time.time(), 1)
                        logger.warning(f"Rate limited, waiting {wait_time:.0f}s")
                        time.sleep(min(wait_time, 60))
                        continue

                if response.status_code >= 500:
                    if attempt < MAX_RETRIES - 1:
                        delay = RETRY_DELAY * (2 ** attempt)
                        logger.warning(f"Server error {response.status_code}, retrying in {delay}s")
                        time.sleep(delay)
                        continue

                if response.status_code >= 400:
                    raise requests.exceptions.HTTPError(
                        f"{response.status_code} Error fetching diff for {repo}#{number}",
                        response=response,
                    )

                return response.text

            except requests.exceptions.RequestException as e:
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAY * (2 ** attempt)
                    logger.warning(f"Request failed: {e}, retrying in {delay}s")
                    time.sleep(delay)
                    continue
                raise

        raise requests.exceptions.RequestException(f"Failed to fetch diff after {MAX_RETRIES} retries")

    def search_open_prs(self, username: str) -> list[PullRequest]:
        """Search for open PRs authored by a user.

        Args:
            username: GitHub username.

        Returns:
            List of PullRequest objects for open PRs.
        """
        query = f"type:pr is:open author:{username} org:{self.config.org}"

        prs = []
        for item in self._paginate_search("issues", query):
            pr = self._parse_pr_from_search(item)
            prs.append(pr)

        return prs

    def get_reviewers_for_pr_batch(
        self,
        prs: list[PullRequest],
    ) -> dict[tuple[str, int], list[str]]:
        """Fetch reviewers for multiple PRs in parallel.

        Args:
            prs: List of PullRequest objects.

        Returns:
            Dict mapping (repo, pr_number) to list of reviewer usernames.
        """
        if not prs:
            return {}

        def fetch_reviewers(pr: PullRequest) -> tuple[tuple[str, int], list[str] | None]:
            try:
                reviews = self.get_reviews_for_pr(self.config.org, pr.repo, pr.number)
                # Dedupe reviewers, preserving order
                seen = set()
                reviewers = []
                for review in reviews:
                    user = review.get("user", {})
                    login = user.get("login", "")
                    if login and login not in seen:
                        seen.add(login)
                        reviewers.append(login)
                return ((pr.repo, pr.number), reviewers)
            except Exception as e:
                logger.warning(f"Failed to get reviewers for PR {pr.repo}#{pr.number}: {e}")
                return ((pr.repo, pr.number), None)

        results = {}
        futures = [self._executor.submit(fetch_reviewers, pr) for pr in prs]

        for future in as_completed(futures):
            try:
                key, reviewers = future.result(timeout=60)
                if reviewers is not None:
                    results[key] = reviewers
            except Exception as e:
                logger.warning(f"Batch reviewers fetch failed: {e}")

        return results
