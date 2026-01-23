---
description: This skill writes performance reviews for team members. Use when asked to "write performance review", "draft review", "create perf review", "evaluate performance", or "review feedback for [name]".
allowed-tools:
  - mcp__ic-tracker__get_github_contributions
  - mcp__ic-tracker__get_confluence_contributions
  - mcp__ic-tracker__get_team_members
  - mcp__ic-tracker__get_contribution_trends
  - mcp__ic-tracker__get_contribution_distribution
  - mcp__ic-tracker__get_competency_analysis
  - mcp__ic-tracker__get_peer_feedback
  - mcp__ic-tracker__get_team_bandwidth
  - mcp__ic-tracker__search_jira_issues
  - mcp__ic-tracker__get_initiative_roadmap
  - Read
  - Glob
---

# Performance Review Skill

Generate a comprehensive performance review using contribution data and documented goals.

## Workflow

1. **Identify the team member**
   - Use `mcp__ic-tracker__get_team_members` to get available members
   - If not specified, ask user which team member to review

2. **Read the EGF reference documents**
   - Read `references/engineering-growth-framework.md` for role expectations and competencies
   - Read `references/engineering-growth-rubric.md` for detailed behavioral criteria at each level

3. **Parse date range and gather contribution data**
   - Parse any date range from the user's request (see Date Ranges section below)
   - If no date range specified, default to last 90 days
   - Convert named ranges to explicit `start_date` and `end_date` parameters
   - `mcp__ic-tracker__get_github_contributions` - PRs, reviews, lines changed, review turnaround
   - `mcp__ic-tracker__get_confluence_contributions` - docs created/updated
   - `mcp__ic-tracker__get_contribution_trends` - week-over-week or monthly trends
   - `mcp__ic-tracker__get_contribution_distribution` - work areas and repo breadth
   - `mcp__ic-tracker__get_competency_analysis` - EGF competency mapping

4. **Gather peer feedback (if available)**
   - `mcp__ic-tracker__get_peer_feedback` - read structured feedback from peers
   - Incorporate feedback themes into strengths and growth areas

5. **Read the team member's goals**
   - Find goal file: `goals/<name>.md`
   - Extract performance goals, key initiatives, key results

6. **Analyze alignment and score goals**
   - Map contributions to documented initiatives
   - Calculate goal alignment scores (see Scoring Methodology below)
   - Identify work supporting stated key results
   - Evaluate against EGF competencies and expected level for their role
   - Note gaps or areas needing attention

7. **Generate review**

## Date Ranges

The skill supports several named date range formats. Parse these from the user's request and resolve to concrete dates.

| Format | Example | Resolution |
|--------|---------|------------|
| Quarter | `Q4 2025`, `Q1` | Q1: Jan 1 - Mar 31, Q2: Apr 1 - Jun 30, Q3: Jul 1 - Sep 30, Q4: Oct 1 - Dec 31 |
| Half | `H1 2025`, `H2` | H1: Jan 1 - Jun 30, H2: Jul 1 - Dec 31 |
| Relative | `last 30 days`, `last 6 months` | Rolling window ending today |
| Year | `2025` | Jan 1 - Dec 31 of that year |
| Explicit | `2025-01-01 to 2025-03-31` | Use dates as provided |
| Default | (none specified) | Last 90 days |

**Resolution rules:**
- If year is omitted (e.g., `Q4`, `H2`), use current year
- For relative ranges, calculate from today's date
- Pass resolved dates as `start_date` and `end_date` (YYYY-MM-DD format) to contribution tools

## Goal Alignment Scoring

For each goal, calculate an alignment score (0-100) using these components:

### Evidence Count (0-40 points)
| PRs/Docs Supporting Goal | Points |
|--------------------------|--------|
| 0 | 0 |
| 1-2 | 10 |
| 3-5 | 20 |
| 6-10 | 30 |
| 11+ | 40 |

### Keyword Relevance (0-30 points)
Match PR titles and documentation against goal keywords:
- Extract keywords from goal title and description
- Score each piece of evidence: Strong match (3 pts), Moderate match (2 pts), Weak match (1 pt)
- Cap at 30 points

### Key Result Progress (0-30 points)
For quantitative key results (KRs):
| % of KR Target Achieved | Points |
|------------------------|--------|
| 0% | 0 |
| 1-25% | 8 |
| 26-50% | 15 |
| 51-75% | 22 |
| 76-100% | 30 |
| >100% | 30 (note as exceeded) |

### Score Interpretation
| Total Score | Status |
|-------------|--------|
| 0-30 | Needs Attention |
| 31-60 | In Progress |
| 61-85 | On Track |
| 86-100 | Exceeded |

### Gap Analysis
For each goal, document:
- Missing evidence types (e.g., "No documentation PRs for this goal")
- Unaddressed key results
- Potential blockers inferred from contribution patterns

## Output Format

```
# Performance Review: [Name]
**Review Period:** [Start Date] - [End Date] ([Named Range if applicable])
**Role:** [Title from goals]

## Summary
[2-3 sentence overview]

## Goal Progress

### [Goal #1: Title]
**Alignment Score:** [X]/100 ([Status])

**Evidence:**
- [Specific PR demonstrating progress]
- [Quantitative metrics]

**Key Result Progress:**
- [KR1]: [Achieved] / [Target] ([%])

**Gap Analysis:** [What's missing or needs attention]

[Repeat for each goal...]

## Contributions Breakdown

### Code Delivery
- PRs Merged: [X]
- Lines Changed: [+X / -Y]
- Review Turnaround: [Avg X hours]
- Key Deliverables: [Notable PRs with context]

### Code Reviews
- Reviews Given: [X]
- Avg Turnaround: [X hours]

### Documentation
- Pages Created/Updated: [X]

### Work Distribution
- Primary Area: [frontend/backend/infra/etc]
- Repos Touched: [X]

### Contribution Trends
[Week-over-week or month-over-month trend analysis]

## Competency Analysis

### [Competency Name] (Score: X/100)
- [Evidence with level and reasoning]

[Repeat for each EGF competency...]

## Peer Feedback Summary
(If available)
- **Common Strengths:** [Themes from peer feedback]
- **Growth Areas Identified:** [Themes from peer feedback]

## Strengths Demonstrated
- [Strength with specific example]

## Growth Opportunities
- [Area for development, constructively framed]

## Recommendation
[Overall assessment and guidance]
```

## Guidelines

- Ground all feedback in specific contributions from the data
- Connect achievements to documented goals and key results
- Use objective language without superlatives
- Reference EGF competencies from the rubric: Execution & Delivery, Skills & Knowledge, Teamwork & Communication, Influence & Leadership
- Use the Engineering Growth Rubric to evaluate demonstrated behaviors at each level
- Reference the Role Framework to set appropriate expectations for the engineer's role/sub-level
- Reference COGIS values when relevant: Camaraderie, Openness, Grit, Integrity, Simplicity
