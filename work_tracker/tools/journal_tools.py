"""MCP tools for personal reflection/journaling."""

import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from mcp.types import Tool

from ..models import Config
from ..utils import (
    MAX_JOURNAL_ENTRIES_PER_DAY,
    MAX_JOURNAL_FILE_SIZE_MB,
    PREVIEW_LENGTH,
    resolve_username,
    sanitize_username_for_filesystem,
    utc_now,
)

logger = logging.getLogger(__name__)

JOURNAL_DIR = "reflections"  # Directory for journal entries


def get_journal_tools() -> list[Tool]:
    """Return list of journal-related MCP tools."""
    return [
        Tool(
            name="add_journal_entry",
            description="Add a personal reflection or journal entry. Entries are stored with today's date.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The journal entry content (markdown supported)",
                    },
                    "title": {
                        "type": "string",
                        "description": "Optional title for the entry",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional tags for categorization. Examples: 'wins', 'learning', 'blockers'",
                    },
                    "github_username": {
                        "type": "string",
                        "description": "GitHub username. If omitted and 'self' is configured, uses self.",
                    },
                },
                "required": ["content"],
            },
        ),
        Tool(
            name="get_journal_entries",
            description="Get journal entries within a date range.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Number of days to look back (default: 30, max: 365)",
                        "default": 30,
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format. Overrides 'days'. Example: '2026-01-01'",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format. Defaults to today. Example: '2026-01-31'",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by tags (any match)",
                    },
                    "github_username": {
                        "type": "string",
                        "description": "GitHub username. If omitted and 'self' is configured, uses self.",
                    },
                },
            },
        ),
        Tool(
            name="search_journal",
            description="Search journal entries by keyword.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (case-insensitive)",
                    },
                    "days": {
                        "type": "integer",
                        "description": "Limit search to last N days (default: 90, max: 365)",
                        "default": 90,
                    },
                    "github_username": {
                        "type": "string",
                        "description": "GitHub username. If omitted and 'self' is configured, uses self.",
                    },
                },
                "required": ["query"],
            },
        ),
    ]


def _get_journal_dir(github_username: str) -> Path:
    """Get path to user's journal directory."""
    safe_username = sanitize_username_for_filesystem(github_username)
    return Path(JOURNAL_DIR) / safe_username


def _get_journal_file_path(github_username: str, date: datetime) -> Path:
    """Get path to journal file for a specific date."""
    return _get_journal_dir(github_username) / f"{date.strftime('%Y-%m-%d')}.md"


def _parse_journal_file(file_path: Path) -> list[dict]:
    """Parse a journal markdown file into entries.

    Format:
        ## Title (optional)
        [HH:MM] (optional)

        Content here...
        #tag1 #tag2

        ---

        ## Another Entry
        ...

    Args:
        file_path: Path to journal file.

    Returns:
        List of entry dicts with time, title, content, tags.
    """
    if not file_path.exists():
        return []

    try:
        # Check file size limit
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        if file_size_mb > MAX_JOURNAL_FILE_SIZE_MB:
            logger.warning(
                f"Journal file {file_path} exceeds size limit "
                f"({file_size_mb:.1f}MB > {MAX_JOURNAL_FILE_SIZE_MB}MB)"
            )
            # Still try to parse but log warning

        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        entries = []
        # Split by horizontal rules (entry separators)
        sections = re.split(r'\n---+\n', content)

        for section in sections:
            if not section.strip():
                continue

            lines = section.strip().split('\n')
            title = None
            time_str = None
            content_lines = []

            i = 0
            # Check for title (## Header)
            if i < len(lines) and lines[i].startswith('## '):
                title = lines[i][3:].strip()
                i += 1

            # Check for time [HH:MM]
            if i < len(lines):
                time_match = re.match(r'\[(\d{2}:\d{2})\]', lines[i].strip())
                if time_match:
                    time_str = time_match.group(1)
                    i += 1

            # Rest is content
            content_lines = lines[i:]
            entry_content = '\n'.join(content_lines).strip()

            # Extract tags from content
            tags = []
            tag_matches = re.findall(r'#(\w+)', entry_content)
            if tag_matches:
                # Use set to deduplicate, then convert to list
                tags = list(set(tag_matches))

            if entry_content:  # Only add if there's actual content
                entries.append({
                    "time": time_str,
                    "title": title,
                    "content": entry_content,
                    "tags": tags,
                })

        logger.debug(f"Parsed {len(entries)} entries from {file_path}")
        return entries

    except Exception as e:
        logger.error(f"Failed to parse journal file {file_path}: {e}")
        return []


def _write_journal_entry(
    github_username: str,
    date: datetime,
    title: Optional[str],
    content: str,
    tags: Optional[list[str]],
) -> None:
    """Append an entry to a journal file."""
    file_path = _get_journal_file_path(github_username, date)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Check entry count limit
    if file_path.exists():
        existing_entries = _parse_journal_file(file_path)
        if len(existing_entries) >= MAX_JOURNAL_ENTRIES_PER_DAY:
            raise ValueError(
                f"Maximum of {MAX_JOURNAL_ENTRIES_PER_DAY} entries per day reached"
            )

    now = utc_now()
    time_str = now.strftime("%H:%M")

    # Prepare entry
    separator = "\n---\n\n" if file_path.exists() else ""

    entry_parts = []
    if title:
        entry_parts.append(f"## {title}")
    entry_parts.append(f"[{time_str}]\n")
    entry_parts.append(content)

    if tags:
        tag_str = " ".join(f"#{tag}" for tag in tags)
        entry_parts.append(f"\n\n{tag_str}")

    entry = "\n".join(entry_parts)

    with open(file_path, "a", encoding="utf-8") as f:
        f.write(separator)
        f.write(entry)
        f.write("\n")

    logger.debug(f"Added journal entry to {file_path}")


def _get_date_range(
    days: int,
    start_date: Optional[str],
    end_date: Optional[str],
) -> tuple[datetime, datetime]:
    """Parse date range parameters with validation."""
    now = utc_now()

    try:
        if end_date:
            until = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc)
        else:
            until = now

        if start_date:
            since = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
        else:
            if days <= 0:
                raise ValueError("days must be positive")
            if days > 365:
                raise ValueError("days cannot exceed 365")
            since = until - timedelta(days=days)

        if since > until:
            raise ValueError("start_date must be before end_date")

        return since, until

    except ValueError as e:
        if "Invalid isoformat string" in str(e):
            raise ValueError(f"Invalid date format (expected YYYY-MM-DD): {e}")
        raise


async def handle_add_journal_entry(
    config: Config,
    content: str,
    title: Optional[str] = None,
    tags: Optional[list[str]] = None,
    github_username: Optional[str] = None,
) -> dict:
    """Add a journal entry."""
    username = resolve_username(config, github_username)
    if isinstance(username, dict):
        return username

    now = utc_now()

    try:
        _write_journal_entry(username, now, title, content, tags)
        logger.info(f"Added journal entry for {username}")

        return {
            "success": True,
            "github_username": username,
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M"),
        }
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"Failed to add journal entry for {username}: {e}")
        return {"error": f"Failed to save entry: {e}"}


async def handle_get_journal_entries(
    config: Config,
    days: int = 30,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    tags: Optional[list[str]] = None,
    github_username: Optional[str] = None,
) -> dict:
    """Get journal entries within a date range."""
    username = resolve_username(config, github_username)
    if isinstance(username, dict):
        return username

    try:
        since, until = _get_date_range(days, start_date, end_date)
    except ValueError as e:
        return {"error": str(e)}

    journal_dir = _get_journal_dir(username)
    if not journal_dir.exists():
        return {
            "github_username": username,
            "start_date": since.strftime("%Y-%m-%d"),
            "end_date": until.strftime("%Y-%m-%d"),
            "entries_by_date": [],
            "count": 0,
        }

    # Performance optimization: only check files that exist
    entries_by_date = []

    # Get list of actual journal files in the directory
    if journal_dir.exists():
        journal_files = sorted(journal_dir.glob("*.md"))

        for file_path in journal_files:
            try:
                date_str = file_path.stem
                date = datetime.fromisoformat(date_str).date()

                # Check if date is in range
                if since.date() <= date <= until.date():
                    entries = _parse_journal_file(file_path)

                    # Filter by tags if specified
                    if tags:
                        entries = [
                            e for e in entries
                            if any(tag in e.get("tags", []) for tag in tags)
                        ]

                    if entries:
                        entries_by_date.append({
                            "date": date.isoformat(),
                            "entries": entries,
                        })
            except (ValueError, OSError) as e:
                logger.warning(f"Skipping invalid journal file {file_path}: {e}")
                continue

    total_entries = sum(len(d["entries"]) for d in entries_by_date)

    logger.debug(f"Retrieved {total_entries} journal entries for {username}")

    return {
        "github_username": username,
        "start_date": since.strftime("%Y-%m-%d"),
        "end_date": until.strftime("%Y-%m-%d"),
        "entries_by_date": entries_by_date,
        "count": total_entries,
    }


async def handle_search_journal(
    config: Config,
    query: str,
    days: int = 90,
    github_username: Optional[str] = None,
) -> dict:
    """Search journal entries by keyword."""
    username = resolve_username(config, github_username)
    if isinstance(username, dict):
        return username

    if days <= 0 or days > 365:
        return {"error": "days must be between 1 and 365"}

    now = utc_now()
    since = now - timedelta(days=days)

    journal_dir = _get_journal_dir(username)
    if not journal_dir.exists():
        return {
            "github_username": username,
            "query": query,
            "matches": [],
            "count": 0,
        }

    query_lower = query.lower()
    matches = []

    # Performance optimization: only check files in date range
    if journal_dir.exists():
        journal_files = sorted(journal_dir.glob("*.md"))

        for file_path in journal_files:
            try:
                date_str = file_path.stem
                date = datetime.fromisoformat(date_str).date()

                # Check if date is in range
                if since.date() <= date <= now.date():
                    entries = _parse_journal_file(file_path)

                    for entry in entries:
                        # Check if query matches title or content
                        title_match = entry.get("title") and query_lower in entry["title"].lower()
                        content_match = query_lower in entry["content"].lower()

                        if title_match or content_match:
                            preview = entry["content"][:PREVIEW_LENGTH]
                            if len(entry["content"]) > PREVIEW_LENGTH:
                                preview += "..."

                            matches.append({
                                "date": date.isoformat(),
                                "time": entry.get("time"),
                                "title": entry.get("title"),
                                "content_preview": preview,
                                "tags": entry.get("tags", []),
                            })
            except (ValueError, OSError) as e:
                logger.warning(f"Skipping invalid journal file {file_path}: {e}")
                continue

    logger.debug(f"Found {len(matches)} matches for '{query}' in {username}'s journal")

    return {
        "github_username": username,
        "query": query,
        "matches": matches,
        "count": len(matches),
    }
