---
description: This skill generates brag documents for self-promotion. Use when asked to "brag doc", "brag document", "list my accomplishments", "what should I highlight", "promotion packet", "career highlights", "write my brag doc".
allowed-tools:
  - mcp__work-tracker__get_self
  - mcp__work-tracker__get_github_contributions
  - mcp__work-tracker__get_contribution_distribution
  - mcp__work-tracker__get_contribution_trends
  - mcp__work-tracker__get_member_pulse
  - mcp__work-tracker__get_pr_details
  - mcp__work-tracker__get_confluence_contributions
  - mcp__work-tracker__get_competency_analysis
  - mcp__work-tracker__get_goals
  - mcp__work-tracker__search_jira_issues
  - mcp__work-tracker__get_initiative_roadmap
  - Read
  - Glob
---

# Brag Document Skill

Generate an accomplishment summary suitable for self-promotion, performance reviews, or career advancement discussions.

## Philosophy

A brag document captures your impact in a format that:
- **Emphasizes outcomes** over activities
- **Quantifies impact** where possible
- **Tells stories** that stick
- **Is usable** - copy/paste into review forms, promotion docs, LinkedIn

This is NOT about modesty. You're building a factual record of your work and its impact. Future you will be grateful.

## Workflow

### 1. Identify Self

Call `mcp__work-tracker__get_self` to get configured username. If not configured, ask the user for their GitHub username.

### 2. Determine Time Range

Default: 6 months (180 days)

Support natural language:
- "this year" → Since January 1
- "this half" → Last 6 months
- "last quarter" → Last 3 months

### 3. Gather Comprehensive Contribution Data

Run in parallel:
- `mcp__work-tracker__get_github_contributions` (days: 180)
- `mcp__work-tracker__get_member_pulse` (days: 180)
- `mcp__work-tracker__get_contribution_distribution` (days: 180)
- `mcp__work-tracker__get_contribution_trends` (period_type: "monthly", num_periods: 6)

If Confluence configured:
- `mcp__work-tracker__get_confluence_contributions` (days: 180)

### 4. Deep Dive on Significant PRs

From the pulse data, identify the largest/most impactful PRs (by lines changed, complexity, or reviewer count).

For top 3-5 PRs:
- Call `mcp__work-tracker__get_pr_details` with `include_diff: true`
- Understand what was actually built, not just file changes

### 5. Get Initiative Context (if Jira configured)

If Jira is available:
- `mcp__work-tracker__search_jira_issues` - Find completed epics/stories assigned to the user
- For major initiatives, call `mcp__work-tracker__get_initiative_roadmap` to show scope

### 6. Get Competency Evidence

- `mcp__work-tracker__get_competency_analysis` (days: 180)

Use this to map work to competencies for leveling conversations.

### 7. Check Goals Alignment

- `mcp__work-tracker__get_goals`
- Read any goal files in `goals/` directory
- Connect accomplishments to stated objectives

### 8. Generate Brag Document

## Output Format

```markdown
# Brag Document: [Your Name]
**Period:** [Date Range - e.g., "January 2026 - June 2026"]
**Generated:** [Today's Date]

---

## Executive Summary

[2-3 sentences capturing your biggest impact this period. Lead with outcomes, not activities.]

*Example: "Led the authentication system migration serving 50K daily users with zero downtime. Reduced incident response time by 40% through observability improvements. Established cross-team code review standards adopted by 3 other teams."*

---

## Major Accomplishments

### [Accomplishment 1: Title - Lead with Impact]

**Impact:** [Business/technical outcome - what changed because of this work?]

**My Role:** [What you specifically did - be specific, claim your work]

**Evidence:**
- [Link to key PR or deliverable with numbers]
- [Metric improvement if available]
- [Recognition or adoption by others]

**Technical Highlights:**
- [Interesting technical decision or challenge overcome]

---

### [Accomplishment 2: Title]

[Same structure...]

---

## By the Numbers

| Metric | Count |
|--------|-------|
| PRs Merged | X |
| Code Reviews Given | X |
| Documentation Pages | X |
| Lines of Code | +X / -Y |
| Cross-Team Contributions | X repos/teams |

*Note: These numbers provide context but are NOT the story. Focus on impact.*

---

## Technical Leadership

### Systems I Own/Maintain
- **[System Name]**: [Brief description of scope and impact]
- **[System Name]**: [Description]

### Technical Decisions I Drove
- **[Decision]**: [What you decided and the positive outcome]
- **[Decision]**: [What you decided and outcome]

### Code Review Impact
- Reviewed X PRs across [list of repos/teams]
- **Key catches:** [Notable issues you prevented through review]
- **Knowledge sharing:** [Patterns you spread through reviews]

---

## Collaboration & Influence

### Cross-Team Work
- **[Initiative]**: [Your role in cross-team effort and outcome]
- **[Initiative]**: [Your role and outcome]

### Mentorship & Support
- [Who you helped and what they achieved]
- [Pairing sessions, knowledge transfers, onboarding]

### Documentation Contributions
- [Key docs you authored with adoption metrics]
- [Process improvements or runbooks created]

---

## Skills Demonstrated

[Map to competencies or leveling rubrics if available]

- **[Skill/Competency]**: [Concrete evidence from work]
- **[Skill/Competency]**: [Evidence]
- **[Skill/Competency]**: [Evidence]

---

## Initiative Contributions

[If Jira data available]

| Initiative | Role | Impact |
|------------|------|--------|
| [Initiative Key] | [Your role] | [Outcome/status] |

---

## Goal Alignment

[If goals exist]

| Goal | Status | Key Evidence |
|------|--------|--------------|
| [Goal 1] | ✅ Completed | [Brief evidence with link] |
| [Goal 2] | 🔄 On Track | [Brief evidence] |
| [Goal 3] | 📈 Exceeded | [Brief evidence] |

---

## Quotable Highlights

*One-line summaries good for LinkedIn, Slack, or quick mentions*

> "Migrated authentication system for 50K users with zero downtime"

> "Reduced incident MTTR by 40% through observability improvements"

> "Code review feedback adopted as team standard across 3 teams"

---

## What's Next

[Brief mention of upcoming work - shows trajectory and ambition]

*Note: This section is optional but can help frame your growth narrative*

---

*Generated with [Work Tracker](https://github.com/anthropics/pulse-mcp) on [Date]*
```

## Guidelines

### Do
- **Lead with impact**, not activity
- Use **specific numbers** and outcomes wherever possible
- **Frame contributions** in terms of value to team/company/users
- Make it **easy to copy** sections into other documents
- Include **quotable one-liners** for easy reference
- **Connect work** to stated goals and initiatives
- Use **active voice** and own your achievements
- Include **technical depth** for engineering audiences

### Do Not
- Be falsely modest - this is literally a brag document
- Exaggerate or claim credit for others' work
- Use vague language ("helped with", "worked on", "contributed to")
- Include routine work that doesn't demonstrate impact or growth
- Make it too long - aim for 2-3 pages max
- Focus on effort without outcomes
- List every single PR - curate the impactful ones

### Audience Awareness

This document might be used for:
- Performance review self-assessments
- Promotion packets
- Manager 1:1s for visibility
- LinkedIn updates
- Resume bullet points
- Comp review discussions

**Write it so sections can be pulled independently.**

## Impact Framing Examples

**Good (Impact-focused)**:
- "Migrated authentication system serving 50K users with zero downtime"
- "Reduced database query time by 60%, improving page load for 10K daily requests"
- "Established code review standard adopted by 3 teams, reducing bug escape rate"

**Bad (Activity-focused)**:
- "Worked on authentication migration"
- "Improved database performance"
- "Participated in code reviews"

## When to Use Numbers

✅ **Use numbers when they add context:**
- User/request volume (shows scale)
- Performance improvements (shows impact)
- Time saved (shows efficiency)
- Adoption metrics (shows influence)

❌ **Don't use numbers when they're not impressive:**
- "Fixed 3 bugs" (unless they were critical)
- "Attended 12 meetings" (nobody cares)

## Special Cases

**Low contribution periods**:
If you had a valid low-output period (parental leave, medical, etc.), note it briefly without apology. The brag doc covers what you DID ship.

**Behind on goals**:
Frame honestly - "Progress on X is behind target due to Y priority shift. Delivered Z instead, which had higher impact."

**Mostly maintenance work**:
Maintenance IS valuable. Frame it: "Maintained 3 production systems with 99.9% uptime serving 100K users."

## Notes

- Pull quotes from PR descriptions or review comments when available
- If you found problems and fixed them, that's bragworthy
- Team wins you drove count - don't hide behind "we"
- Influence matters - people adopting your work is impact
