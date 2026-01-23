"""Competency mapping engine for EGF competencies."""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class Competency(str, Enum):
    """EGF competency areas."""
    EXECUTION_DELIVERY = "Execution & Delivery"
    SKILLS_KNOWLEDGE = "Skills & Knowledge"
    TEAMWORK_COMMUNICATION = "Teamwork & Communication"
    INFLUENCE_LEADERSHIP = "Influence & Leadership"


class EvidenceLevel(str, Enum):
    """Strength of evidence for a competency signal."""
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"


@dataclass
class CompetencyEvidence:
    """Evidence supporting a competency signal."""
    competency: Competency
    level: EvidenceLevel
    signal_type: str  # e.g., "pr_pattern", "review_activity", "breadth"
    reasoning: str
    sources: list[dict] = field(default_factory=list)  # [{"type": "pr", "title": ..., "url": ...}]


# Patterns for detecting competency signals in PR titles/descriptions
COMPETENCY_PATTERNS = {
    Competency.EXECUTION_DELIVERY: [
        (r"\b(fix|bug|patch|hotfix|resolve)\b", "Bug fixes demonstrate debugging skills", EvidenceLevel.MODERATE),
        (r"\b(implement|add|create|build|ship)\b", "New feature delivery", EvidenceLevel.MODERATE),
        (r"\b(refactor|optimize|improve|performance)\b", "Code improvement work", EvidenceLevel.MODERATE),
        (r"\b(migrate|upgrade|update)\b", "System modernization", EvidenceLevel.MODERATE),
        (r"\b(release|deploy|rollout)\b", "Release management", EvidenceLevel.STRONG),
    ],
    Competency.SKILLS_KNOWLEDGE: [
        (r"\b(architecture|design|pattern)\b", "Architectural thinking", EvidenceLevel.STRONG),
        (r"\b(security|auth|encryption|vulnerability)\b", "Security expertise", EvidenceLevel.STRONG),
        (r"\b(test|testing|coverage|spec)\b", "Testing discipline", EvidenceLevel.MODERATE),
        (r"\b(api|endpoint|graphql|rest)\b", "API design skills", EvidenceLevel.MODERATE),
        (r"\b(database|query|index|schema)\b", "Database knowledge", EvidenceLevel.MODERATE),
        (r"\b(cache|redis|memcached)\b", "Caching knowledge", EvidenceLevel.MODERATE),
        (r"\b(docker|kubernetes|k8s|container)\b", "Container expertise", EvidenceLevel.STRONG),
        (r"\b(ci|cd|pipeline|workflow)\b", "DevOps skills", EvidenceLevel.MODERATE),
    ],
    Competency.TEAMWORK_COMMUNICATION: [
        (r"\b(doc|docs|documentation|readme)\b", "Documentation work", EvidenceLevel.MODERATE),
        (r"\b(review|feedback|suggestion)\b", "Review engagement", EvidenceLevel.WEAK),
        (r"\b(pair|collaborate|together)\b", "Collaboration signals", EvidenceLevel.MODERATE),
    ],
    Competency.INFLUENCE_LEADERSHIP: [
        (r"\b(rfc|proposal|design doc)\b", "Technical proposals", EvidenceLevel.STRONG),
        (r"\b(mentor|onboard|guide)\b", "Mentorship signals", EvidenceLevel.STRONG),
        (r"\b(initiative|project|epic)\b", "Project leadership", EvidenceLevel.MODERATE),
        (r"\b(standard|convention|pattern)\b", "Setting standards", EvidenceLevel.MODERATE),
    ],
}


def analyze_pr_for_competencies(pr_title: str, pr_description: str | None = None) -> list[CompetencyEvidence]:
    """Analyze a PR title and description for competency signals.

    Args:
        pr_title: PR title text.
        pr_description: Optional PR description/body text.

    Returns:
        List of competency evidence items found.
    """
    evidence = []
    text = f"{pr_title} {pr_description or ''}".lower()

    for competency, patterns in COMPETENCY_PATTERNS.items():
        for pattern, reasoning, level in patterns:
            # Text is already lowercased, no need for IGNORECASE
            if re.search(pattern, text):
                evidence.append(CompetencyEvidence(
                    competency=competency,
                    level=level,
                    signal_type="pr_pattern",
                    reasoning=reasoning,
                    sources=[{"type": "pr_title", "text": pr_title}],
                ))
                break  # Only one match per competency per PR

    return evidence


def analyze_contributions_for_competencies(
    prs_merged: list[dict],
    reviews_given: list[dict],
    distribution: dict | None = None,
    review_turnaround: dict | None = None,
) -> dict:
    """Analyze contribution data to map to EGF competencies.

    Args:
        prs_merged: List of merged PRs.
        reviews_given: List of code reviews given.
        distribution: Optional distribution data (by_repo, by_area).
        review_turnaround: Optional review turnaround metrics.

    Returns:
        Dict mapping competencies to evidence lists and scores.
    """
    results = {
        competency.value: {
            "evidence": [],
            "evidence_count": 0,
            "score": 0,  # 0-100 based on evidence strength
        }
        for competency in Competency
    }

    # Analyze PR titles for patterns
    for pr in prs_merged:
        title = pr.get("title", "")
        for ev in analyze_pr_for_competencies(title):
            results[ev.competency.value]["evidence"].append({
                "signal_type": ev.signal_type,
                "level": ev.level.value,
                "reasoning": ev.reasoning,
                "source": {"type": "pr", "title": title, "url": pr.get("url", "")},
            })

    # Execution & Delivery: volume of merged work
    pr_count = len(prs_merged)
    if pr_count >= 10:
        results[Competency.EXECUTION_DELIVERY.value]["evidence"].append({
            "signal_type": "volume",
            "level": EvidenceLevel.STRONG.value,
            "reasoning": f"Merged {pr_count} PRs, demonstrating consistent delivery",
        })
    elif pr_count >= 5:
        results[Competency.EXECUTION_DELIVERY.value]["evidence"].append({
            "signal_type": "volume",
            "level": EvidenceLevel.MODERATE.value,
            "reasoning": f"Merged {pr_count} PRs, showing solid output",
        })

    # Teamwork & Communication: review activity
    review_count = len(reviews_given)
    if review_count >= 15:
        results[Competency.TEAMWORK_COMMUNICATION.value]["evidence"].append({
            "signal_type": "review_activity",
            "level": EvidenceLevel.STRONG.value,
            "reasoning": f"Provided {review_count} code reviews, actively supporting teammates",
        })
    elif review_count >= 5:
        results[Competency.TEAMWORK_COMMUNICATION.value]["evidence"].append({
            "signal_type": "review_activity",
            "level": EvidenceLevel.MODERATE.value,
            "reasoning": f"Provided {review_count} code reviews",
        })

    # Review turnaround as indicator of responsiveness
    if review_turnaround:
        avg_hours = review_turnaround.get("avg_hours")
        if avg_hours is not None:
            if avg_hours <= 4:
                results[Competency.TEAMWORK_COMMUNICATION.value]["evidence"].append({
                    "signal_type": "responsiveness",
                    "level": EvidenceLevel.STRONG.value,
                    "reasoning": f"Average review turnaround of {avg_hours:.1f} hours shows excellent responsiveness",
                })
            elif avg_hours <= 12:
                results[Competency.TEAMWORK_COMMUNICATION.value]["evidence"].append({
                    "signal_type": "responsiveness",
                    "level": EvidenceLevel.MODERATE.value,
                    "reasoning": f"Average review turnaround of {avg_hours:.1f} hours shows good responsiveness",
                })

    # Skills & Knowledge: breadth across repos/areas
    if distribution:
        by_repo = distribution.get("by_repo", {})
        by_area = distribution.get("by_area", {})

        if len(by_repo) >= 5:
            results[Competency.SKILLS_KNOWLEDGE.value]["evidence"].append({
                "signal_type": "breadth",
                "level": EvidenceLevel.STRONG.value,
                "reasoning": f"Contributed to {len(by_repo)} repositories, showing broad codebase familiarity",
            })
        elif len(by_repo) >= 3:
            results[Competency.SKILLS_KNOWLEDGE.value]["evidence"].append({
                "signal_type": "breadth",
                "level": EvidenceLevel.MODERATE.value,
                "reasoning": f"Contributed to {len(by_repo)} repositories",
            })

        # Multi-area expertise
        if len(by_area) >= 3:
            area_list = ", ".join(list(by_area.keys())[:4])
            results[Competency.SKILLS_KNOWLEDGE.value]["evidence"].append({
                "signal_type": "versatility",
                "level": EvidenceLevel.STRONG.value,
                "reasoning": f"Work spans multiple areas: {area_list}",
            })

    # Influence & Leadership: ratio of reviews to PRs (helping others vs own work)
    if pr_count > 0 and review_count > 0:
        review_ratio = review_count / pr_count
        if review_ratio >= 2.0:
            results[Competency.INFLUENCE_LEADERSHIP.value]["evidence"].append({
                "signal_type": "mentorship_ratio",
                "level": EvidenceLevel.MODERATE.value,
                "reasoning": f"Review-to-PR ratio of {review_ratio:.1f}x suggests significant investment in helping teammates",
            })

    # Calculate scores based on evidence
    for competency in results:
        evidence_list = results[competency]["evidence"]
        results[competency]["evidence_count"] = len(evidence_list)

        # Score: weighted by evidence level
        score = 0
        for ev in evidence_list:
            level = ev.get("level", "weak")
            if level == "strong":
                score += 30
            elif level == "moderate":
                score += 15
            else:
                score += 5
        results[competency]["score"] = min(score, 100)

    return results


def get_competency_summary(analysis: dict) -> dict:
    """Generate a summary of competency analysis.

    Args:
        analysis: Output from analyze_contributions_for_competencies.

    Returns:
        Summary with top competencies and gaps.
    """
    # Sort competencies by score
    sorted_competencies = sorted(
        [(c, data["score"], data["evidence_count"]) for c, data in analysis.items()],
        key=lambda x: (x[1], x[2]),
        reverse=True,
    )

    # Identify strengths (score >= 50) and gaps (score < 20)
    strengths = [c for c, score, _ in sorted_competencies if score >= 50]
    growth_areas = [c for c, score, _ in sorted_competencies if score < 20]

    return {
        "top_competencies": [{"competency": c, "score": s} for c, s, _ in sorted_competencies[:2]],
        "strengths": strengths,
        "growth_areas": growth_areas,
        "scores": {c: s for c, s, _ in sorted_competencies},
    }
