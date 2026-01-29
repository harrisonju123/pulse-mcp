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
Volume alone does not indicate exceptional performance. Score based on **quality and ownership**, not just count.

| PRs/Docs Supporting Goal | Points | Notes |
|--------------------------|--------|-------|
| 0 | 0 | No evidence |
| 1-2 | 10 | Minimal engagement |
| 3-5 | 15 | Some evidence |
| 6-10 | 20 | Consistent execution |
| 11+ with execution only | 25 | High volume, but assigned work only |
| 6+ with ownership evidence | 35 | Drove decisions, scoped work, identified gaps |
| 11+ with ownership evidence | 40 | Led initiative with high output |

**Ownership evidence includes:** Scoping work independently, identifying gaps before being asked, driving technical decisions, leading cross-team coordination, mentoring others on the work.

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
| 0-25 | Needs Attention |
| 26-50 | In Progress |
| 51-70 | On Track |
| 71-85 | Strong |
| 86-100 | Exceeded (rare) |

**Note:** "On Track" represents solid, reliable work meeting expectations. "Exceeded" is rare and requires demonstrated ownership, initiative, and impact beyond assigned work.

## Calibration Philosophy

Scoring should be conservative and defensible. Default to "Meets Expectations" for solid work.

### Core Principles
- **"Meets Expectations" is the baseline for solid performers.** Reliably completing assigned work well is expected, not exceptional.
- **"Exceeds" requires demonstrated ownership, initiative, and impact beyond assigned work.** This is rare and should be reserved for clear evidence of going above and beyond.
- **Executing tickets well ≠ exceeding expectations.** Completing assigned Jira tickets, even many of them, demonstrates execution—not ownership.
- **Avoid score inflation.** Do not give high scores simply because there were many PRs or the work was technically complex.
- **Avoid upward trajectory language unless strongly warranted.** Phrases like "trending toward Exceeds" or "on track for promotion" require exceptional evidence.

### Ownership vs Execution

| Type | Definition | Scoring Impact |
|------|------------|----------------|
| **Execution** | Completing assigned work reliably and with quality | Baseline expectation (On Track) |
| **Ownership** | Scoping work independently, identifying gaps, driving technical decisions, leading workstreams, mentoring | Required for Strong/Exceeded scores |

High scores require ownership evidence, not just execution volume. Examples of ownership:
- Identified and scoped a technical initiative before being asked
- Drove architectural decisions with clear rationale
- Led cross-team coordination to unblock work
- Mentored teammates and elevated team capabilities
- Proactively addressed tech debt or operational concerns

### Tenure Modifier

Adjust expectations based on time in role:

| Tenure | Expectation Adjustment |
|--------|------------------------|
| < 6 months | **Cap scores at 60** unless exceptional initiative demonstrated. Acknowledge good ramp-up without inflating scores. At this stage, learning and ramping is expected. |
| 6-12 months | Normal scoring applies. Should be contributing consistently. |
| 12+ months | Higher expectations for ownership and initiative. Execution alone is insufficient for high scores. |

**For newer employees:** Acknowledge positive ramp-up trajectory without framing it as "exceeding." Completing onboarding and learning systems well is the expectation for new hires.

## Competency Score Reinterpretation

The `mcp__ic-tracker__get_competency_analysis` tool returns scores that tend toward inflation. Reinterpret them conservatively:

| Tool Score | Skill Interpretation | Meaning |
|------------|---------------------|---------|
| 0-20 | Gap | Clear development need |
| 21-40 | Developing | Building capability, not yet consistent |
| 41-55 | Solid | Meeting expectations for level |
| 56-70 | Strong | Consistent, reliable performance |
| 71-85 | Very Strong | Above expectations with ownership evidence |
| 86-100 | Exceptional (rare) | Truly outstanding, requires clear evidence |

**Calibration guidance:**
- Volume of PRs alone does not indicate exceptional performance
- Look for evidence of ownership, mentorship, cross-team impact for higher interpretations
- Tenure matters: < 6 months caps at "Solid" unless clear initiative shown
- Tool's "Exceptional" (78+) should often be reinterpreted as "Strong" or "Solid" based on actual evidence

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
**Tenure:** [X months in role]

## Summary
[2-3 sentence overview]

## Goal Progress

### [Goal #1: Title]
**Alignment Score:** [X]/100 ([Needs Attention/In Progress/On Track/Strong/Exceeded])

**Evidence:**
- [Specific PR demonstrating progress]
- [Quantitative metrics]
- **Ownership indicators:** [If any: scoped work, drove decisions, identified gaps | If none: Execution only]

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

### [Competency Name]
**Tool Score:** X/100 → **Calibrated:** [Gap/Developing/Solid/Strong/Very Strong/Exceptional]
- [Evidence with level and reasoning]
- [Ownership indicators if present]

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
**Rating:** [Meets Expectations / Exceeds Expectations / Needs Improvement]

[1-2 sentence summary of overall performance without hedging.]

**To move to [next level]:**
- [Specific, actionable criteria needed to advance]
- [Evidence that would demonstrate advancement]

[If tenure < 6 months: Acknowledge ramp-up progress without implying trajectory toward exceeds.]
```

## Guidelines

### Calibration
- **Default to "Meets Expectations"** for solid performers completing assigned work well
- **Avoid upward trajectory language** ("trending toward Exceeds", "on track for promotion") unless evidence is overwhelming
- **Avoid hedging language** ("nearly", "almost", "could be considered") - give a clear rating
- **Be specific about what would constitute "Exceeds"** - vague potential doesn't count
- **For newer employees:** acknowledge good ramp-up as meeting expectations for their tenure, not as exceeding

### Evidence Standards
- Ground all feedback in specific contributions from the data
- Connect achievements to documented goals and key results
- Use objective language without superlatives
- Distinguish between execution (completing assigned work) and ownership (driving initiatives)

### Framework References
- Reference EGF competencies from the rubric: Execution & Delivery, Skills & Knowledge, Teamwork & Communication, Influence & Leadership
- Use the Engineering Growth Rubric to evaluate demonstrated behaviors at each level
- Reference the Role Framework to set appropriate expectations for the engineer's role/sub-level
- Reference COGIS values when relevant: Camaraderie, Openness, Grit, Integrity, Simplicity
