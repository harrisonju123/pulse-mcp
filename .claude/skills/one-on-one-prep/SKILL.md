---
description: This skill generates 1:1 meeting prep documents. Use when asked to "prep for 1:1", "1:1 prep", "one on one prep", "prepare for 1:1 with [name]", "what should I discuss with [name]".
allowed-tools:
  - mcp__ic-tracker__get_github_contributions
  - mcp__ic-tracker__get_contribution_trends
  - mcp__ic-tracker__get_team_bandwidth
  - mcp__ic-tracker__get_peer_feedback
  - mcp__ic-tracker__get_competency_analysis
  - mcp__ic-tracker__get_initiative_roadmap
  - mcp__ic-tracker__search_jira_issues
  - mcp__ic-tracker__get_team_members
  - Read
  - Glob
---

# 1:1 Prep Skill

Generate concise, actionable 1:1 meeting prep documents by aggregating data from GitHub, Jira, and goals files.

## What This Prep Should Answer

1. What wins should I acknowledge?
2. Is their output trending up/down vs their baseline?
3. Are they actually blocked on anything?
4. What patterns might need discussion?
5. What 2-3 things should I ask about?

## Workflow

1. **Identify team member**
   - Use `mcp__ic-tracker__get_team_members` to get available members and resolve the name
   - If not specified, ask which team member the 1:1 is with

2. **Gather recent contributions (14 days)**
   - `mcp__ic-tracker__get_github_contributions` with `days: 14`
   - Note PRs merged and reviews given

3. **Get trend baseline**
   - `mcp__ic-tracker__get_contribution_trends` with `period_type: "biweekly"`, `num_periods: 3`
   - Compare current period to 6-week average

4. **Get in-progress work**
   - Get Jira account ID from `get_team_members` response (jira_account_id field)
   - JQL: `assignee = "<jira-account-id>" AND status = "In Progress" ORDER BY updated DESC`
   - Limit to 5 items, show ticket key and title

5. **Check for blockers**
   - Blocked items: `assignee = "<jira-account-id>" AND status = "Blocked"`
   - Overdue: `assignee = "<jira-account-id>" AND duedate < now() AND status != Done`
   - Note: Status names vary by project. Adjust "Blocked" to match your workflow.

6. **Read goals file**
   - Find goal file: `goals/<name>.md` (use Glob if needed)
   - Extract goal titles for reference
   - If no goals file exists, skip the Goals section and add a question: "Do you have documented goals we should set up?"

7. **Extract OKR data from goals file (if exists)**
   - Parse Performance Goal sections (look for `### Performance Goal #N:` headers)
   - Extract goal title and count of Key Results (bullet points under "Key Results:")
   - If "Jira Epics/Initiatives" section exists, extract epic keys (e.g., `PROJ-123`)
   - Query `mcp__ic-tracker__get_initiative_roadmap` for each epic to get progress %
   - Skip this section if no goals file exists

8. **Gather career progress data (if goals file exists)**
   - Call `mcp__ic-tracker__get_competency_analysis` with `days: 90`
   - Extract from goals file:
     - Current level from "Current Leveling" section (P2/P3/P4/P5)
     - Target level from "Long term goal" line
   - Skip this section if no goals file exists

9. **Surface recent peer feedback (if any)**
   - `mcp__ic-tracker__get_peer_feedback` for this user
   - Only include if feedback exists

10. **Generate prep document**

## Output Format

```markdown
# 1:1 Prep: [Name]
[Date] | Last 14 days

## Wins
- [Notable accomplishment with context]
- [Large/impactful PR if applicable - include line count for context]

## Activity (vs 6-week avg)
| Metric  | This Period | Avg | Trend   |
|---------|-------------|-----|---------|
| PRs     | X           | Y   | ↑/↓ Z%  |
| Reviews | X           | Y   | ↑/↓ Z%  |

## In Progress
- [PROJ-123] [Title]
- [PROJ-456] [Title]

## Blockers
- [PROJ-789] [Title] - blocked X days

## Goals Check
Review: goals/[name].md
Focus areas: [Goal 1 title], [Goal 2 title], [Goal 3 title]

## OKR Status
| Goal | Key Results | Jira Progress |
|------|-------------|---------------|
| #1 [Goal title] | X KRs | —/X% |
| #2 [Goal title] | X KRs | —/X% |
| #3 [Goal title] | X KRs | —/X% |

**Discussion prompts:**
- Goal #N: "[Question about specific KR]" (KR: [KR text])
- Goal #N: "[Question about specific KR]" (KR: [KR text])

## Career Progress (90-day view)
**Current:** P3 (Engineer) | **Target:** P4 (Senior)

| Competency              | Score | vs Target |
|-------------------------|-------|-----------|
| Execution & Delivery    | 75    | Ready     |
| Skills & Knowledge      | 45    | Building  |
| Teamwork & Communication| 60    | Ready     |
| Influence & Leadership  | 25    | Gap       |

**Strongest:** [Competency] - [brief evidence]
**Growth focus:** [Competency] - [what's missing]

**Coaching prompt:** [One question connecting growth area to documented goal]

## Feedback Themes
- [Theme from peer feedback]

## Questions
- [Specific question from data]
- [Specific question from data]
```

## Section Rules

- **Omit empty sections entirely** - if no blockers, skip Blockers; if no feedback, skip Feedback Themes
- **Wins is always included** - identify 1-2 notable contributions:
  - PRs with high line count (largest PR in period)
  - Trend improvements (e.g., "53% above average")
  - Completed significant work items
- **Activity table is always included** - show comparison to 6-week average with trend arrows (↑/↓)
- **In Progress** - show up to 5 items with actual ticket keys and titles
- **Blockers** - only show items with status "Blocked" or overdue with due dates
- **Goals Check** - simple reference to goals file with focus area titles; no assessment
- **OKR Status** - shows performance goals with KR counts and optional Jira progress; omit if no goals file exists
  - Goal titles: Use the text after "Performance Goal #N:" (e.g., "Execution & Delivery")
  - KR count: Count bullet points under "Key Results:" for each goal
  - Jira Progress: Show "X%" if epic progress available from `get_initiative_roadmap`, "—" otherwise
  - Discussion prompts: Pick 1-2 specific, measurable KRs that can be quickly assessed (avoid vague ones)
- **Career Progress** - 90-day competency pulse check; omit if no goals file exists
  - Parse current level from "Current Leveling" section and target from "Long term goal" line
  - Score thresholds for "vs Target" column:
    - "Ready": Score >= 50
    - "Building": Score 30-49
    - "Gap": Score < 30
  - "Strongest": Highest-scoring competency with brief evidence from analysis
  - "Growth focus": Lowest-scoring competency with what's missing
  - "Coaching prompt": ONE specific question connecting a growth area to their documented performance goals
- **Questions** - generate 2-3 specific questions derived from patterns in the data

## Guidelines

### Do
- Use data directly without paraphrasing
- Keep PR titles verbatim
- State facts plainly
- Omit sections with no data
- Focus on items that warrant discussion
- Show trend comparisons with percentages

### Do Not
- Add filler phrases ("Great progress!", "Excellent work!", "Keep it up!")
- Add commentary or opinions
- Hedge ("potentially experiencing some delays" -> just say "blocked")
- Paraphrase or "translate" PR titles
- Include empty sections
- Add time estimates or predictions
- List epic keys without context or titles
- Ask generic questions like "No story points on issues - is this intentional?" or "Should status be updated?"
- Query for stale in-progress items (epics staying open for weeks is normal)

## Comparison to Other Skills

| Aspect | Performance Review | Weekly Update | 1:1 Prep |
|--------|-------------------|---------------|----------|
| Time range | 90 days | 7 days | 14 days (activity) / 90 days (career) |
| Depth | Deep analysis | Summary | Actionable highlights |
| Goal scoring | Detailed (0-100) | None | Reference only |
| OKR tracking | Full assessment | None | Status + discussion prompts |
| Career mapping | Deep analysis | None | Pulse check |
| Blocker detection | No | Basic | Yes (Jira queries) |
| Trend comparison | No | No | Yes (6-week baseline) |
| Output length | Long | Medium | Short (~1 page) |
