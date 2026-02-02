---
description: This skill generates weekly status updates. Use when asked to "write weekly update", "create status report", "summarize my week", "generate standup", "what did I work on", or "team update".
allowed-tools:
  - mcp__work-tracker__get_github_contributions
  - mcp__work-tracker__get_confluence_contributions
  - mcp__work-tracker__get_team_members
  - mcp__work-tracker__get_team_bandwidth
  - mcp__work-tracker__search_jira_issues
  - Read
  - Glob
---

# Weekly Update Skill

Generate concise weekly status updates for individuals or teams.

## Workflow

1. **Determine scope**
   - Individual: specific person's update
   - Team: summary for all team members
   - Default: 7 days (adjustable)

2. **Identify team member(s)**
   - Use `mcp__work-tracker__get_team_members` to resolve names to GitHub usernames

3. **Fetch contribution data**
   - `mcp__work-tracker__get_github_contributions` with `days: 7`
   - `mcp__work-tracker__get_confluence_contributions` with `days: 7`
   - For Jira work: `mcp__work-tracker__search_jira_issues` with JQL like:
     - `assignee = "account-id" AND updated >= -7d ORDER BY updated DESC`
   - For team bandwidth: `mcp__work-tracker__get_team_bandwidth`

4. **Optionally read goals** for context on how work aligns with objectives

5. **Generate update**

## Individual Update Format

```
# Weekly Update: [Name]
**Week of:** [Date Range]

## Completed This Week
- [PR/ticket with business impact]
- [Documentation/collaboration activity]

## In Progress
- [Current work and status/blockers]

## Code Review Contributions
- Reviewed [X] PRs

## Metrics
| Metric | Count |
|--------|-------|
| PRs Merged | X |
| Reviews Given | X |
| Jira Completed | X |
| Docs Updated | X |

## Next Week Focus
- [Planned priorities]

## Blockers
- [Any blockers, or "None"]
```

## Team Summary Format

```
# Team Weekly Summary
**Week of:** [Date Range]

## Overview

| Member | PRs Merged | Reviews | Jira Completed | Docs |
|--------|------------|---------|----------------|------|
| [Name] | X | X | X | X |

## Highlights by Team Member

### [Name]
**Focus:** [Primary theme]
- [Key accomplishment]

## Key Themes
1. [Common theme across team]

## Blockers / Risks
- [Identified blockers or "None"]
```

## Guidelines

- Keep descriptions concise and outcome-focused
- Translate technical work into business value
- Group related PRs/tickets into logical deliverables
- For team summaries, identify patterns across contributions
