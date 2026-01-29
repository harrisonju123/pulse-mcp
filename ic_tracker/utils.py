"""Shared utilities for ic_tracker."""

import re
from datetime import datetime, timedelta, timezone


def parse_date_range(
    days: int = 14,
    start_date: str | None = None,
    end_date: str | None = None,
) -> tuple[datetime, datetime] | dict:
    """Parse date range from parameters.

    Args:
        days: Number of days to look back (used if start_date not provided).
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.

    Returns:
        Tuple of (since, until) datetimes, or error dict if validation fails.
    """
    if start_date:
        try:
            since = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            until = (
                datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if end_date
                else datetime.now(timezone.utc)
            )
            if since > until:
                return {"error": "start_date must be before end_date"}
        except ValueError as e:
            return {"error": f"Invalid date format. Expected YYYY-MM-DD: {e}"}
    else:
        if days < 1 or days > 365:
            return {"error": "days must be between 1 and 365"}
        since = datetime.now(timezone.utc) - timedelta(days=days)
        until = datetime.now(timezone.utc)

    return since, until


# Patterns for inferring area from file path
AREA_PATTERNS = [
    # Frontend patterns
    (r"(^|/)src/(components|pages|views|ui|frontend)/", "frontend"),
    (r"\.(tsx|jsx|vue|svelte)$", "frontend"),
    (r"(^|/)(web|client|app)/", "frontend"),
    (r"(^|/)styles?/", "frontend"),
    (r"\.(css|scss|sass|less)$", "frontend"),

    # Backend patterns
    (r"(^|/)src/(api|server|services|handlers)/", "backend"),
    (r"(^|/)(cmd|internal|pkg)/", "backend"),
    (r"(^|/)controllers?/", "backend"),
    (r"(^|/)models?/", "backend"),

    # Infrastructure patterns
    (r"(^|/)(infra|infrastructure|terraform|pulumi)/", "infrastructure"),
    (r"(^|/)(k8s|kubernetes|helm|charts)/", "infrastructure"),
    (r"(^|/)\.github/(workflows|actions)/", "infrastructure"),
    (r"\.(tf|tfvars)$", "infrastructure"),
    (r"(Dockerfile|docker-compose)", "infrastructure"),

    # Data patterns
    (r"(^|/)(data|analytics|etl|pipelines)/", "data"),
    (r"(^|/)migrations?/", "data"),
    (r"\.sql$", "data"),

    # Testing patterns
    (r"(^|/)(tests?|spec|__tests__|e2e)/", "testing"),
    (r"[._]test\.(py|go|ts|js)$", "testing"),
    (r"[._]spec\.(py|go|ts|js)$", "testing"),

    # Documentation patterns
    (r"(^|/)(docs?|documentation)/", "documentation"),
    (r"\.(md|rst|adoc)$", "documentation"),
    (r"(README|CHANGELOG|CONTRIBUTING)", "documentation"),

    # Configuration patterns
    (r"(^|/)(config|configs|settings)/", "configuration"),
    (r"\.(yaml|yml|json|toml|ini)$", "configuration"),
]


def infer_area_from_path(file_path: str) -> str:
    """Infer the work area from a file path.

    Uses pattern matching to categorize files into areas like
    frontend, backend, infrastructure, data, testing, documentation,
    or configuration.

    Args:
        file_path: Path to the file (can be relative or absolute).

    Returns:
        Inferred area string, or "other" if no pattern matches.
    """
    for pattern, area in AREA_PATTERNS:
        if re.search(pattern, file_path, re.IGNORECASE):
            return area
    return "other"


def get_file_extension(file_path: str) -> str:
    """Extract file extension from path.

    Args:
        file_path: Path to the file.

    Returns:
        File extension without the dot, or empty string if no extension.
    """
    match = re.search(r"\.([^./]+)$", file_path)
    return match.group(1).lower() if match else ""


# Patterns for identifying generated/noise files vs feature work
GENERATED_FILE_PATTERNS = [
    # Lock files and dependency manifests
    (r"(^|/)go\.sum$", "deps"),
    (r"(^|/)package-lock\.json$", "deps"),
    (r"(^|/)yarn\.lock$", "deps"),
    (r"(^|/)pnpm-lock\.yaml$", "deps"),
    (r"(^|/)Gemfile\.lock$", "deps"),
    (r"(^|/)poetry\.lock$", "deps"),
    (r"(^|/)Pipfile\.lock$", "deps"),
    (r"(^|/)composer\.lock$", "deps"),
    (r"(^|/)Cargo\.lock$", "deps"),

    # Vendor and node_modules
    (r"(^|/)vendor/", "vendor"),
    (r"(^|/)node_modules/", "vendor"),

    # Generated code patterns
    (r"\.pb\.go$", "generated"),
    (r"_gen\.go$", "generated"),
    (r"_generated\.go$", "generated"),
    (r"\.generated\.", "generated"),
    (r"(^|/)generated/", "generated"),
    (r"mock_.*\.go$", "generated"),
    (r"_mock\.go$", "generated"),
    (r"\.graphql\.ts$", "generated"),
    (r"__generated__/", "generated"),

    # Build outputs
    (r"(^|/)dist/", "build"),
    (r"(^|/)build/", "build"),
    (r"\.min\.js$", "build"),
    (r"\.min\.css$", "build"),
    (r"\.bundle\.js$", "build"),

    # Snapshots and fixtures
    (r"\.snap$", "snapshot"),
    (r"__snapshots__/", "snapshot"),

    # IDE and editor files
    (r"(^|/)\.idea/", "ide"),
    (r"(^|/)\.vscode/", "ide"),
    (r"\.DS_Store$", "ide"),
]

# Test file patterns (important but separate from feature work)
TEST_FILE_PATTERNS = [
    r"(^|/)tests?/",
    r"(^|/)__tests__/",
    r"(^|/)spec/",
    r"_test\.go$",
    r"_test\.py$",
    r"\.test\.(ts|tsx|js|jsx)$",
    r"\.spec\.(ts|tsx|js|jsx)$",
    r"_spec\.rb$",
    r"test_.*\.py$",
]


def categorize_file(file_path: str) -> str:
    """Categorize a file as feature work, test, or noise.

    Args:
        file_path: Path to the file.

    Returns:
        Category: "feature", "test", "deps", "vendor", "generated", "build", "snapshot", "ide"
    """
    # Check generated/noise patterns first
    for pattern, category in GENERATED_FILE_PATTERNS:
        if re.search(pattern, file_path, re.IGNORECASE):
            return category

    # Check test patterns
    for pattern in TEST_FILE_PATTERNS:
        if re.search(pattern, file_path, re.IGNORECASE):
            return "test"

    # Default to feature work
    return "feature"


def is_feature_file(file_path: str) -> bool:
    """Check if a file represents actual feature work.

    Args:
        file_path: Path to the file.

    Returns:
        True if the file is feature work (not generated, deps, tests, etc.)
    """
    return categorize_file(file_path) == "feature"
