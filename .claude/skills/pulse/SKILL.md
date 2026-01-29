---
description: Generate qualitative pulse summary for person or team. Use when asked to "pulse", "team pulse", "what did [name] ship", "what's [team] working on", "qualitative summary".
allowed-tools:
  - mcp__ic-tracker__get_member_pulse
  - mcp__ic-tracker__get_pr_details
  - mcp__ic-tracker__get_teams
  - mcp__ic-tracker__get_team_members
---

# Pulse

Generate a qualitative summary of what someone (or a team) shipped, emphasizing narrative over metrics.

## Invocation

```
/pulse harrisonju123           # single person
/pulse market_expansion        # whole team
/pulse                         # all teams
```

## Workflow

### For Individual (e.g., `/pulse harrisonju123`)

1. Call `mcp__ic-tracker__get_member_pulse` for the username
2. For the most significant PRs (largest, most interesting titles), call `mcp__ic-tracker__get_pr_details` with `include_diff: true` to understand what was actually built
3. Analyze the diff content - focus on feature files, ignore generated/deps
4. Group work by semantic theme based on actual code changes (not just PR titles)
5. Write narrative: "**Shipped:** [theme summary]" with bullet points for grouped work
6. Note collaboration patterns from the `collaboration` data
7. Flag any open work or stale PRs

### Deeper Analysis with get_pr_details

Use `get_pr_details` to understand *what* was actually built:

```
get_pr_details(repo="mauvelous-hippo", pr_number=492, include_diff=true)
```

The tool returns:
- **feature_files**: Actual application code changes with diffs
- **test_files**: Test changes (shows test coverage)
- **other_files**: Generated code, deps, vendor (noise to filter out)
- **summary**: Stats showing what % is feature work vs noise

Focus your analysis on feature files. The diff content shows exactly what code was added/changed.

### For Team (e.g., `/pulse market_expansion`)

1. Call `mcp__ic-tracker__get_team_members` with team filter
2. Call `mcp__ic-tracker__get_member_pulse` for each member
3. Write per-person narrative sections
4. Add "Team Patterns" section highlighting:
   - Who works closely together (frequent_collaborators overlap)
   - Review load distribution
   - Any stale work across the team

### For All Teams (e.g., `/pulse`)

1. Call `mcp__ic-tracker__get_teams` to get team list
2. For each team, follow the team workflow above
3. Add cross-team patterns if any

## Output Format

### Individual Output

```markdown
## [Name] - 2-Week Pulse ([Start Date] - [End Date])

**Shipped:** [One-line theme summary based on PR titles]
- [Grouped accomplishment 1 - combine related PRs]
- [Grouped accomplishment 2]
- [Grouped accomplishment 3]

**Collaboration:** [Who reviewed their PRs, who they reviewed for]
- Reviewed by: [names with counts]
- Reviewed for: [names with counts]
- Tight loop with: [frequent collaborators]

**Open threads:** [X PRs in review] - [list any PRs open > 3 days]
```

### Team Output

```markdown
## [Team Name] - 2-Week Pulse ([Start Date] - [End Date])

### [Member 1 Name]
**Shipped:** [Theme summary]
- [Accomplishment 1]
- [Accomplishment 2]

**Collaboration:** [Pattern summary]

**Open threads:** [Status]

---

### [Member 2 Name]
[Same format...]

---

### Team Patterns
- [Who works closely together based on collaboration overlap]
- [Review load distribution - who's doing most reviews]
- [Any concerns: stale PRs, low engagement, etc.]
```

## Semantic Grouping Guidelines

Group PR titles into themes rather than listing each PR:

| Theme | PR Title Keywords |
|-------|-------------------|
| Migration | migrate, migration, transfer, move |
| Signal/Detection | signal, detect, event, trigger, webhook |
| Validation | validate, validation, check, verify |
| Infrastructure | config, setup, deploy, ci, workflow |
| Bug Fixes | fix, bug, patch, hotfix |
| Refactoring | refactor, cleanup, improve, optimize |
| Testing | test, spec, coverage |
| Documentation | doc, readme, guide |

Example grouping:
- PRs: "Add migration validation", "Extend migration workflow", "Fix migration edge case"
- Grouped as: "**Migration system improvements** - validation, workflow extensions, edge case fixes"

## Guidelines

- **Lead with what they BUILT, not how many PRs** - "Shipped the signal detection system" not "Merged 8 PRs"
- **Group related PRs into themes** - don't enumerate every PR individually
- **Collaboration is a feature** - highlight tight working relationships positively
- **Frame concerns constructively** - "1 PR waiting on review (3 days)" not "slow reviewer"
- **Skip empty sections** - if no open PRs, don't include "Open threads: None"
- **Be specific about themes** - use domain language from PR titles, not generic categories
