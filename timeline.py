"""
Raj Browser MCP — Time-Travel DOM Debugging

When automation fails, the usual output is just an error message
-- you don't get to see what the page actually looked like at
that exact moment, or what changed on it in the seconds before
things went wrong. This module fixes that.

Two halves:

1. A lightweight, always-on MutationObserver (injected via
   add_init_script so it survives navigation, same trick as
   console.py) that keeps a compact rolling log of what changed
   on the page -- node added/removed, attribute changed, text
   changed -- with timestamps. Cheap enough to leave running.

2. "Checkpoints" -- an explicit (or automatic-on-failure)
   snapshot of the page at a moment in time: a screenshot + the
   full HTML, saved to disk and indexed. Given two checkpoints,
   timeline_diff() produces a readable diff of what actually
   changed between them (HTML diff + the mutation events that
   happened in between) -- so instead of "step 4 failed", you get
   "here's exactly what the page looked like right before it
   failed, and everything that changed in the 3 seconds before
   that".

recovery.py calls timeline_auto_checkpoint() on every failure it
sees (best-effort, never blocks the actual error path), so this
happens automatically without needing to remember to call it.
"""

import difflib
import json
import os
import time

from browser import browser


# ============================================================
# STORAGE
# ============================================================

_TIMELINE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "timeline"
)
_INDEX_PATH = os.path.join(_TIMELINE_DIR, "index.json")

_MAX_MUTATIONS_CLIENT_SIDE = 500   # cap kept inside the page's own JS array


def _ensure_dir():
    os.makedirs(_TIMELINE_DIR, exist_ok=True)


def _load_index():
    _ensure_dir()
    if not os.path.exists(_INDEX_PATH):
        return []
    try:
        with open(_INDEX_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_index(index):
    _ensure_dir()
    tmp = _INDEX_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)
    os.replace(tmp, _INDEX_PATH)


async def _get_page():
    page = await browser.get_page()
    if page is None:
        raise RuntimeError("No active browser page available.")
    return page


# ============================================================
# MUTATION OBSERVER (client-side change log)
# ============================================================

_OBSERVER_INIT_SCRIPT = f"""
() => {{
    if (window.__raj_timeline_installed) return;
    window.__raj_timeline_installed = true;
    window.__raj_mutations = [];

    const MAX = {_MAX_MUTATIONS_CLIENT_SIDE};

    function describe(node) {{
        if (!node || node.nodeType !== 1) return null;
        return {{
            tag: node.tagName ? node.tagName.toLowerCase() : null,
            id: node.id || null,
            class: (node.className || '').toString().slice(0, 80) || null,
        }};
    }}

    function record(entry) {{
        entry.time = Date.now() / 1000;
        window.__raj_mutations.push(entry);
        if (window.__raj_mutations.length > MAX) {{
            window.__raj_mutations.shift();
        }}
    }}

    function start() {{
        if (!document.body) {{
            setTimeout(start, 50);
            return;
        }}

        const observer = new MutationObserver((mutations) => {{
            for (const m of mutations) {{
                if (m.type === 'childList') {{
                    if (m.addedNodes.length) {{
                        record({{
                            type: 'added',
                            target: describe(m.target),
                            count: m.addedNodes.length,
                            sample: describe(m.addedNodes[0]),
                        }});
                    }}
                    if (m.removedNodes.length) {{
                        record({{
                            type: 'removed',
                            target: describe(m.target),
                            count: m.removedNodes.length,
                            sample: describe(m.removedNodes[0]),
                        }});
                    }}
                }} else if (m.type === 'attributes') {{
                    record({{
                        type: 'attribute',
                        target: describe(m.target),
                        attribute: m.attributeName,
                        value: m.target.getAttribute
                            ? (m.target.getAttribute(m.attributeName) || '').slice(0, 100)
                            : null,
                    }});
                }} else if (m.type === 'characterData') {{
                    record({{
                        type: 'text',
                        value: (m.target.textContent || '').slice(0, 100),
                    }});
                }}
            }}
        }});

        observer.observe(document.body, {{
            childList: true,
            attributes: true,
            characterData: true,
            subtree: true,
        }});

        window.__raj_timeline_observer = observer;
    }}

    start();
}}
"""


async def timeline_start():
    """
    Start the always-on DOM mutation log. Uses add_init_script so
    it re-installs itself automatically after every navigation --
    call this once per session, not once per page.
    """
    try:
        page = await _get_page()
        await page.add_init_script(_OBSERVER_INIT_SCRIPT)
        # Also apply immediately to whatever's already loaded.
        try:
            await page.evaluate(_OBSERVER_INIT_SCRIPT)
        except Exception:
            pass
        return {"success": True, "message": "Time-travel DOM timeline started (navigation-persistent)"}
    except Exception as error:
        return {"success": False, "error": str(error)}


async def timeline_get_mutations(since: float = None, limit: int = 200):
    """Pull the recorded mutation log, optionally only entries after `since` (unix timestamp)."""
    try:
        page = await _get_page()
        mutations = await page.evaluate("() => window.__raj_mutations || []")

        if since is not None:
            mutations = [m for m in mutations if m.get("time", 0) >= since]

        mutations = mutations[-max(1, int(limit)):]

        return {"success": True, "count": len(mutations), "mutations": mutations}
    except Exception as error:
        return {"success": False, "error": str(error)}


async def timeline_clear_mutations():
    try:
        page = await _get_page()
        await page.evaluate("() => { window.__raj_mutations = []; }")
        return {"success": True, "message": "Mutation log cleared"}
    except Exception as error:
        return {"success": False, "error": str(error)}


# ============================================================
# CHECKPOINTS (screenshot + HTML snapshot at a moment in time)
# ============================================================

async def timeline_checkpoint(label: str = None):
    """
    Save a full checkpoint of the page RIGHT NOW: a screenshot and
    the complete HTML, indexed and retrievable later. Use this
    before/after risky steps ("before_login", "after_submit") so
    you can diff exactly what changed.
    """
    try:
        page = await _get_page()
        _ensure_dir()

        ts = time.time()
        safe_label = (label or "checkpoint").replace(" ", "_")[:60]
        base_name = f"{int(ts * 1000)}_{safe_label}"

        screenshot_path = os.path.join(_TIMELINE_DIR, base_name + ".png")
        html_path = os.path.join(_TIMELINE_DIR, base_name + ".html")

        try:
            await page.screenshot(path=screenshot_path)
        except Exception:
            screenshot_path = None

        html = await page.content()
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

        entry = {
            "label": label,
            "time": ts,
            "url": page.url,
            "title": await page.title(),
            "screenshot": screenshot_path,
            "html": html_path,
        }

        index = _load_index()
        index.append(entry)
        _save_index(index)

        return {"success": True, "action": "timeline_checkpoint", "checkpoint": entry}

    except Exception as error:
        return {"success": False, "error": str(error)}


async def timeline_auto_checkpoint(reason: str):
    """
    Best-effort automatic checkpoint, meant to be called by
    recovery.py right when an action fails. Never raises -- a
    debugging aid must never itself break the real error path.
    """
    try:
        return await timeline_checkpoint(label=f"auto_error_{reason}"[:60])
    except Exception:
        return {"success": False}


async def timeline_list_checkpoints(limit: int = 100):
    try:
        index = _load_index()
        return {"success": True, "count": len(index), "checkpoints": index[-max(1, int(limit)):]}
    except Exception as error:
        return {"success": False, "error": str(error)}


async def timeline_clear_checkpoints():
    try:
        index = _load_index()
        for entry in index:
            for path_key in ("screenshot", "html"):
                p = entry.get(path_key)
                if p and os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass
        _save_index([])
        return {"success": True, "cleared": len(index)}
    except Exception as error:
        return {"success": False, "error": str(error)}


# ============================================================
# DIFF BETWEEN TWO CHECKPOINTS
# ============================================================

def _visible_text_lines(html: str):
    """
    Crude but dependency-free text extraction: strip tags, keep
    non-empty lines, for a readable diff instead of a wall of
    HTML tag noise.
    """
    import re
    text = re.sub(r"<script.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "\n", text)
    lines = [line.strip() for line in text.split("\n")]
    return [line for line in lines if line]


async def timeline_diff(index_a: int, index_b: int, max_lines: int = 80):
    """
    Diff two checkpoints (by their position in
    timeline_list_checkpoints(), most recent last -- so -1 and -2
    are the two most recent). Returns a readable text diff of
    visible content plus every mutation event recorded between
    the two checkpoint timestamps.
    """
    try:
        index = _load_index()

        if not (-len(index) <= index_a < len(index)) or not (-len(index) <= index_b < len(index)):
            return {"success": False, "error": f"Checkpoint index out of range (have {len(index)} checkpoints)."}

        a = index[index_a]
        b = index[index_b]

        with open(a["html"], "r", encoding="utf-8") as f:
            html_a = f.read()
        with open(b["html"], "r", encoding="utf-8") as f:
            html_b = f.read()

        lines_a = _visible_text_lines(html_a)
        lines_b = _visible_text_lines(html_b)

        diff = list(difflib.unified_diff(
            lines_a, lines_b,
            fromfile=a.get("label") or "checkpoint_a",
            tofile=b.get("label") or "checkpoint_b",
            lineterm="",
        ))[:max_lines]

        mutations_result = await timeline_get_mutations(
            since=min(a["time"], b["time"]), limit=300,
        )
        between = [
            m for m in mutations_result.get("mutations", [])
            if min(a["time"], b["time"]) <= m.get("time", 0) <= max(a["time"], b["time"])
        ]

        return {
            "success": True,
            "action": "timeline_diff",
            "checkpoint_a": {"label": a.get("label"), "time": a["time"], "url": a["url"]},
            "checkpoint_b": {"label": b.get("label"), "time": b["time"], "url": b["url"]},
            "text_diff": diff,
            "mutations_between": between,
            "mutation_count_between": len(between),
        }

    except Exception as error:
        return {"success": False, "error": str(error)}


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "timeline_start",
    "timeline_get_mutations",
    "timeline_clear_mutations",
    "timeline_checkpoint",
    "timeline_auto_checkpoint",
    "timeline_list_checkpoints",
    "timeline_clear_checkpoints",
    "timeline_diff",
]
