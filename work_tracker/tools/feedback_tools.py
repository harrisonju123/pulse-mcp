"""MCP tools for peer feedback data."""

import logging
import re
from pathlib import Path

from mcp.types import Tool

from ..models import Config

logger = logging.getLogger(__name__)

# Base directory for feedback files (relative to project root)
FEEDBACK_DIR = "feedback"


def get_feedback_tools() -> list[Tool]:
    """Return list of feedback-related MCP tools."""
    return [
        Tool(
            name="get_peer_feedback",
            description=(
                "Get structured peer feedback for a team member from feedback files. "
                "Reads feedback from feedback/{github_username}/{period}/*.md files."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "github_username": {
                        "type": "string",
                        "description": "GitHub username of the team member",
                    },
                    "period": {
                        "type": "string",
                        "description": "Review period (e.g., '2025-H1', '2025-Q4', '2025'). If not provided, returns all available feedback.",
                    },
                },
                "required": ["github_username"],
            },
        ),
    ]


def _parse_feedback_file(file_path: Path) -> dict | None:
    """Parse a feedback markdown file.

    Expected format:
    ---
    from: <author_name or anonymous>
    relationship: <peer|manager|skip-level|cross-functional>
    date: <YYYY-MM-DD>
    ---

    ## Strengths
    <bullet points>

    ## Growth Areas
    <bullet points>

    ## Other Comments
    <text>

    Args:
        file_path: Path to the feedback markdown file.

    Returns:
        Dict with parsed feedback data, or None if parsing fails.
    """
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to read feedback file {file_path}: {e}")
        return None

    feedback = {
        "file": file_path.name,
        "from": "anonymous",
        "relationship": "peer",
        "date": None,
        "strengths": [],
        "growth_areas": [],
        "comments": "",
    }

    # Parse frontmatter
    frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if frontmatter_match:
        frontmatter = frontmatter_match.group(1)
        for line in frontmatter.strip().split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip().lower()
                value = value.strip()
                if key == "from":
                    feedback["from"] = value
                elif key == "relationship":
                    feedback["relationship"] = value
                elif key == "date":
                    feedback["date"] = value

        content = content[frontmatter_match.end():]

    # Parse sections
    sections = re.split(r"\n##\s+", content)

    for section in sections:
        if not section.strip():
            continue

        lines = section.strip().split("\n")
        header = lines[0].lower().strip()
        body = "\n".join(lines[1:]).strip()

        if "strength" in header:
            # Extract bullet points
            bullets = re.findall(r"^[\-\*]\s*(.+)$", body, re.MULTILINE)
            feedback["strengths"] = [b.strip() for b in bullets if b.strip()]
        elif "growth" in header or "area" in header or "improvement" in header:
            bullets = re.findall(r"^[\-\*]\s*(.+)$", body, re.MULTILINE)
            feedback["growth_areas"] = [b.strip() for b in bullets if b.strip()]
        elif "comment" in header or "other" in header:
            feedback["comments"] = body

    return feedback


async def handle_get_peer_feedback(
    config: Config,
    github_username: str,
    period: str | None = None,
) -> dict:
    """Get peer feedback for a team member.

    Args:
        config: Application configuration.
        github_username: GitHub username.
        period: Optional review period (e.g., '2025-H1').

    Returns:
        Dict containing structured peer feedback.
    """
    if github_username not in config.team_members:
        return {
            "error": f"Unknown team member: {github_username}. "
            f"Available: {', '.join(config.team_members.keys())}"
        }

    # Sanitize username to prevent path traversal
    if not re.match(r"^[a-zA-Z0-9_-]+$", github_username):
        return {"error": "Invalid github_username format"}

    member = config.team_members[github_username]

    # Build path to feedback directory
    feedback_base = Path(FEEDBACK_DIR) / github_username

    if not feedback_base.exists():
        return {
            "member_name": member.name,
            "github_username": github_username,
            "feedback": [],
            "summary": {
                "total_feedback_count": 0,
                "periods_available": [],
            },
            "note": f"No feedback directory found at {feedback_base}",
        }

    # Find available periods
    available_periods = []
    if feedback_base.is_dir():
        for item in feedback_base.iterdir():
            if item.is_dir():
                available_periods.append(item.name)

    # Determine which periods to read
    if period:
        periods_to_read = [period] if period in available_periods else []
        if not periods_to_read:
            return {
                "member_name": member.name,
                "github_username": github_username,
                "feedback": [],
                "summary": {
                    "total_feedback_count": 0,
                    "periods_available": available_periods,
                },
                "note": f"No feedback found for period '{period}'. Available periods: {available_periods}",
            }
    else:
        periods_to_read = available_periods

    # Read feedback files
    all_feedback = []
    for period_name in periods_to_read:
        period_dir = feedback_base / period_name
        if not period_dir.is_dir():
            continue

        for file_path in period_dir.glob("*.md"):
            feedback_data = _parse_feedback_file(file_path)
            if feedback_data:
                feedback_data["period"] = period_name
                all_feedback.append(feedback_data)

    # Aggregate feedback
    all_strengths = []
    all_growth_areas = []
    relationship_breakdown = {}

    for fb in all_feedback:
        all_strengths.extend(fb.get("strengths", []))
        all_growth_areas.extend(fb.get("growth_areas", []))

        rel = fb.get("relationship", "peer")
        relationship_breakdown[rel] = relationship_breakdown.get(rel, 0) + 1

    # Find common themes (simple frequency analysis)
    def find_themes(items: list[str], min_count: int = 2) -> list[dict]:
        word_freq: dict[str, int] = {}
        for item in items:
            words = re.findall(r"\b\w{4,}\b", item.lower())
            for word in words:
                word_freq[word] = word_freq.get(word, 0) + 1

        themes = [
            {"keyword": word, "mentions": count}
            for word, count in sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
            if count >= min_count
        ]
        return themes[:5]

    result = {
        "member_name": member.name,
        "github_username": github_username,
        "period": period if period else "all",
        "feedback": all_feedback,
        "summary": {
            "total_feedback_count": len(all_feedback),
            "periods_available": available_periods,
            "relationship_breakdown": relationship_breakdown,
            "all_strengths": all_strengths,
            "all_growth_areas": all_growth_areas,
            "strength_themes": find_themes(all_strengths),
            "growth_themes": find_themes(all_growth_areas),
        },
    }

    return result
