import asyncio
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
#
# Native JS dialogs (alert/confirm/prompt/beforeunload) block the
# page entirely until accept()/dismiss() is called. If nobody
# handles them, automation just hangs forever -- this is a very
# common way headless browser automation silently freezes.

_dialog_handler = None
_monitored_page = None

_mode = "accept"          # "accept" | "dismiss" | "manual"
_auto_timeout_s = 20       # manual-mode safety net
_enabled = False           # was dialog handling ever explicitly started?

_dialog_log = []
_pending = None           # {"dialog": <Dialog>, "type", "message", "default_value", "time"}


def _detach_existing():
    global _dialog_handler, _monitored_page
    if _monitored_page is not None and not _monitored_page.is_closed():
        try:
            if _dialog_handler is not None:
                _monitored_page.remove_listener("dialog", _dialog_handler)
        except Exception:
            pass
    _dialog_handler = None
    _monitored_page = None


# ============================================================
# START / STOP
# ============================================================

async def dialog_start_handling(mode: str = "accept", auto_timeout: int = 20):
    """
    Attach a dialog listener to the current page.

    mode:
        "accept"  - every alert/confirm/prompt is auto-accepted
                    immediately (default OK / empty prompt text)
        "dismiss" - every dialog is auto-dismissed (cancel)
        "manual"  - dialogs are held open and reported via
                    dialog_get_pending(); the caller must resolve
                    them with dialog_accept()/dialog_dismiss().
                    A safety timeout auto-dismisses a manual
                    dialog after `auto_timeout` seconds so a
                    forgotten dialog can never hang the browser
                    forever.
    """
    global _mode, _auto_timeout_s, _dialog_handler, _monitored_page

    if mode not in ("accept", "dismiss", "manual"):
        return {
            "success": False,
            "error": 'mode must be one of "accept", "dismiss", "manual".',
        }

    try:
        page = await _get_page()

        _detach_existing()

        _mode = mode
        _auto_timeout_s = max(1, int(auto_timeout))

        async def _on_dialog(dialog):
            global _pending

            entry = {
                "type": dialog.type,
                "message": dialog.message,
                "default_value": getattr(dialog, "default_value", None),
                "time": time.time(),
            }
            _dialog_log.append(entry)

            if _mode == "accept":
                try:
                    await dialog.accept()
                except Exception:
                    pass
                entry["resolved"] = "accepted"
                return

            if _mode == "dismiss":
                try:
                    await dialog.dismiss()
                except Exception:
                    pass
                entry["resolved"] = "dismissed"
                return

            # manual mode -- hold it open, but never forever
            _pending = {**entry, "dialog": dialog}

            async def _auto_release():
                await asyncio.sleep(_auto_timeout_s)
                global _pending
                if _pending is not None and _pending.get("dialog") is dialog:
                    try:
                        await dialog.dismiss()
                    except Exception:
                        pass
                    entry["resolved"] = "auto_dismissed_timeout"
                    _pending = None

            asyncio.ensure_future(_auto_release())

        _dialog_handler = _on_dialog
        _monitored_page = page
        page.on("dialog", _dialog_handler)

        global _enabled
        _enabled = True

        return {
            "success": True,
            "action": "dialog_start_handling",
            "mode": _mode,
            "auto_timeout": _auto_timeout_s,
        }

    except Exception as error:
        return {"success": False, "error": str(error)}


async def dialog_stop_handling():
    try:
        _detach_existing()
        global _enabled
        _enabled = False
        return {"success": True, "action": "dialog_stop_handling"}
    except Exception as error:
        return {"success": False, "error": str(error)}


async def reattach_if_active():
    """
    Re-attach dialog handling (same mode/timeout as before) to
    whatever page is now active. Called automatically by
    tabs.py after switch_tab()/new_tab(), so dialog handling
    follows the active tab instead of staying pinned to whichever
    page was active when dialog_start_handling() was first called.
    """
    if not _enabled:
        return {"success": True, "skipped": True}

    try:
        return await dialog_start_handling(mode=_mode, auto_timeout=_auto_timeout_s)
    except Exception as error:
        return {"success": False, "error": str(error)}


# ============================================================
# MANUAL RESOLUTION
# ============================================================

async def dialog_get_pending():
    """Return info about the currently open (unresolved) manual dialog, if any."""
    if _pending is None:
        return {"success": True, "pending": None}

    return {
        "success": True,
        "pending": {
            "type": _pending["type"],
            "message": _pending["message"],
            "default_value": _pending["default_value"],
        },
    }


async def dialog_accept(prompt_text: str = None):
    """Accept the currently pending manual dialog (optionally supplying prompt text)."""
    global _pending

    if _pending is None:
        return {
            "success": False,
            "error": "No pending dialog to accept.",
        }

    dialog = _pending["dialog"]
    entry_type = _pending["type"]

    try:
        if prompt_text is not None:
            await dialog.accept(prompt_text)
        else:
            await dialog.accept()

        _pending = None

        return {
            "success": True,
            "action": "dialog_accept",
            "type": entry_type,
        }

    except Exception as error:
        _pending = None
        return {"success": False, "error": str(error)}


async def dialog_dismiss():
    """Dismiss (cancel) the currently pending manual dialog."""
    global _pending

    if _pending is None:
        return {
            "success": False,
            "error": "No pending dialog to dismiss.",
        }

    dialog = _pending["dialog"]
    entry_type = _pending["type"]

    try:
        await dialog.dismiss()
        _pending = None

        return {
            "success": True,
            "action": "dialog_dismiss",
            "type": entry_type,
        }

    except Exception as error:
        _pending = None
        return {"success": False, "error": str(error)}


# ============================================================
# HISTORY
# ============================================================

async def dialog_get_log(limit: int = 50):
    limit = max(1, int(limit))

    log = [
        {k: v for k, v in entry.items() if k != "dialog"}
        for entry in _dialog_log[-limit:]
    ]

    return {
        "success": True,
        "count": len(log),
        "log": log,
    }


async def dialog_clear_log():
    _dialog_log.clear()
    return {"success": True, "action": "dialog_clear_log"}


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "dialog_start_handling",
    "dialog_stop_handling",
    "reattach_if_active",
    "dialog_get_pending",
    "dialog_accept",
    "dialog_dismiss",
    "dialog_get_log",
    "dialog_clear_log",
]
