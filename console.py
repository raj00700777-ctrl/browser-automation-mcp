"""
Raj Browser MCP — Browser Console Logs + JS Errors

Captures REAL console output (log/info/warn/error/debug) via
Playwright's native page.on("console") event, plus uncaught
exceptions via page.on("pageerror"). Both are Page-level events
that persist automatically across navigations -- no JS injection
or add_init_script trickery needed, and nothing is lost on
page.goto().
"""

import time

from browser import browser


# ============================================================
# PAGE ACCESS
# ============================================================

async def _get_page():
    page = await browser.get_page()

    if page is None:
        raise RuntimeError("No active browser page available.")

    return page


# ============================================================
# STATE
# ============================================================

_console_handler = None
_pageerror_handler = None
_monitored_page = None

_logs = []          # every console.* message
_page_errors = []   # uncaught exceptions / unhandled rejections

_MAX_ENTRIES = 2000


def _detach_existing():
    global _console_handler, _pageerror_handler, _monitored_page
    if _monitored_page is not None and not _monitored_page.is_closed():
        try:
            if _console_handler is not None:
                _monitored_page.remove_listener("console", _console_handler)
            if _pageerror_handler is not None:
                _monitored_page.remove_listener("pageerror", _pageerror_handler)
        except Exception:
            pass
    _console_handler = None
    _pageerror_handler = None
    _monitored_page = None


# ============================================================
# START / STOP
# ============================================================

async def console_start_monitoring():
    """
    Attach real console + uncaught-exception listeners to the
    current page. Safe to call multiple times -- any previous
    listeners are detached first so entries never get duplicated.
    """
    try:
        page = await _get_page()

        _detach_existing()

        def _on_console(msg):
            try:
                location = msg.location or {}
            except Exception:
                location = {}

            _logs.append({
                "level": msg.type,          # log | info | warning | error | debug ...
                "text": msg.text,
                "url": location.get("url"),
                "line": location.get("lineNumber"),
                "time": time.time(),
            })
            if len(_logs) > _MAX_ENTRIES:
                del _logs[: len(_logs) - _MAX_ENTRIES]

        def _on_pageerror(error):
            _page_errors.append({
                "message": str(error),
                "time": time.time(),
            })
            if len(_page_errors) > _MAX_ENTRIES:
                del _page_errors[: len(_page_errors) - _MAX_ENTRIES]

        global _console_handler, _pageerror_handler, _monitored_page
        _console_handler = _on_console
        _pageerror_handler = _on_pageerror
        _monitored_page = page

        page.on("console", _console_handler)
        page.on("pageerror", _pageerror_handler)

        return {
            "success": True,
            "message": "Console monitoring started (native, navigation-persistent)",
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


async def console_stop_monitoring():
    try:
        _detach_existing()
        return {"success": True, "message": "Console monitoring stopped"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================
# READ LOGS
# ============================================================

async def console_get_logs(level: str = None, limit: int = 200):
    """
    Get captured console messages.
    level: optional filter -- "log" | "info" | "warning" | "error" | "debug"
    """
    try:
        limit = max(1, int(limit))
        logs = _logs

        if level:
            logs = [l for l in logs if l.get("level") == level]

        logs = logs[-limit:]

        return {"success": True, "logs": logs, "count": len(logs)}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def console_get_errors(limit: int = 200):
    """
    Get real console.error(...) calls AND uncaught exceptions /
    unhandled promise rejections, combined and time-sorted.
    """
    try:
        limit = max(1, int(limit))

        console_errors = [
            {**l, "source": "console.error"} for l in _logs if l.get("level") == "error"
        ]
        exceptions = [
            {**e, "source": "uncaught_exception"} for e in _page_errors
        ]

        combined = sorted(
            console_errors + exceptions,
            key=lambda x: x.get("time", 0),
        )[-limit:]

        return {"success": True, "errors": combined, "count": len(combined)}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def console_has_errors():
    try:
        count = len([l for l in _logs if l.get("level") == "error"]) + len(_page_errors)
        return {"success": True, "has_errors": count > 0, "error_count": count}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def console_clear():
    try:
        _logs.clear()
        _page_errors.clear()
        return {"success": True, "message": "Console logs cleared"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "console_start_monitoring",
    "console_stop_monitoring",
    "console_get_logs",
    "console_get_errors",
    "console_has_errors",
    "console_clear",
]
