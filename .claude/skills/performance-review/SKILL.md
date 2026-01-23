---
description: This skill writes performance reviews for team members. Use when asked to "write performance review", "draft review", "create perf review", "evaluate performance", or "review feedback for [name]".
allowed-tools:
  - mcp__ic-tracker__get_github_contributions
  - mcp__ic-tracker__get_confluence_contributions
  - mcp__ic-tracker__get_team_members
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
   - `mcp__ic-tracker__get_github_contributions` - PRs, reviews, lines changed
   - `mcp__ic-tracker__get_confluence_contributions` - docs created/updated

4. **Read the team member's goals**
   - Find goal file: `goals/<name>.md`
   - Extract performance goals, key initiatives, key results

5. **Analyze alignment**
   - Map contributions to documented initiatives
   - Identify work supporting stated key results
   - Evaluate against EGF competencies and expected level for their role
   - Note gaps or areas needing attention

6. **Generate review**

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

## Output Format

```
# Performance Review: [Name]
**Review Period:** [Start Date] - [End Date] ([Named Range if applicable])
**Role:** [Title from goals]

## Summary
[2-3 sentence overview]

## Goal Progress

### [Goal #1: Title]
**Status:** On Track / Needs Attention / Exceeded

**Evidence:**
- [Specific PR demonstrating progress]
- [Quantitative metrics]

**Assessment:** [How work contributed to this goal]

[Repeat for each goal...]

## Contributions Breakdown

### Code Delivery
- PRs Merged: [X]
- Lines Changed: [X]
- Key Deliverables: [Notable PRs with context]

### Documentation
- Pages Created/Updated: [X]

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
