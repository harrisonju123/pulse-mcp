---
description: This skill generates personal self-assessment reflections. Use when asked to "self-assess", "reflect on my work", "self-review", "what have I accomplished", "how am I doing", "review my progress".
allowed-tools:
  - mcp__work-tracker__get_self
  - mcp__work-tracker__get_github_contributions
  - mcp__work-tracker__get_confluence_contributions
  - mcp__work-tracker__get_contribution_trends
  - mcp__work-tracker__get_contribution_distribution
  - mcp__work-tracker__get_competency_analysis
  - mcp__work-tracker__get_goals
  - mcp__work-tracker__get_goal_progress
  - mcp__work-tracker__get_journal_entries
  - mcp__work-tracker__search_journal
  - Read
  - Glob
---

# Self-Assessment Skill

Generate a reflective self-assessment for personal growth and self-awareness.

## Philosophy

Unlike a performance review (which evaluates against expectations), a self-assessment is:
- **Reflective** - Focus on learning and growth, not judgment
- **Personal** - Written in first person, for yourself
- **Growth-oriented** - Identify patterns and opportunities, not just metrics
- **Honest** - Acknowledge both accomplishments and struggles

This is YOUR reflection, not a report to anyone else.

## Workflow

### 1. Identify Self

Call `mcp__work-tracker__get_self` to get configured username. If not configured, ask the user for their GitHub username.

### 2. Gather Contribution Data (90 days default)

Run these in parallel:
- `mcp__work-tracker__get_github_contributions` (days: 90)
- `mcp__work-tracker__get_confluence_contributions` (days: 90)
- `mcp__work-tracker__get_contribution_trends` (period_type: "biweekly", num_periods: 4)
- `mcp__work-tracker__get_contribution_distribution` (days: 90)

### 3. Get Goal Context

Run these to understand goals:
- `mcp__work-tracker__get_goals` (status: "active")
- `mcp__work-tracker__get_goal_progress`

If goals exist in markdown files:
- Use `Glob` to find `goals/*.md` files for the user
- Use `Read` to read any goal files found

### 4. Gather Recent Reflections (if any)

- `mcp__work-tracker__get_journal_entries` (days: 90)

Look for patterns in self-noted wins, learnings, blockers.

### 5. Get Competency Insights

- `mcp__work-tracker__get_competency_analysis` (days: 90)

Use as data points, NOT as judgments. This is about understanding your work patterns, not scoring yourself.

### 6. Generate Self-Assessment

## Output Format

```markdown
# Self-Assessment: [Period]

*This is my personal reflection on the last [N] days of work.*

---

## What I Shipped

### Major Accomplishments
- [Accomplishment with context - what you built and why it mattered]
- [Another accomplishment]

### Key Contributions
[Group PRs/docs by theme - not just a list, but patterns]

- **[Theme/Area]**: [What you did in this area]
- **[Theme/Area]**: [What you did in this area]

---

## How I Grew

### Skills I Developed
- **[Skill]**: [Evidence from work - what did you learn by doing?]
- **[Skill]**: [Evidence]

### New Areas I Explored
- [New repos, technologies, or domains you worked in]

---

## Progress on My Goals

[If goals exist]

### [Goal 1 Title]
**Progress:** [Description of what you did toward this goal]
**Key Results:** X/Y completed
**Reflection:** [What went well? What was harder than expected?]

### [Goal 2 Title]
...

[If no goals exist]

*No formal goals tracked. Consider setting some for the next period.*

---

## Patterns I Notice

### What's Working
- [Pattern that's serving you well - not a brag, just an observation]
- [Another pattern]

### What's Challenging
- [Honest acknowledgment of struggles - frame as reality, not weakness]
- [Another challenge]

*Note: Challenges aren't failures. They're just where growth happens.*

---

## What I'm Learning About Myself

[Insights from the data or reflections - not "areas for improvement" but genuine self-knowledge]

- [Insight about how you work, what energizes you, what drains you]
- [Insight about your impact or collaboration style]

---

## Where I Want to Focus Next

[Not "improvement areas" but genuine interests and growth directions]

- [Something you want to learn or build]
- [An area you want to deepen]
- [A way you want to work differently]

---

## Questions I'm Sitting With

[Open questions for continued reflection - these don't need answers]

- [Question about your work, career, or growth]
- [Question about what's next]

---

*Generated with [Work Tracker](https://github.com/anthropics/pulse-mcp)*
```

## Guidelines

### Do
- Use first person ("I shipped...", "I noticed...", "I'm learning...")
- Frame observations neutrally - patterns, not judgments
- Connect data to personal experience
- Include both quantitative and qualitative observations
- Reference journal entries if they add meaningful context
- Be specific about what you learned, not just what you did
- Acknowledge complexity and nuance

### Do Not
- Use performance review language ("exceeds", "meets expectations", "demonstrates")
- Judge yourself harshly OR inflate accomplishments artificially
- Focus only on metrics without meaning
- Include recommendations for "improvement" (this isn't a PIP)
- Use corporate speak or hollow phrases ("synergy", "excellence", "world-class")
- Compare yourself to others
- Force positivity - it's okay if some things were hard

### Tone

The output should feel like a thoughtful letter to yourself, not a report to your manager. It should help you:
- **Remember** what you've actually done (we forget our own work)
- **See patterns** you might miss day-to-day
- **Identify** what genuinely interests you
- **Prepare** for conversations about your career (without the anxiety)
- **Ground** yourself in reality, not fears or aspirations

This is NOT a document for someone else to read. It's for YOU.

## Example Framing

**Good (Reflective)**:
- "I notice I'm drawn to infrastructure work more than feature work"
- "The authentication project taught me how to navigate ambiguity"
- "I'm still figuring out how to balance deep work with being available for the team"

**Bad (Evaluative)**:
- "I exceeded expectations on infrastructure work"
- "I successfully led the authentication project"
- "I need to improve my time management skills"

## Notes

- If the user has NO contributions in the period, acknowledge this honestly without judgment
- If journal entries reveal struggles, include them - this is growth data
- If goals are behind, that's just information, not failure
- The value is in the reflection, not the achievements
