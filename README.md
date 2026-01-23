# IC Tracker

MCP server for engineering managers. Pulls GitHub, Confluence, and Jira data for your team. Works with Claude Code and Cursor.

**Features:**
- GitHub contributions (PRs, reviews, lines changed)
- Confluence activity (pages, comments)
- Jira planning (initiative roadmaps, team bandwidth, issue search)
- Skills for 1:1 prep, performance reviews, and weekly updates

## GitHub-Only Quick Start

If you only need GitHub tracking (no Confluence), here's the minimal setup:

```bash
./setup.sh
```

Then edit `config.json`:

```json
{
  "github": {
    "token": "ghp_xxxxxxxxxxxx",
    "org": "yourcompany",
    "repos": []
  },
  "team_members": {
    "octocat": {
      "atlassian_account_id": "N/A",
      "name": "Octocat"
    }
  }
}
```

That's it! No Confluence section needed. Use `"N/A"` for `atlassian_account_id`.

## Quick Setup

```bash
./setup.sh
```

The script will:
1. Create a Python virtual environment
2. Install dependencies
3. Create `config.json` from template (if missing)
4. Print ready-to-copy MCP config with absolute paths
5. Optionally validate your API connections

After running, copy the printed JSON config to the appropriate location (see below).

## What Gets Installed

The setup script creates:
- `.venv/` - Python virtual environment (local to this directory)
- `config.json` - Your configuration file (copied from template)

Nothing is installed globally. To uninstall, simply delete this directory.

## Configuration

### 1. API Tokens

Create tokens for the services you use:

| Service | Token URL | Required Scope |
|---------|-----------|----------------|
| GitHub | https://github.com/settings/tokens | `repo` (classic token) |
| Confluence | https://id.atlassian.com/manage-profile/security/api-tokens | N/A |
| Jira | https://id.atlassian.com/manage-profile/security/api-tokens | N/A (same token works for both) |

### 2. config.json

Edit `config.json` with your values:

```json
{
  "github": {
    "token": "ghp_xxxxxxxxxxxx",
    "org": "yourcompany",
    "repos": ["repo1", "repo2"]
  },
  "confluence": {
    "base_url": "https://yourcompany.atlassian.net/wiki",
    "email": "you@company.com",
    "api_token": "your-confluence-api-token",
    "space_keys": ["ENGG", "DOCS"]
  },
  "jira": {
    "base_url": "https://yourcompany.atlassian.net",
    "email": "you@company.com",
    "api_token": "your-jira-api-token",
    "project_keys": ["PROJ", "TEAM"],
    "story_point_field": "customfield_10016",
    "epic_link_field": "customfield_10014"
  },
  "team_members": {
    "github-username": {
      "atlassian_account_id": "712020:abc123-def456-...",
      "name": "Jane Smith"
    }
  }
}
```

**Notes:**
- The `confluence` and `jira` sections are optional - remove if not using
- `repos` is optional - leave as `[]` to search all repos in the org
- Use `"N/A"` for `atlassian_account_id` if not using Confluence/Jira

**Important - Jira URL:**
- Some orgs have separate Jira instances (e.g., `yourcompany-tech.atlassian.net` vs `yourcompany.atlassian.net`)
- Check the URL when viewing your Jira board to get the correct base URL
- The API token is the same for both Confluence and Jira

### 3. MCP Configuration

#### Config Locations

| Editor | Location | Scope |
|--------|----------|-------|
| Claude Code | `~/.claude/mcp_settings.json` | All projects (global) |
| Claude Code | `.claude/settings.local.json` | Current project only |
| Cursor | `~/.cursor/mcp.json` | Global |

**Recommendation:** Use global config (`~/.claude/mcp_settings.json`) for MCP servers.

#### Claude Code

Add to `~/.claude/mcp_settings.json` (create if it doesn't exist):

```json
{
  "mcpServers": {
    "ic-tracker": {
      "command": "/path/to/ic-tracker/.venv/bin/python",
      "args": ["/path/to/ic-tracker/server.py"],
      "env": {
        "IC_TRACKER_CONFIG": "/path/to/ic-tracker/config.json"
      }
    }
  }
}
```

#### Cursor

Add to `~/.cursor/mcp.json` (create the file if it doesn't exist):

```json
{
  "mcpServers": {
    "ic-tracker": {
      "command": "/path/to/ic-tracker/.venv/bin/python",
      "args": ["/path/to/ic-tracker/server.py"],
      "env": {
        "IC_TRACKER_CONFIG": "/path/to/ic-tracker/config.json"
      }
    }
  }
}
```

**Tip:** Run `./setup.sh` to get the config with correct absolute paths for your machine.

After adding the config, restart Claude Code or Cursor for the MCP server to load.

### 4. Validate

```bash
./setup.sh  # and choose 'y' when prompted
# or
.venv/bin/python server.py --validate
```

## Available Tools

Once configured, you'll have access to these MCP tools:

### GitHub Tools
| Tool | Description |
|------|-------------|
| `get_github_contributions` | PRs merged, code reviews given, lines changed |
| `get_contribution_trends` | Week-over-week or monthly contribution trends |
| `get_contribution_distribution` | Work distribution by repo, file type, area |
| `get_competency_analysis` | Map contributions to EGF competencies |

### Confluence Tools
| Tool | Description |
|------|-------------|
| `get_confluence_contributions` | Pages created/updated, comments added |

### Jira Planning Tools
| Tool | Description |
|------|-------------|
| `get_initiative_roadmap` | Shows epics under an initiative with progress % |
| `get_team_bandwidth` | Work distribution across team members |
| `search_jira_issues` | Flexible JQL search for any query |

### Other Tools
| Tool | Description |
|------|-------------|
| `get_team_members` | List configured team members |
| `get_peer_feedback` | Read structured feedback files |

All tools support `start_date`, `end_date`, and `days` parameters for flexible date ranges.

## Example Usage

After setup, just ask Claude naturally:

```
"Show me the roadmap for ME-453"
"What's the team's bandwidth right now?"
"Get my GitHub contributions for the last 30 days"
"Search for open bugs in PROJ"
"Prep for my 1:1 with Jordan"
"Write a performance review for Jordan"
"Generate my weekly update"
```

## Skills

This project includes custom Claude Code skills that use the MCP tools:

| Skill | Trigger | Description |
|-------|---------|-------------|
| `/one-on-one-prep` | "prep for 1:1 with [name]" | Generates actionable 1:1 meeting prep with blockers, goals, and discussion questions |
| `/performance-review` | "write performance review for [name]" | Generates comprehensive review using GitHub, Confluence, Jira data and goals |
| `/weekly-update` | "write my weekly update" | Generates weekly status report from contributions |

Skills are defined in `.claude/skills/` and can be customized for your team's needs.

## Goal Files

Store team member goals in `goals/<firstname-lastname>.md`. Copy from `goals/TEMPLATE.md`.

These are used by the `/performance-review` skill to evaluate contributions against stated objectives.

## Finding Jira Project Keys

Project keys are the prefix on issue IDs (e.g., `ME` in `ME-123`).

**To find your team's project keys:**
1. Go to your Jira board or backlog
2. Look at any issue ID - the letters before the dash are the project key
3. Add all projects your team works in to `project_keys` in config.json

**Example:** If your team works on issues like `ME-123`, `LC-456`, and `PLAT-789`:
```json
"project_keys": ["ME", "LC", "PLAT"]
```

**Finding the right Jira instance:**
- Check the URL when viewing your Jira board
- Some orgs have multiple instances (e.g., `company.atlassian.net` vs `company-tech.atlassian.net`)
- Use the URL that matches where your team's boards live

## Finding Jira Custom Field IDs

The `story_point_field` and `epic_link_field` vary by Jira instance.

**To find your field IDs:**

1. Open any Jira issue that has story points
2. Click `...` menu → `Export` → `Export XML`
3. Search for your story point value in the XML
4. The field ID looks like `customfield_10016`

**Common defaults:**
| Field | Common ID | Notes |
|-------|-----------|-------|
| Story Points | `customfield_10016` | Often varies |
| Epic Link | `customfield_10014` | Legacy field, may not exist in newer Jira |

**Alternative method (requires admin):**
1. Go to Jira Settings → Issues → Custom Fields
2. Click on the field name
3. The ID is in the URL: `.../customfields/10016`

## Finding Atlassian Account IDs

Atlassian account IDs aren't shown in the UI. To find them:

1. Go to any Confluence page edited by the person
2. Click their profile picture/name to open their profile
3. Look at the URL: `https://yourcompany.atlassian.net/wiki/people/712020:abc123-def456-...`
4. The account ID is the part after `/people/`

## Manual Setup

If you prefer not to use the setup script:

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create config
cp config.example.json config.json
# Edit config.json with your values

# Validate
python server.py --validate
```

## Troubleshooting

Run `python server.py --validate` to check your configuration.

**"Configuration not loaded"**
- Ensure `IC_TRACKER_CONFIG` env var points to your config.json
- Check the path in your MCP config is absolute and correct

**"401 Error" or "token is invalid or expired"**
- GitHub: Generate a new token at https://github.com/settings/tokens
- Confluence/Jira: Generate a new token at https://id.atlassian.com/manage-profile/security/api-tokens

**"Unknown team member"**
- GitHub usernames are case-sensitive
- Atlassian account IDs must be the full ID including the `712020:` prefix

**"0 team member(s) configured" or empty team_members**
- Your `team_members` object in config.json is empty
- Add at least one team member with their GitHub username as the key

**MCP server not appearing in Claude Code/Cursor**
- Verify the Python path exists: `ls /path/to/.venv/bin/python`
- Check JSON syntax in your MCP config file
- Restart the application after config changes
- For Claude Code, check `~/.claude/mcp_settings.json` (not `settings.json`)

**Empty results**
- Verify the date range includes actual activity
- For Confluence, check that `space_keys` match your space keys exactly

**Jira: Wrong instance or no results**
- Check if your org has multiple Jira instances (e.g., `company.atlassian.net` vs `company-tech.atlassian.net`)
- Verify `project_keys` includes all projects you want to query
- Test with: `IC_TRACKER_CONFIG=/path/to/config.json python server.py --validate`

**Jira: Initiative roadmap shows 0 epics**
- Jira Advanced Roadmaps (Plans) uses virtual hierarchy not captured by parent links
- Use `search_jira_issues` with JQL to find related issues instead
- Example: `project = ME AND type = Epic ORDER BY created DESC`

**Jira: Finding custom field IDs**
- `story_point_field` and `epic_link_field` vary by Jira instance
- To find yours: Open a Jira issue → Export to JSON → Search for your story point field name
- Common defaults: `customfield_10016` (story points), `customfield_10014` (epic link)
