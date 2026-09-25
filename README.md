# Raj Browser MCP

A local browser-automation MCP server for Claude Desktop, built on
Playwright + Chrome DevTools Protocol. Connects to a real, visible
Chrome window (not headless, not a downloaded browser binary) so
you can watch automation happen live using your own installed
Chrome.

## Requirements

- Python 3.10+
- Google Chrome installed (auto-detected on Windows/Mac/Linux)
- `mcp` package **version 2.0.0 or newer** (see troubleshooting below)

## Setup

```bash
pip install -r requirements.txt
```

That's it -- no browser download step needed. This project connects
to your existing Chrome via CDP (`connect_over_cdp`), it never
launches Playwright's own bundled browser, so `playwright install`
is not required.

Add to your Claude Desktop MCP config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "Raj Browser MCP": {
      "command": "/full/absolute/path/to/python",
      "args": ["/full/absolute/path/to/server.py"]
    }
  }
}
```

**Use the FULL absolute path to your Python interpreter**, not just
`"python"` -- Claude Desktop's process often doesn't inherit your
shell's PATH, so a bare `"python"` command commonly fails to launch
on Windows even when `python` works fine in your terminal. Find your
interpreter's path with `where python` (Windows) or `which python3`
(Mac/Linux).

Restart Claude Desktop. The first tool call will launch Chrome
automatically.

### Custom Chrome location

If Chrome isn't auto-detected (non-standard install path), set an
environment variable:

```bash
RAJ_MCP_CHROME_PATH=/path/to/chrome
```

### Use an existing Chrome profile (keep your logins)

By default a fresh, empty automation profile is created inside the
project folder (`chrome_profile/`) so this works out of the box for
anyone who clones the repo. To reuse a profile you're already logged
into elsewhere, point at it explicitly:

```bash
RAJ_MCP_CHROME_PROFILE=/path/to/existing/chrome/profile
```

## Troubleshooting

**`ImportError: cannot import name 'MCPServer' from 'mcp.server'`**
Your `mcp` package is an older v1.x install (which used a class
called `FastMCP` instead). Upgrade it:
```bash
pip install --upgrade mcp
```

**Chrome doesn't launch / "Could not find a Chrome/Chromium
installation"**
Set `RAJ_MCP_CHROME_PATH` to your Chrome executable's full path (see
above).

## What's inside

147 tools across navigation, interaction, extraction, vision,
multi-tab/swarm execution, an AI goal-planner (`browser_agent`),
self-healing codegen, a semantic form-filler, a website
legitimacy/scam checker (RDAP + Wayback Machine + SSL
cross-referencing), performance profiling, and more -- see the
module docstrings in each `.py` file for details on a given area.

## Data & output directories

`data/`, `output/`, and `chrome_profile/` are created automatically
at runtime and are gitignored -- they hold your local browsing
session, screenshots, and learned automation state, and are never
meant to be committed.
