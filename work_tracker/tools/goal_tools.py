"""MCP tools for personal goal tracking."""

import json
import logging
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from mcp.types import Tool

from ..models import Config, Goal, GoalKeyResult
from ..utils import (
    GOAL_ID_MAX_LENGTH,
    MAX_GOALS_PER_USER,
    resolve_username,
    sanitize_username_for_filesystem,
    utc_now,
)

logger = logging.getLogger(__name__)

GOALS_DIR = "goals"  # Directory for goal files
GOALS_FILE_VERSION = "1.0"


def get_goal_tools() -> list[Tool]:
    """Return list of goal-related MCP tools."""
    return [
        Tool(
            name="get_goals",
            description="List goals for self or a specified user. Returns active goals with their key results and progress.",
            inputSchema={
                "type": "object",
                "properties": {
                    "github_username": {
                        "type": "string",
                        "description": "GitHub username. If omitted and 'self' is configured, uses self.",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["active", "completed", "archived", "all"],
                        "description": "Filter by goal status. Default: active",
                        "default": "active",
                    },
                },
            },
        ),
        Tool(
            name="add_goal",
            description="Add a new goal with optional key results and target date. Examples: target_date='2026-06-30', '2026-12-31', 'Q2 2026'",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Goal title (must not be empty)",
                    },
                    "description": {
                        "type": "string",
                        "description": "Detailed description of the goal",
                    },
                    "category": {
                        "type": "string",
                        "enum": ["career", "learning", "project", "health", "general"],
                        "description": "Goal category. Default: general",
                        "default": "general",
                    },
                    "target_date": {
                        "type": "string",
                        "description": "Target completion date. Examples: '2026-06-30', 'Q1 2026', '2026-12-31'",
                    },
                    "key_results": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "description": {"type": "string"},
                                "target": {"type": "string"},
                            },
                            "required": ["description"],
                        },
                        "description": "Measurable key results for the goal",
                    },
                    "github_username": {
                        "type": "string",
                        "description": "GitHub username. If omitted and 'self' is configured, uses self.",
                    },
                },
                "required": ["title"],
            },
        ),
        Tool(
            name="update_goal_progress",
            description="Update progress on a goal. Can update status, add a progress note, or update key result progress.",
            inputSchema={
                "type": "object",
                "properties": {
                    "goal_id": {
                        "type": "string",
                        "description": "Goal ID (slug) to update",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["active", "completed", "archived"],
                        "description": "New status for the goal",
                    },
                    "progress_note": {
                        "type": "string",
                        "description": "Add a progress note with today's date",
                    },
                    "key_result_updates": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "index": {"type": "integer", "description": "Key result index (0-based)"},
                                "current": {"type": "string", "description": "Current progress value"},
                                "status": {"type": "string", "enum": ["pending", "in_progress", "completed", "blocked"]},
                            },
                            "required": ["index"],
                        },
                        "description": "Updates to specific key results",
                    },
                    "github_username": {
                        "type": "string",
                        "description": "GitHub username. If omitted and 'self' is configured, uses self.",
                    },
                },
                "required": ["goal_id"],
            },
        ),
        Tool(
            name="get_goal_progress",
            description="Get detailed progress summary for a specific goal or all goals.",
            inputSchema={
                "type": "object",
                "properties": {
                    "goal_id": {
                        "type": "string",
                        "description": "Specific goal ID. If omitted, returns summary for all active goals.",
                    },
                    "github_username": {
                        "type": "string",
                        "description": "GitHub username. If omitted and 'self' is configured, uses self.",
                    },
                },
            },
        ),
    ]


def _get_goals_file_path(github_username: str) -> Path:
    """Get path to user's goals JSON file."""
    safe_username = sanitize_username_for_filesystem(github_username)
    return Path(GOALS_DIR) / f"{safe_username}-goals.json"


def _load_goals(github_username: str) -> list[Goal]:
    """Load goals from JSON file with validation."""
    file_path = _get_goals_file_path(github_username)
    if not file_path.exists():
        logger.debug(f"No goals file found for {github_username}")
        return []

    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        # Check version (for future migrations)
        file_version = data.get("version", "1.0")
        if file_version != GOALS_FILE_VERSION:
            logger.warning(
                f"Goals file version mismatch for {github_username}: "
                f"expected {GOALS_FILE_VERSION}, got {file_version}"
            )

        goals = []
        for i, g in enumerate(data.get("goals", [])):
            try:
                if "id" not in g or "title" not in g:
                    logger.warning(
                        f"Skipping goal {i} for {github_username}: missing required fields"
                    )
                    continue

                key_results = []
                for kr_data in g.get("key_results", []):
                    if "description" not in kr_data:
                        logger.warning(f"Skipping key result without description in goal {g['id']}")
                        continue
                    try:
                        key_results.append(GoalKeyResult(**kr_data))
                    except Exception as e:
                        logger.warning(f"Skipping malformed key result in goal {g['id']}: {e}")
                        continue

                created_at = None
                if g.get("created_at"):
                    try:
                        created_at = datetime.fromisoformat(g["created_at"])
                    except ValueError:
                        logger.warning(f"Invalid created_at in goal {g['id']}")

                updated_at = None
                if g.get("updated_at"):
                    try:
                        updated_at = datetime.fromisoformat(g["updated_at"])
                    except ValueError:
                        logger.warning(f"Invalid updated_at in goal {g['id']}")

                goals.append(Goal(
                    id=g["id"],
                    title=g["title"],
                    description=g.get("description"),
                    category=g.get("category", "general"),
                    target_date=g.get("target_date"),
                    key_results=key_results,
                    status=g.get("status", "active"),
                    created_at=created_at,
                    updated_at=updated_at,
                    progress_notes=g.get("progress_notes", []),
                ))
            except Exception as e:
                logger.warning(f"Skipping malformed goal {i} for {github_username}: {e}")
                continue

        logger.debug(f"Loaded {len(goals)} goals for {github_username}")
        return goals

    except json.JSONDecodeError as e:
        logger.error(f"Corrupted goal file for {github_username}: {e}")
        return []
    except Exception as e:
        logger.error(f"Failed to load goals for {github_username}: {e}")
        return []


def _save_goals(github_username: str, goals: list[Goal]) -> None:
    """Atomic write prevents data corruption from concurrent writes/crashes."""
    file_path = _get_goals_file_path(github_username)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "version": GOALS_FILE_VERSION,
        "github_username": github_username,
        "goals": [
            {
                "id": g.id,
                "title": g.title,
                "description": g.description,
                "category": g.category,
                "target_date": g.target_date,
                "key_results": [
                    {
                        "description": kr.description,
                        "target": kr.target,
                        "current": kr.current,
                        "status": kr.status,
                    }
                    for kr in g.key_results
                ],
                "status": g.status,
                "created_at": g.created_at.isoformat() if g.created_at else None,
                "updated_at": g.updated_at.isoformat() if g.updated_at else None,
                "progress_notes": g.progress_notes,
            }
            for g in goals
        ],
    }

    # Write to temp file first, then atomic rename
    temp_fd, temp_path = tempfile.mkstemp(
        dir=file_path.parent,
        prefix=f".{file_path.name}.",
        suffix=".tmp"
    )

    try:
        with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        # Atomic rename (overwrites destination)
        os.replace(temp_path, file_path)
        logger.debug(f"Saved {len(goals)} goals for {github_username}")
    except Exception:
        # Clean up temp file on error
        try:
            os.unlink(temp_path)
        except:
            pass
        raise


def _generate_goal_id(title: str) -> str:
    """Slugified title, ensuring unique IDs for duplicate titles."""
    if not title or not title.strip():
        raise ValueError("Goal title cannot be empty")

    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")

    if not slug:
        raise ValueError(f"Goal title '{title}' produces invalid ID (no alphanumeric characters)")

    return slug[:GOAL_ID_MAX_LENGTH]


async def handle_get_goals(
    config: Config,
    github_username: Optional[str] = None,
    status: str = "active",
) -> dict:
    """Get goals for a user."""
    username = resolve_username(config, github_username)
    if isinstance(username, dict):
        return username

    goals = _load_goals(username)

    if status != "all":
        goals = [g for g in goals if g.status == status]

    return {
        "github_username": username,
        "goals": [
            {
                "id": g.id,
                "title": g.title,
                "description": g.description,
                "category": g.category,
                "target_date": g.target_date,
                "status": g.status,
                "key_results": [
                    {
                        "description": kr.description,
                        "target": kr.target,
                        "current": kr.current,
                        "status": kr.status,
                    }
                    for kr in g.key_results
                ],
                "progress_notes_count": len(g.progress_notes),
            }
            for g in goals
        ],
        "count": len(goals),
    }


async def handle_add_goal(
    config: Config,
    title: str,
    description: Optional[str] = None,
    category: str = "general",
    target_date: Optional[str] = None,
    key_results: Optional[list[dict]] = None,
    github_username: Optional[str] = None,
) -> dict:
    """Add a new goal with validation and limits."""
    username = resolve_username(config, github_username)
    if isinstance(username, dict):
        return username

    # Validate title
    try:
        goal_id = _generate_goal_id(title)
    except ValueError as e:
        return {"error": str(e)}

    goals = _load_goals(username)

    # Check limit
    active_goals = [g for g in goals if g.status == "active"]
    if len(active_goals) >= MAX_GOALS_PER_USER:
        return {
            "error": f"Maximum of {MAX_GOALS_PER_USER} active goals reached. "
            "Archive or complete some goals first."
        }

    now = utc_now()

    # Ensure unique ID
    existing_ids = {g.id for g in goals}
    original_id = goal_id
    if goal_id in existing_ids:
        suffix = 1
        while f"{goal_id}-{suffix}" in existing_ids:
            suffix += 1
        goal_id = f"{goal_id}-{suffix}"
        logger.debug(f"Goal ID collision for '{title}': {original_id} -> {goal_id}")

    krs = []
    if key_results:
        for kr in key_results:
            if "description" in kr:
                krs.append(GoalKeyResult(
                    description=kr["description"],
                    target=kr.get("target"),
                ))

    goal = Goal(
        id=goal_id,
        title=title,
        description=description,
        category=category,
        target_date=target_date,
        key_results=krs,
        status="active",
        created_at=now,
        updated_at=now,
    )

    goals.append(goal)
    _save_goals(username, goals)

    logger.info(f"Added goal '{title}' (id: {goal_id}) for {username}")

    return {
        "success": True,
        "github_username": username,
        "goal": {
            "id": goal.id,
            "title": goal.title,
            "category": goal.category,
            "key_results_count": len(goal.key_results),
        },
    }


async def handle_update_goal_progress(
    config: Config,
    goal_id: str,
    status: Optional[str] = None,
    progress_note: Optional[str] = None,
    key_result_updates: Optional[list[dict]] = None,
    github_username: Optional[str] = None,
) -> dict:
    """Update progress on a goal."""
    username = resolve_username(config, github_username)
    if isinstance(username, dict):
        return username

    goals = _load_goals(username)
    goal = next((g for g in goals if g.id == goal_id), None)

    if not goal:
        return {"error": f"Goal not found: {goal_id}"}

    now = utc_now()
    changes = []

    if status:
        old_status = goal.status
        goal.status = status
        changes.append(f"Status updated: {old_status} -> {status}")
        logger.debug(f"Goal {goal_id} status: {old_status} -> {status}")

    if progress_note:
        goal.progress_notes.append({
            "date": now.strftime("%Y-%m-%d"),
            "note": progress_note,
        })
        changes.append("Progress note added")
        logger.debug(f"Added progress note to goal {goal_id}")

    if key_result_updates:
        for update in key_result_updates:
            idx = update["index"]
            if 0 <= idx < len(goal.key_results):
                kr = goal.key_results[idx]
                if "current" in update:
                    kr.current = update["current"]
                if "status" in update:
                    kr.status = update["status"]
                changes.append(f"Key result #{idx} updated")
            else:
                logger.warning(f"Invalid key result index {idx} for goal {goal_id}")

    if changes:
        goal.updated_at = now
        _save_goals(username, goals)
        logger.info(f"Updated goal {goal_id} for {username}: {', '.join(changes)}")

    return {
        "success": True,
        "goal_id": goal_id,
        "changes": changes,
    }


async def handle_get_goal_progress(
    config: Config,
    goal_id: Optional[str] = None,
    github_username: Optional[str] = None,
) -> dict:
    """Get detailed progress summary."""
    username = resolve_username(config, github_username)
    if isinstance(username, dict):
        return username

    goals = _load_goals(username)

    if goal_id:
        goal = next((g for g in goals if g.id == goal_id), None)
        if not goal:
            return {"error": f"Goal not found: {goal_id}"}
        goals = [goal]
    else:
        goals = [g for g in goals if g.status == "active"]

    summaries = []
    for g in goals:
        completed_krs = sum(1 for kr in g.key_results if kr.status == "completed")
        total_krs = len(g.key_results)

        summaries.append({
            "id": g.id,
            "title": g.title,
            "status": g.status,
            "target_date": g.target_date,
            "key_results_progress": f"{completed_krs}/{total_krs}",
            "key_results": [
                {
                    "description": kr.description,
                    "target": kr.target,
                    "current": kr.current,
                    "status": kr.status,
                }
                for kr in g.key_results
            ],
            "recent_notes": g.progress_notes[-5:] if g.progress_notes else [],
        })

    return {
        "github_username": username,
        "goals": summaries,
        "summary": {
            "active_goals": len([s for s in summaries if s["status"] == "active"]),
            "total_key_results": sum(len(s["key_results"]) for s in summaries),
            "completed_key_results": sum(
                sum(1 for kr in s["key_results"] if kr["status"] == "completed")
                for s in summaries
            ),
        },
    }
