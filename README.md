# Pulse MCP

An MCP server that gives AI assistants (Claude, Cursor) visibility into your team's work across GitHub, Jira, and Confluence.

**Ask questions like:**
- "What did Sarah ship this week?"
- "Prep me for my 1:1 with Alex"
- "Show the roadmap for PROJ-123"
- "Write my weekly update"
- "Draft a performance review for Jordan"

## Quick Start (GitHub only)

The fastest way to get started - just GitHub, no Jira/Confluence needed.

```bash
# 1. Clone and setup
git clone https://github.com/YOUR_USERNAME/pulse-mcp.git
cd pulse-mcp
./setup.sh

# 2. Get a GitHub token
#    → https://github.com/settings/tokens
#    → Generate new token (classic) → select 'repo' scope

# 3. Edit config.json with your token and team
```

**Minimal config.json:**
```json
{
  "github": {
    "token": "ghp_your_token_here",
    "org": "your-github-org",
    "repos": []
  },
  "team_members": {
    "octocat": { "atlassian_account_id": "N/A", "name": "Octocat" },
    "hubot": { "atlassian_account_id": "N/A", "name": "Hubot" }
  }
}
```

The setup script prints MCP config to copy into Claude Code or Cursor. Restart after adding it.

## What You Can Do

### Track contributions
```
"What did @alice ship in the last 2 weeks?"
"Show me contribution trends for the team"
"Who reviewed the most PRs this month?"
```

### Prep for meetings
```
"Prep for my 1:1 with Bob"        → /one-on-one-prep
"Write my weekly update"          → /weekly-update
"Draft a review for Carol"        → /performance-review
```

### Plan and track work (requires Jira)
```
"Show the roadmap for INITIATIVE-123"
"What's the team's bandwidth?"
"Search for open bugs in PROJ"
```

## Adding Jira & Confluence

Expand your config.json:

```json
{
  "github": { ... },
  "confluence": {
    "base_url": "https://yourcompany.atlassian.net/wiki",
    "email": "you@company.com",
    "api_token": "your-atlassian-token",
    "space_keys": ["ENGINEERING", "DOCS"]
  },
  "jira": {
    "base_url": "https://yourcompany.atlassian.net",
    "email": "you@company.com",
    "api_token": "your-atlassian-token",
    "project_keys": ["PROJ", "TEAM"],
    "story_point_field": "customfield_10016",
    "epic_link_field": "customfield_10014"
  },
  "team_members": {
    "github-username": {
      "atlassian_account_id": "712020:abc123-...",
      "name": "Full Name"
    }
  }
}
```

Get your Atlassian API token: https://id.atlassian.com/manage-profile/security/api-tokens

## MCP Configuration

After running `./setup.sh`, add the printed config to:

| App | Config File |
|-----|-------------|
| Claude Code | `~/.claude/mcp_settings.json` |
| Cursor | `~/.cursor/mcp.json` |

Then restart the app.

## Available Tools

| Tool | Description |
|------|-------------|
| `get_github_contributions` | PRs merged, reviews given, lines changed |
| `get_member_pulse` | Qualitative summary of what someone shipped |
| `get_pr_details` | Deep dive into a specific PR with file categorization |
| `get_contribution_trends` | Week-over-week or monthly trends |
| `get_contribution_distribution` | Work by repo, file type, area |
| `get_teams` | List configured teams |
| `get_team_members` | List team members |
| `get_confluence_contributions` | Pages created/updated, comments |
| `get_initiative_roadmap` | Epics under an initiative with progress |
| `get_team_bandwidth` | Work distribution across team |
| `search_jira_issues` | Flexible JQL search |

## Skills (Claude Code)

Built-in skills that combine multiple tools:

| Skill | What it does |
|-------|--------------|
| `/pulse [name]` | Qualitative summary of what someone shipped |
| `/one-on-one-prep [name]` | Meeting prep with blockers, goals, discussion topics |
| `/weekly-update` | Generate your weekly status report |
| `/performance-review [name]` | Draft a review using contribution data |

## Multi-Team Support

Organize members into teams:

```json
{
  "teams": {
    "platform": {
      "name": "Platform Team",
      "members": {
        "alice": { "atlassian_account_id": "...", "name": "Alice" },
        "bob": { "atlassian_account_id": "...", "name": "Bob" }
      }
    },
    "product": {
      "name": "Product Team",
      "members": {
        "carol": { "atlassian_account_id": "...", "name": "Carol" }
      }
    }
  }
}
```

Then ask: "What did the platform team ship?" or "/pulse platform"

## Goal Files

For performance reviews, store goals in `goals/<name>.md`:

```bash
cp goals/TEMPLATE.md goals/alice-smith.md
# Edit with their goals
```

The `/performance-review` skill uses these to evaluate against objectives.

## Customizing Reference Docs

The performance review skill uses reference documents in `.claude/skills/performance-review/references/`.

To customize for your company:
1. Copy `engineering-growth-framework.example.md` → `engineering-growth-framework.md`
2. Copy `engineering-growth-rubric.example.md` → `engineering-growth-rubric.md`
3. Edit with your company's actual framework

These files are gitignored so your internal docs stay private.

## Troubleshooting

**Validate your config:**
```bash
.venv/bin/python server.py --validate
```

**Common issues:**

| Problem | Solution |
|---------|----------|
| MCP server not loading | Check paths are absolute in MCP config, restart app |
| 401 errors | Regenerate API token, check it has correct scopes |
| Empty results | Check date range, verify usernames are correct |
| Unknown team member | GitHub usernames are case-sensitive |

**Finding Atlassian account IDs:**
1. Go to their Confluence profile
2. URL contains: `/wiki/people/712020:abc123-...`
3. Copy the part after `/people/`

**Finding Jira custom field IDs:**
1. Export any issue to XML
2. Search for your story point value
3. Field ID looks like `customfield_10016`

## Manual Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json
# Edit config.json
python server.py --validate
```

## License

MIT
