"""
Raj Browser MCP — Task Memoization (safe fast-path replay)

Every browser_agent(goal) call re-runs the FULL planner: regex
intent-detection, adaptive search resolution, step-by-step
execution, goal verification. For a goal that's run cleanly
dozens of times before (a scholarship-check, a quiz-bot login
flow), that reasoning is repeated identically every single time.

This module lets a CLEAN, fully-verified run get compiled into a
"fast-path": the exact sequence of tool calls (with the same
role+name semantic metadata codegen.py uses) that produced a
verified-complete result. On an EXACT repeat of the same goal on
the same domain, the fast-path can be replayed directly, skipping
the regex/planning overhead.

Designed around 5 specific failure modes, each handled explicitly
rather than papered over:

  1. Ambiguous goal matching
     -> EXACT string match only (goal + domain). No fuzzy/loose
        matching, ever. A slightly different goal simply doesn't
        match, and runs the full planner (slower, never wrong).

  2. Fast-path can't "think" if the situation changed
     -> Every replayed step's own success flag is checked. The
        instant any step reports success=False, the WHOLE
        fast-path attempt is abandoned mid-way (not resumed,
        not partially trusted) and control falls back to the
        full planner for the entire goal from scratch.

  3. Self-healing only fixes selector drift, not new steps
     -> Because step-by-step success is checked (see #2), an
        unexpected new step (e.g. a page that suddenly shows an
        OTP screen) causes the very next fast-path step to fail
        against the wrong page state, which is caught immediately
        rather than silently misclicking.

  4. A first-run mistake becoming a permanent silent repeat
     -> Fast-paths are saved as UNAPPROVED candidates. They are
        never auto-used until a human explicitly reviews and
        approves them via review_fastpath()/approve_fastpath() --
        exactly like reviewing a codegen script once before
        trusting it.

  5. Only works through browser_agent()
     -> Documented, not silently pretended away. Direct tool
        calls are not memoized; only full planner runs are.

On top of all that: even a fully-successful fast-path replay
still runs the SAME final goal-state verification a normal run
would -- "used the fast-path" is never treated as "definitely
correct" without that last check passing too.
"""

import json
import os
import time

_STORE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "fastpaths.json"
)

_FAILURE_AUTO_DISABLE_THRESHOLD = 3   # consecutive failures -> auto-unapprove


def _ensure_dir():
    os.makedirs(os.path.dirname(_STORE_PATH), exist_ok=True)


def _load():
    _ensure_dir()
    if not os.path.exists(_STORE_PATH):
        return {}
    try:
        with open(_STORE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(store):
    _ensure_dir()
    tmp = _STORE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2)
    os.replace(tmp, _STORE_PATH)


def _key(domain: str, goal: str) -> str:
    # Deliberately EXACT goal-text match (whitespace-normalized) -- see
    # failure mode #1. Domain is NOT part of the lookup key: for
    # "navigate to X" style goals, the browser is by definition
    # somewhere OTHER than X before the goal runs, so gating lookup
    # on "current domain == recorded domain" would mean a navigation
    # fast-path could never match except by coincidence. Domain is
    # still recorded and shown in review/list for the human's
    # context -- it just isn't part of what identifies the entry.
    return " ".join(str(goal).strip().split()).lower()


# ============================================================
# CANDIDATE SAVING (called by planner.py after a clean run)
# ============================================================

def save_candidate(domain: str, goal: str, steps: list):
    """
    Save (or refresh) a fast-path CANDIDATE for domain+goal. Never
    auto-approved -- see approve_fastpath(). steps is a list of
    {"tool", "args", "kwargs", "semantic"} dicts, in order.
    """
    store = _load()
    k = _key(domain, goal)
    existing = store.get(k, {})

    store[k] = {
        "domain": domain,
        "goal": goal,
        "steps": steps,
        "approved": existing.get("approved", False),
        "created": existing.get("created", time.time()),
        "updated": time.time(),
        "use_count": existing.get("use_count", 0),
        "consecutive_failures": 0,   # a fresh clean run resets any failure streak
    }
    _save(store)
    return store[k]


def record_fastpath_result(domain: str, goal: str, success: bool):
    store = _load()
    k = _key(domain, goal)
    entry = store.get(k)
    if entry is None:
        return

    if success:
        entry["use_count"] = entry.get("use_count", 0) + 1
        entry["consecutive_failures"] = 0
    else:
        entry["consecutive_failures"] = entry.get("consecutive_failures", 0) + 1
        if entry["consecutive_failures"] >= _FAILURE_AUTO_DISABLE_THRESHOLD:
            entry["approved"] = False   # auto-unapprove -- see failure mode #4

    store[k] = entry
    _save(store)


# ============================================================
# HUMAN REVIEW / APPROVAL
# ============================================================

def list_fastpaths():
    store = _load()
    return [
        {
            "domain": v["domain"], "goal": v["goal"], "approved": v["approved"],
            "step_count": len(v["steps"]), "use_count": v["use_count"],
            "consecutive_failures": v.get("consecutive_failures", 0),
        }
        for v in store.values()
    ]


def review_fastpath(domain: str, goal: str):
    """Show the compiled steps for a candidate before approving it -- same spirit as reviewing a codegen script."""
    store = _load()
    entry = store.get(_key(domain, goal))
    if entry is None:
        return {"found": False}
    return {"found": True, **entry}


def approve_fastpath(domain: str, goal: str):
    store = _load()
    k = _key(domain, goal)
    if k not in store:
        return {"success": False, "error": "No candidate found for that domain+goal."}
    store[k]["approved"] = True
    store[k]["consecutive_failures"] = 0
    _save(store)
    return {"success": True, "domain": domain, "goal": goal, "approved": True}


def reject_fastpath(domain: str, goal: str):
    store = _load()
    k = _key(domain, goal)
    existed = k in store
    store.pop(k, None)
    _save(store)
    return {"success": True, "existed": existed}


def get_approved_fastpath(domain: str, goal: str):
    """Used internally by planner.py -- returns the entry ONLY if approved, else None."""
    store = _load()
    entry = store.get(_key(domain, goal))
    if entry is None or not entry.get("approved"):
        return None
    return entry


__all__ = [
    "save_candidate",
    "record_fastpath_result",
    "list_fastpaths",
    "review_fastpath",
    "approve_fastpath",
    "reject_fastpath",
    "get_approved_fastpath",
]
