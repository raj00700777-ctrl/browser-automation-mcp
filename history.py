"""
Raj Browser MCP — Action Logging + Statistics
"""

from datetime import datetime
from collections import Counter

_history = []


def log_action(action: str, details: dict = None):
    entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "details": details or {},
    }
    _history.append(entry)
    return {"success": True, "logged": entry}


def get_history(limit: int = 100):
    return {"success": True, "history": _history[-limit:], "total": len(_history)}


def get_last_action():
    if not _history:
        return {"success": False, "error": "No actions logged"}
    return {"success": True, "action": _history[-1]}


def clear_history():
    _history.clear()
    return {"success": True, "message": "History cleared"}


def get_statistics():
    counts = Counter(h["action"] for h in _history)
    return {
        "success": True,
        "total_actions": len(_history),
        "breakdown": dict(counts),
        "most_common": counts.most_common(5),
    }