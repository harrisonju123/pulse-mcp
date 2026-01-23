"""Competency mapping engine for EGF competencies."""

import logging
import math
import re
from collections import defaultdict
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


# Level expectations: threshold score expected at each level for each competency
LEVEL_EXPECTATIONS = {
    "P2": {
        "Execution & Delivery": 35,
        "Skills & Knowledge": 30,
        "Teamwork & Communication": 30,
        "Influence & Leadership": 15,
    },
    "P3": {
        "Execution & Delivery": 45,
        "Skills & Knowledge": 40,
        "Teamwork & Communication": 40,
        "Influence & Leadership": 25,
    },
    "P4": {
        "Execution & Delivery": 55,
        "Skills & Knowledge": 55,
        "Teamwork & Communication": 50,
        "Influence & Leadership": 45,
    },
    "P5": {
        "Execution & Delivery": 60,
        "Skills & Knowledge": 65,
        "Teamwork & Communication": 55,
        "Influence & Leadership": 60,
    },
}


def calculate_impact_score(evidence_list: list[dict], prs_merged: list[dict] | None = None) -> float:
    """Calculate impact multiplier based on complexity signals.

    Analyzes evidence and PR data for signals of high-impact work like
    large PRs, cross-repo work, and architecture/design contributions.

    Args:
        evidence_list: List of evidence dicts with source info.
        prs_merged: Optional list of merged PRs with additions/deletions.

    Returns:
        Impact multiplier in range 0.8-1.2
    """
    impact_signals = 0

    for ev in evidence_list:
        source = ev.get("source", {})

        # Large PRs (500+ lines)
        additions = source.get("additions", 0)
        if additions >= 1000:
            impact_signals += 2
        elif additions >= 500:
            impact_signals += 1

        # Cross-repo work
        if "cross-repo" in ev.get("reasoning", "").lower():
            impact_signals += 1

        # Architecture/design work
        if ev.get("signal_type") == "pr_pattern":
            title = source.get("title", "").lower()
            if any(kw in title for kw in ["architect", "design", "rfc", "proposal"]):
                impact_signals += 2

    # Also check PRs directly for large contributions
    if prs_merged:
        for pr in prs_merged:
            additions = pr.get("additions", 0)
            if additions >= 1000:
                impact_signals += 1
            elif additions >= 500:
                impact_signals += 0.5

    # Map to 0.8-1.2 range
    return 0.8 + min(impact_signals, 4) * 0.1


def calculate_competency_score(evidence_list: list[dict], impact_multiplier: float = 1.0) -> int:
    """Calculate competency score with diminishing returns and impact weighting.

    Uses a diminishing returns model where repeated evidence of the same type
    contributes less to the score. Applies soft cap at 85.

    Args:
        evidence_list: List of evidence dicts with level and signal_type.
        impact_multiplier: Multiplier from calculate_impact_score (0.8-1.2).

    Returns:
        Score in range 0-85 (reserve 85+ for exceptional cases)
    """
    if not evidence_list:
        return 0

    # Base score from evidence (diminishing returns)
    base_score = 0.0
    evidence_by_type: dict[str, list] = defaultdict(list)

    for ev in evidence_list:
        signal_type = ev.get("signal_type", "unknown")
        evidence_by_type[signal_type].append(ev)

        # Point values with diminishing returns per signal type
        type_count = len(evidence_by_type[signal_type])
        diminishing_factor = 1 / (1 + 0.3 * (type_count - 1))  # 1.0, 0.77, 0.63, 0.53...

        level_points = {"strong": 20, "moderate": 12, "weak": 5}
        points = level_points.get(ev.get("level", "weak"), 5)
        base_score += points * diminishing_factor

    # Diversity bonus (breadth across signal types)
    unique_types = len(evidence_by_type)
    diversity_bonus = min(unique_types * 3, 15)  # Max 15 points for 5+ types

    # Combine and apply impact
    raw_score = (base_score + diversity_bonus) * impact_multiplier

    # Soft cap at 85 (sigmoid-like compression above 60)
    if raw_score > 60:
        excess = raw_score - 60
        compressed = 60 + (25 * (1 - math.exp(-excess / 30)))  # Asymptotically approaches 85
        return min(int(compressed), 85)

    return min(int(raw_score), 85)


def get_score_label(score: int) -> str:
    """Map score to human-readable label.

    Args:
        score: Competency score (0-85).

    Returns:
        Label string: Gap, Developing, Proficient, Strong, or Exceptional
    """
    if score >= 76:
        return "Exceptional"
    elif score >= 61:
        return "Strong"
    elif score >= 41:
        return "Proficient"
    elif score >= 21:
        return "Developing"
    else:
        return "Gap"


def get_vs_target_label(score: int, competency: str, level: str | None) -> str | None:
    """Determine if score meets level expectations.

    Args:
        score: Competency score.
        competency: Competency name.
        level: Engineer level (P2, P3, P4, P5) or None.

    Returns:
        Label: "Exceeding", "Meeting", "Developing", "Gap", or None if no level.
    """
    if not level or level not in LEVEL_EXPECTATIONS:
        return None

    threshold = LEVEL_EXPECTATIONS[level].get(competency, 50)

    if score >= threshold + 15:
        return "Exceeding"
    elif score >= threshold:
        return "Meeting"
    elif score >= threshold - 15:
        return "Developing"
    else:
        return "Gap"


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
    level: str | None = None,
) -> dict:
    """Analyze contribution data to map to EGF competencies.

    Args:
        prs_merged: List of merged PRs (may include additions/deletions stats).
        reviews_given: List of code reviews given.
        distribution: Optional distribution data (by_repo, by_area).
        review_turnaround: Optional review turnaround metrics.
        level: Optional engineer level (P2, P3, P4, P5) for relative scoring.

    Returns:
        Dict mapping competencies to evidence lists, scores, and labels.
    """
    results = {
        competency.value: {
            "evidence": [],
            "evidence_count": 0,
            "score": 0,
            "score_label": "Gap",
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

    # Calculate impact multiplier from PR stats
    all_evidence = []
    for competency_data in results.values():
        all_evidence.extend(competency_data["evidence"])
    impact_multiplier = calculate_impact_score(all_evidence, prs_merged)

    # Calculate scores using new algorithm with diminishing returns
    for competency_name in results:
        evidence_list = results[competency_name]["evidence"]
        results[competency_name]["evidence_count"] = len(evidence_list)

        # Calculate score with diminishing returns and impact weighting
        score = calculate_competency_score(evidence_list, impact_multiplier)
        results[competency_name]["score"] = score
        results[competency_name]["score_label"] = get_score_label(score)

        # Add level-relative comparison if level is provided
        vs_target = get_vs_target_label(score, competency_name, level)
        if vs_target:
            results[competency_name]["vs_target"] = vs_target

    return results


def get_competency_summary(analysis: dict) -> dict:
    """Generate a summary of competency analysis.

    Args:
        analysis: Output from analyze_contributions_for_competencies.

    Returns:
        Summary with top competencies, gaps, and score labels.
    """
    # Sort competencies by score
    sorted_competencies = sorted(
        [
            (c, data["score"], data["evidence_count"], data.get("score_label", "Gap"))
            for c, data in analysis.items()
        ],
        key=lambda x: (x[1], x[2]),
        reverse=True,
    )

    # Identify strengths (score >= 50) and gaps (score < 30)
    # New thresholds: strengths at Proficient+, gaps at Developing or below
    strengths = [c for c, score, _, _ in sorted_competencies if score >= 50]
    growth_areas = [c for c, score, _, _ in sorted_competencies if score < 30]

    return {
        "top_competencies": [
            {"competency": c, "score": s, "label": label}
            for c, s, _, label in sorted_competencies[:2]
        ],
        "strengths": strengths,
        "growth_areas": growth_areas,
        "scores": {c: s for c, s, _, _ in sorted_competencies},
        "labels": {c: label for c, _, _, label in sorted_competencies},
    }
