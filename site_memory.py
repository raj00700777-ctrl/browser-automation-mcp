"""
Raj Browser MCP — Self-Improving Site Memory

Most automation starts from zero on every site, every time.
This module gives the MCP a persistent, per-domain memory: once
it has found "the search box" or "the login button" on
youtube.com, it remembers exactly where that was -- so the next
time (even in a completely new session, days later) it can go
straight there instead of re-discovering it from scratch.

It's built entirely on top of the existing finder.py (natural-
language element discovery) -- this module just adds a
persistent cache layer with confidence tracking in front of it:

    smart_find("search_box", "the search input", domain=...)
        1. Do we already know "search_box" for this domain?
           -> verify the remembered selector still resolves on
              the CURRENT page (sites redesign -- a stale memory
              must never be trusted blindly).
           -> if valid: instant hit, no re-discovery needed.
        2. If not remembered, or the remembered selector no
           longer resolves: fall back to finder.find_element()
           (the existing smart finder), and if it succeeds,
           remember the result for next time.
        3. Every use can report back success/failure via
           record_outcome() -- a selector that keeps failing
           gets demoted and eventually re-discovered fresh
           instead of being trusted forever.

Storage is a single JSON file on disk, so memory survives
across MCP server restarts, not just within one session.
"""

import json
import os
import re
import time
from urllib.parse import urlparse

from browser import browser


# ============================================================
# STORAGE
# ============================================================

_STORAGE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "site_memory.json"
)

_CONFIDENCE_DEMOTE_THRESHOLD = -2   # net (success - failure) score below this = forget it
_MAX_KEYS_PER_DOMAIN = 200          # sanity cap so memory can't grow unbounded


def _ensure_storage_dir():
    os.makedirs(os.path.dirname(_STORAGE_PATH), exist_ok=True)


def _load_store():
    _ensure_storage_dir()
    if not os.path.exists(_STORAGE_PATH):
        return {}
    try:
        with open(_STORAGE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # Corrupt/partial file -- don't crash the whole automation
        # over a broken cache, just start fresh.
        return {}


def _save_store(store):
    _ensure_storage_dir()
    tmp_path = _STORAGE_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2)
    os.replace(tmp_path, _STORAGE_PATH)   # atomic on both Windows and POSIX


def _domain_from_url(url: str) -> str:
    try:
        host = (urlparse(url).hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


async def _current_domain():
    page = await browser.get_page()
    return _domain_from_url(page.url)


# ============================================================
# LOW-LEVEL REMEMBER / RECALL
# ============================================================

async def remember_selector(
    domain: str,
    key: str,
    selector: str,
    role: str = None,
    name: str = None,
):
    """
    Save (or overwrite) a learned selector for `key` on `domain`.
    key is a short, meaningful label like "search_box",
    "login_button", "add_to_cart", "price" -- whatever the
    caller wants to remember by.
    """
    try:
        store = _load_store()
        domain_entries = store.setdefault(domain, {})

        if len(domain_entries) >= _MAX_KEYS_PER_DOMAIN and key not in domain_entries:
            # Evict the least successful entry to make room rather
            # than growing the file forever on very key-heavy sites.
            worst_key = min(
                domain_entries,
                key=lambda k: domain_entries[k].get("score", 0),
            )
            del domain_entries[worst_key]

        domain_entries[key] = {
            "selector": selector,
            "role": role,
            "name": name,
            "score": domain_entries.get(key, {}).get("score", 0),
            "success_count": domain_entries.get(key, {}).get("success_count", 0),
            "fail_count": domain_entries.get(key, {}).get("fail_count", 0),
            "last_updated": time.time(),
        }

        _save_store(store)

        return {"success": True, "action": "remember_selector", "domain": domain, "key": key}

    except Exception as error:
        return {"success": False, "error": str(error)}


async def recall_selector(domain: str, key: str):
    """Look up a remembered selector for domain+key, without verifying it against a live page."""
    try:
        store = _load_store()
        entry = store.get(domain, {}).get(key)

        if entry is None:
            return {"success": True, "found": False}

        return {"success": True, "found": True, "entry": entry}

    except Exception as error:
        return {"success": False, "error": str(error)}


async def record_outcome(domain: str, key: str, success: bool):
    """
    Report back whether a remembered (or freshly discovered)
    selector actually worked when used. Selectors that keep
    failing get demoted and eventually dropped, so a site
    redesign doesn't leave automation stuck reusing a dead
    selector forever.
    """
    try:
        store = _load_store()
        domain_entries = store.get(domain, {})
        entry = domain_entries.get(key)

        if entry is None:
            return {"success": False, "error": f"No memory for {domain}/{key} to update."}

        if success:
            entry["success_count"] = entry.get("success_count", 0) + 1
            entry["score"] = entry.get("score", 0) + 1
        else:
            entry["fail_count"] = entry.get("fail_count", 0) + 1
            entry["score"] = entry.get("score", 0) - 1

        forgotten = False
        if entry["score"] <= _CONFIDENCE_DEMOTE_THRESHOLD:
            del domain_entries[key]
            forgotten = True
        else:
            domain_entries[key] = entry

        store[domain] = domain_entries
        _save_store(store)

        return {
            "success": True,
            "action": "record_outcome",
            "domain": domain,
            "key": key,
            "forgotten": forgotten,
            "score": entry["score"] if not forgotten else None,
        }

    except Exception as error:
        return {"success": False, "error": str(error)}


# ============================================================
# HIGH-LEVEL: MEMORY-BACKED SMART FIND
# ============================================================

async def smart_find(key: str, description: str, domain: str = None, timeout: int = 10000):
    """
    The main entry point. Tries memory first, falls back to
    finder.find_element() (natural-language discovery) if needed,
    and learns from a successful fallback so next time is instant.

    key: short label to remember this element by (e.g. "search_box")
    description: natural-language description, passed to finder.py
                 if memory doesn't have (or can no longer verify) an
                 answer -- e.g. "the main search input"
    domain: defaults to the current page's hostname if omitted
    """
    try:
        import finder

        page = await browser.get_page()
        current_domain = _domain_from_url(page.url)

        if domain is None:
            domain = current_domain
        elif domain != current_domain:
            # The caller asked for a specific domain's memory, but
            # the browser isn't actually there right now -- searching
            # whatever page IS open and filing it under the wrong
            # domain key would silently poison the memory. Fail
            # loudly instead of guessing.
            return {
                "success": False,
                "error": (
                    f"Requested domain '{domain}' but the browser is "
                    f"currently on '{current_domain}' ({page.url}). "
                    f"Navigate to {domain} first, or omit domain= to "
                    f"use whatever page is currently open."
                ),
            }

        if not domain:
            return {"success": False, "error": "Could not determine domain for the current page."}

        # --- Step 1: try memory ---
        recalled = await recall_selector(domain, key)

        if recalled.get("found"):
            selector = recalled["entry"]["selector"]
            try:
                count = await page.locator(selector).count()
            except Exception:
                count = 0

            if count > 0:
                return {
                    "success": True,
                    "source": "memory",
                    "domain": domain,
                    "key": key,
                    "selector": selector,
                    "score": recalled["entry"].get("score", 0),
                }
            # Selector no longer resolves (site changed) -- fall
            # through to rediscovery instead of trusting stale memory.

        # --- Step 2: fall back to natural-language discovery ---
        discovered = await finder.find_element(description)

        if not discovered.get("success") or not discovered.get("best_match"):
            return {
                "success": False,
                "source": "discovery",
                "domain": domain,
                "key": key,
                "error": f"Could not find an element matching '{description}' on {domain}.",
            }

        best = discovered["best_match"]
        selector = best["selector"]

        # --- Step 3: remember it for next time ---
        await remember_selector(domain, key, selector, role=best.get("type"), name=best.get("text"))

        return {
            "success": True,
            "source": "discovery",
            "domain": domain,
            "key": key,
            "selector": selector,
            "learned": True,
        }

    except Exception as error:
        return {"success": False, "error": str(error)}


# ============================================================
# INTROSPECTION / MANAGEMENT
# ============================================================

async def list_known_domains():
    try:
        store = _load_store()
        return {"success": True, "count": len(store), "domains": sorted(store.keys())}
    except Exception as error:
        return {"success": False, "error": str(error)}


async def get_domain_memory(domain: str):
    try:
        store = _load_store()
        return {"success": True, "domain": domain, "entries": store.get(domain, {})}
    except Exception as error:
        return {"success": False, "error": str(error)}


async def forget_domain(domain: str):
    try:
        store = _load_store()
        existed = domain in store
        store.pop(domain, None)
        _save_store(store)
        return {"success": True, "domain": domain, "existed": existed}
    except Exception as error:
        return {"success": False, "error": str(error)}


async def forget_selector(domain: str, key: str):
    try:
        store = _load_store()
        existed = key in store.get(domain, {})
        if domain in store and key in store[domain]:
            del store[domain][key]
            if not store[domain]:
                del store[domain]
            _save_store(store)
        return {"success": True, "domain": domain, "key": key, "existed": existed}
    except Exception as error:
        return {"success": False, "error": str(error)}


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "remember_selector",
    "recall_selector",
    "record_outcome",
    "smart_find",
    "list_known_domains",
    "get_domain_memory",
    "forget_domain",
    "forget_selector",
]
