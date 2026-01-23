#!/bin/bash
# IC Tracker MCP Server Setup Script
# Works with Claude Code and Cursor

set -e

# Windows detection
if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]] || [[ -n "$WINDIR" ]]; then
    echo "Error: This script doesn't support Windows directly."
    echo
    echo "For Windows, use manual setup:"
    echo "  1. python -m venv .venv"
    echo "  2. .venv\\Scripts\\activate"
    echo "  3. pip install -r requirements.txt"
    echo "  4. copy config.example.json config.json"
    echo "  5. Edit config.json with your values"
    echo "  6. python server.py --validate"
    echo
    echo "See README.md for MCP configuration paths."
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== IC Tracker MCP Setup ==="
echo

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not found"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Found Python $PYTHON_VERSION"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate and install dependencies
echo "Installing dependencies..."
source .venv/bin/activate
pip install -q -r requirements.txt

# Check for config file
if [ ! -f "config.json" ]; then
    echo
    echo "No config.json found. Creating from template..."
    cp config.example.json config.json
    echo "Please edit config.json with your API tokens and team members."
    echo
    echo "GitHub-only? Remove the 'confluence' and 'jira' sections entirely."
    echo "Use 'N/A' for atlassian_account_id if not using Confluence/Jira."
    echo
    echo "IMPORTANT for Jira:"
    echo "  - Check your Jira URL (some orgs have separate instances)"
    echo "  - Add all project keys you want to query"
    echo
    echo "See README.md for details on getting tokens and custom field IDs."
    echo
fi

# Generate MCP config
echo
echo "=== MCP Configuration ==="
echo

# Claude Code config
CLAUDE_CONFIG=$(cat <<EOF
{
  "mcpServers": {
    "ic-tracker": {
      "command": "$SCRIPT_DIR/.venv/bin/python",
      "args": ["$SCRIPT_DIR/server.py"],
      "env": {
        "IC_TRACKER_CONFIG": "$SCRIPT_DIR/config.json"
      }
    }
  }
}
EOF
)

# Cursor config (same format, different location)
CURSOR_CONFIG=$(cat <<EOF
{
  "mcpServers": {
    "ic-tracker": {
      "command": "$SCRIPT_DIR/.venv/bin/python",
      "args": ["$SCRIPT_DIR/server.py"],
      "env": {
        "IC_TRACKER_CONFIG": "$SCRIPT_DIR/config.json"
      }
    }
  }
}
EOF
)

echo "--- For Claude Code ---"
echo
echo "Config location: ~/.claude/mcp_settings.json"
echo
echo "Add this to your mcp_settings.json:"
echo
echo "$CLAUDE_CONFIG"
echo

# Offer to auto-install for Claude Code
if [ -d "$HOME/.claude" ]; then
    read -p "Auto-install to ~/.claude/mcp_settings.json? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        MCP_SETTINGS="$HOME/.claude/mcp_settings.json"
        if [ -f "$MCP_SETTINGS" ]; then
            # Merge with existing config using Python
            python3 -c "
import json
import sys

new_server = {
    'ic-tracker': {
        'command': '$SCRIPT_DIR/.venv/bin/python',
        'args': ['$SCRIPT_DIR/server.py'],
        'env': {
            'IC_TRACKER_CONFIG': '$SCRIPT_DIR/config.json'
        }
    }
}

with open('$MCP_SETTINGS', 'r') as f:
    config = json.load(f)

if 'mcpServers' not in config:
    config['mcpServers'] = {}

config['mcpServers'].update(new_server)

with open('$MCP_SETTINGS', 'w') as f:
    json.dump(config, f, indent=2)

print('Updated $MCP_SETTINGS')
"
        else
            echo "$CLAUDE_CONFIG" > "$MCP_SETTINGS"
            echo "Created $MCP_SETTINGS"
        fi
        echo
        echo "Restart Claude Code for changes to take effect."
        echo
    fi
fi

echo "--- For Cursor ---"
echo
echo "Add to: ~/.cursor/mcp.json"
echo
echo "$CURSOR_CONFIG"
echo

# Offer to validate
echo "=== Validation ==="
if [ -f "config.json" ]; then
    read -p "Run validation to test your API connections? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        python server.py --validate
    fi
else
    echo "Skipping validation - configure config.json first, then run:"
    echo "  $SCRIPT_DIR/.venv/bin/python $SCRIPT_DIR/server.py --validate"
fi

echo
echo "Setup complete!"
