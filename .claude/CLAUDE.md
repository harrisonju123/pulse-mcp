# IC Tracker - Project Instructions

## Overview

This is an MCP server that provides tools for engineering managers to track team contributions across GitHub, Confluence, and Jira.

## Key Files

- `server.py` - MCP server entry point, registers all tools
- `ic_tracker/clients/` - API clients for GitHub, Confluence, Jira
- `ic_tracker/tools/` - MCP tool handlers
- `ic_tracker/models.py` - Data models and config classes
- `ic_tracker/config.py` - Config loading and validation
- `.claude/skills/` - Custom skills (performance-review, weekly-update)

## Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_jira_client.py -v

# Skip integration tests (require real API)
python -m pytest tests/ -v -m "not integration"
```

## Validating Config

```bash
IC_TRACKER_CONFIG=/path/to/config.json python server.py --validate
```

## Adding New Tools

1. Create handler in `ic_tracker/tools/`
2. Register in `server.py` in `get_tools()` and `handle_tool_call()`
3. Add tests in `tests/`

## Jira API Notes

- Uses new `/rest/api/3/search/jql` endpoint (POST, token-based pagination)
- Issue keys must be validated before use in JQL (injection prevention)
- Epic Link field ID varies by instance (`customfield_10014` is common default)
- Advanced Roadmaps (Plans) hierarchy isn't captured by standard parent links
