---
description: This skill generates 1:1 meeting prep documents. Use when asked to "prep for 1:1", "1:1 prep", "one on one prep", "prepare for 1:1 with [name]", "what should I discuss with [name]".
allowed-tools:
  - mcp__ic-tracker__get_github_contributions
  - mcp__ic-tracker__get_team_bandwidth
  - mcp__ic-tracker__get_peer_feedback
  - mcp__ic-tracker__search_jira_issues
  - mcp__ic-tracker__get_team_members
  - Read
  - Glob
---

# 1:1 Prep Skill

Generate concise, actionable 1:1 meeting prep documents by aggregating data from GitHub, Jira, and goals files.

## Workflow

1. **Identify team member**
   - Use `mcp__ic-tracker__get_team_members` to get available members and resolve the name
   - If not specified, ask which team member the 1:1 is with

2. **Gather recent contributions (14 days)**
   - `mcp__ic-tracker__get_github_contributions` with `days: 14`
   - Note PRs merged and reviews given

3. **Get current workload**
   - `mcp__ic-tracker__get_team_bandwidth` filtered to this user's GitHub username
   - Extract open story points and in-progress items by epic

4. **Check for blockers and risks via Jira**
   - Blocked items: `assignee = "<jira-account-id>" AND status = "Blocked"`
   - Stale in-progress: `assignee = "<jira-account-id>" AND status = "In Progress" AND updated < -7d`
   - Overdue: `assignee = "<jira-account-id>" AND duedate < now() AND status != Done`

5. **Surface recent peer feedback (if any)**
   - `mcp__ic-tracker__get_peer_feedback` for this user
   - Only include if feedback exists

6. **Read goals file**
   - Find goal file: `goals/<name>.md` (use Glob if needed)
   - Extract performance goals and key results for alignment context

7. **Generate prep document**

## Output Format

```markdown
# 1:1 Prep: [Name]
[Date] | Last 14 days

## Stats
| PRs | Reviews | Open Points | Blocked |
|-----|---------|-------------|---------|
| X   | X       | X           | X       |

## Recent Work
- [PR title] ([repo])
- [PR title] ([repo])

## Current
**[Epic name]** - X pts remaining
- [In progress item]
- [In progress item]

## Blockers
- [PROJ-123] [Title] - blocked [X days]
- [PROJ-456] [Title] - overdue [date]

## Goals
**On track:** [Goal] - [evidence]
**Needs attention:** [Goal] - no recent activity

## Feedback Themes
- [Theme from peer feedback]

## Questions
- [Specific question based on data]
- [Specific question based on data]
```

## Section Rules

- **Omit empty sections entirely** - if no blockers, skip the Blockers section; if no feedback, skip Feedback Themes
- **Stats table is always included**
- **Recent Work** - list up to 5 most recent PRs, use actual PR titles
- **Current** - group by epic, show in-progress items
- **Goals** - simple binary: on-track (has recent evidence) or needs-attention (no recent activity)
- **Questions** - generate 2-3 specific questions derived from the data

## Guidelines

### Do
- Use data directly without paraphrasing
- Keep PR titles verbatim
- State facts plainly
- Omit sections with no data
- Focus on items that warrant discussion

### Do Not
- Add filler phrases ("Great progress!", "Excellent work!", "Keep it up!")
- Add commentary or opinions
- Hedge ("potentially experiencing some delays" → just say "blocked")
- Paraphrase or "translate" PR titles
- Include empty sections
- Add time estimates or predictions

## Comparison to Other Skills

| Aspect | Performance Review | Weekly Update | 1:1 Prep |
|--------|-------------------|---------------|----------|
| Time range | 90 days | 7 days | 14 days |
| Depth | Deep analysis | Summary | Actionable highlights |
| Goal scoring | Detailed (0-100) | None | Light (on-track/needs-attention) |
| Blocker detection | No | Basic | Yes (Jira queries) |
| Output length | Long | Medium | Short (~1 page) |
