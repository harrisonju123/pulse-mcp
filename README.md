# IC Tracker

MCP server that pulls GitHub and Confluence contributions for your team. Works with Claude Code and Cursor.

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
  "team_members": {
    "github-username": {
      "atlassian_account_id": "712020:abc123-def456-...",
      "name": "Jane Smith"
    }
  }
}
```

**Notes:**
- The `confluence` section is optional - remove it entirely if you don't use Confluence
- `repos` is optional - leave as `[]` to search all repos in the org
- Use `"N/A"` for `atlassian_account_id` if not using Confluence

### 3. MCP Configuration

#### Config Locations

| Editor | Location | Scope |
|--------|----------|-------|
| Claude Code | `~/.claude/settings.json` | All projects (global) |
| Claude Code | `.claude/settings.local.json` | Current project only |
| Cursor | `~/.cursor/mcp.json` | Global |

**Recommendation:** Use global config (`~/.claude/settings.json`) unless you're testing or have project-specific needs.

#### Claude Code

Add to `~/.claude/settings.json` (global) or `.claude/settings.local.json` (project):

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

| Tool | Description |
|------|-------------|
| `get_github_contributions` | PRs merged, code reviews given, lines changed |
| `get_confluence_contributions` | Pages created/updated, comments added |
| `get_team_members` | List configured team members |

All tools support `start_date`, `end_date`, and `days` parameters for flexible date ranges.

## Goal Files

Store team member goals in `goals/<firstname-lastname>.md`. Copy from `goals/TEMPLATE.md`.

These are used by the `/performance-review` skill to evaluate contributions against stated objectives.

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
- Confluence: Generate a new token at https://id.atlassian.com/manage-profile/security/api-tokens

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

**Empty results**
- Verify the date range includes actual activity
- For Confluence, check that `space_keys` match your space keys exactly
