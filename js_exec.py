"""
Raj Browser MCP — Generic JavaScript Execution

A single escape-hatch tool to run arbitrary JS on the page when
no dedicated tool covers what's needed. Powerful, so it carries
a lightweight guard against the most obvious credential-
exfiltration pattern (reading cookies/localStorage and shipping
them off in the same script) -- everything else is allowed,
since this is a personal automation tool, not a locked-down
sandbox for untrusted input.
"""

import re

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
# LIGHTWEIGHT SAFETY GUARD
# ============================================================

_READS_CREDENTIALS = re.compile(
    r"document\.cookie|localStorage\.|sessionStorage\.",
    re.IGNORECASE,
)

_EXFIL_SINKS = re.compile(
    r"fetch\s*\(|XMLHttpRequest|new\s+Image\s*\(|navigator\.sendBeacon",
    re.IGNORECASE,
)


def _check_script_safety(script: str):
    """
    Block scripts that both read credential-like storage AND ship
    data somewhere in the same call -- the classic exfiltration
    shape. Reading cookies alone, or making a fetch call alone,
    is fine; the combination is what's blocked.
    """
    if not isinstance(script, str):
        return {"blocked": True, "reason": "Script must be a string."}

    if _READS_CREDENTIALS.search(script) and _EXFIL_SINKS.search(script):
        return {
            "blocked": True,
            "reason": (
                "This script reads cookies/storage AND sends "
                "data over the network in the same call, which "
                "matches a credential-exfiltration pattern. "
                "Split the read and the send into two separate "
                "execute_js calls if this was intentional and "
                "safe (e.g. debugging your own site)."
            ),
        }

    return {"blocked": False}


# ============================================================
# GENERIC EXECUTION
# ============================================================

async def execute_js(script: str, arg=None, timeout: int = 10000):
    """
    Run arbitrary JavaScript in the page context.

    script: a JS expression or function, e.g.
        "() => document.title"
        "(x) => x * 2"
    arg: optional single argument passed to the function form.
    """
    try:
        guard = _check_script_safety(script)
        if guard["blocked"]:
            return {"success": False, "action": "execute_js", "error": guard["reason"]}

        page = await _get_page()

        if arg is not None:
            result = await page.evaluate(script, arg)
        else:
            result = await page.evaluate(script)

        return {"success": True, "action": "execute_js", "result": result}

    except Exception as error:
        return {"success": False, "action": "execute_js", "error": str(error)}


async def execute_js_on_element(selector: str, script: str, timeout: int = 10000):
    """
    Run JS with a specific DOM element bound as the function's
    argument, e.g. script="(el) => el.getAttribute('href')".
    """
    try:
        guard = _check_script_safety(script)
        if guard["blocked"]:
            return {
                "success": False,
                "action": "execute_js_on_element",
                "error": guard["reason"],
            }

        page = await _get_page()

        if not isinstance(selector, str) or not selector.strip():
            raise ValueError("Selector cannot be empty.")

        locator = page.locator(selector).first
        await locator.wait_for(state="attached", timeout=max(100, int(timeout)))

        result = await locator.evaluate(script)

        return {
            "success": True,
            "action": "execute_js_on_element",
            "selector": selector,
            "result": result,
        }

    except Exception as error:
        return {
            "success": False,
            "action": "execute_js_on_element",
            "selector": selector,
            "error": str(error),
        }


async def execute_js_on_ref(ref: str, script: str, timeout: int = 10000):
    """Same as execute_js_on_element(), but targets an accessibility ref."""
    import accessibility

    check = await accessibility.resolve_ref(ref)
    if not check.get("success"):
        return check

    result = await execute_js_on_element(check["selector"], script, timeout=timeout)
    result["ref"] = ref
    return result


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "execute_js",
    "execute_js_on_element",
    "execute_js_on_ref",
]
