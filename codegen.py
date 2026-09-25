"""
Raj Browser MCP — Codegen

Converts the recorded action history (see history.py, now
auto-populated by every planner.py _run() call, or manually via
browser_log_action) into a standalone, runnable Playwright Python
script -- so a session driven interactively through Claude can be
replayed later without Claude/MCP in the loop at all.

The generated script connects over CDP the same way browser.py
does, so it reuses whatever Chrome profile / login session the
recording was made against.
"""

import os
import time

import history


# ============================================================
# ACTION -> CODE LINE MAPPING
# ============================================================
#
# Each mapper takes the (args, kwargs) that were passed to the
# underlying tool function and returns one or more lines of
# Playwright Python code. Unmapped/unknown actions still get
# emitted, just as a clearly-marked comment, so nothing recorded
# is silently dropped from the exported script.

def _arg(args, kwargs, index, name, default=None):
    """Pull a value positionally or by keyword, whichever was used."""
    if name in kwargs and kwargs[name] is not None:
        return kwargs[name]
    if len(args) > index:
        return args[index]
    return default


def _repr(value):
    return repr(value)


def _map_navigate(args, kwargs, semantic=None):
    url = _arg(args, kwargs, 0, "url")
    return [f"page.goto({_repr(url)}, wait_until='domcontentloaded')"]


# Mirrors navigation.py's curated site->URL table so open_site()
# actions compile into a real, runnable page.goto() instead of a
# comment -- kept as a static copy here (rather than importing
# navigation.py) so the generated script stays truly standalone.
_KNOWN_SITE_URLS = {
    "google": "https://www.google.com", "google.com": "https://www.google.com",
    "youtube": "https://www.youtube.com", "youtube.com": "https://www.youtube.com",
    "bing": "https://www.bing.com", "bing.com": "https://www.bing.com",
    "duckduckgo": "https://duckduckgo.com", "duckduckgo.com": "https://duckduckgo.com",
    "github": "https://github.com", "github.com": "https://github.com",
    "reddit": "https://www.reddit.com", "reddit.com": "https://www.reddit.com",
    "wikipedia": "https://www.wikipedia.org", "wikipedia.org": "https://www.wikipedia.org",
    "amazon": "https://www.amazon.com", "amazon.com": "https://www.amazon.com",
}


def _map_open_site(args, kwargs, semantic=None):
    site = _arg(args, kwargs, 0, "site")
    url = _KNOWN_SITE_URLS.get(str(site).strip().lower())
    if url:
        return [f"page.goto({_repr(url)}, wait_until='domcontentloaded')  # open_site({_repr(site)})"]
    return [f"# open_site({_repr(site)}) -- not in the known site table, resolve the real URL and use page.goto(...)"]


def _map_click(args, kwargs, semantic=None):
    selector = _arg(args, kwargs, 0, "selector")
    if semantic and semantic.get("name"):
        return [f"smart_click(page, {_repr(selector)}, role={_repr(semantic.get('role'))}, name={_repr(semantic.get('name'))})"]
    return [f"page.locator({_repr(selector)}).first.click()"]


def _map_type(args, kwargs, semantic=None):
    selector = _arg(args, kwargs, 0, "selector")
    text = _arg(args, kwargs, 1, "text", "")
    if semantic and semantic.get("name"):
        return [f"smart_type(page, {_repr(selector)}, {_repr(text)}, role={_repr(semantic.get('role'))}, name={_repr(semantic.get('name'))})"]
    return [
        f"page.locator({_repr(selector)}).first.fill('')",
        f"page.locator({_repr(selector)}).first.type({_repr(text)})",
    ]


def _map_press(args, kwargs, semantic=None):
    selector = _arg(args, kwargs, 0, "selector")
    key = _arg(args, kwargs, 1, "key", "Enter")
    return [f"page.locator({_repr(selector)}).first.press({_repr(key)})"]


def _map_scroll(args, kwargs, semantic=None):
    return ["page.mouse.wheel(0, 500)"]


def _map_wait(args, kwargs, semantic=None):
    seconds = _arg(args, kwargs, 0, "seconds", 1)
    return [f"page.wait_for_timeout({int(float(seconds) * 1000)})"]


def _map_screenshot(args, kwargs, semantic=None):
    return ["page.screenshot(path=f'screenshot_{int(time.time())}.png')"]


def _map_human_click(args, kwargs, semantic=None):
    selector = kwargs.get("selector") or (args[0] if args else None)
    if selector and semantic and semantic.get("name"):
        return [
            "# human-like click (curved mouse path, randomized landing point) + self-healing",
            f"smart_click(page, {_repr(selector)}, role={_repr(semantic.get('role'))}, name={_repr(semantic.get('name'))})",
        ]
    if selector:
        return [
            f"# human-like click (curved mouse path, randomized landing point)",
            f"page.locator({_repr(selector)}).first.click()",
        ]
    return ["# human_click() targeted an accessibility ref -- resolve a stable selector first"]


def _map_human_type(args, kwargs, semantic=None):
    selector = kwargs.get("selector") or (args[0] if args else None)
    text = kwargs.get("text") or (args[1] if len(args) > 1 else "")
    if selector and semantic and semantic.get("name"):
        return [
            "# human-like typing (variable per-character delay) + self-healing",
            f"smart_type(page, {_repr(selector)}, {_repr(text)}, role={_repr(semantic.get('role'))}, name={_repr(semantic.get('name'))})",
        ]
    if selector:
        return [
            "# human-like typing (variable per-character delay)",
            f"page.locator({_repr(selector)}).first.fill('')",
            f"page.locator({_repr(selector)}).first.type({_repr(text)}, delay=120)",
        ]
    return ["# human_type() targeted an accessibility ref -- resolve a stable selector first"]


def _map_switch_tab(args, kwargs, semantic=None):
    index = _arg(args, kwargs, 0, "index", 0)
    return [
        f"page = context.pages[{int(index)}]",
        "page.bring_to_front()",
    ]


def _map_new_tab(args, kwargs, semantic=None):
    return ["page = context.new_page()"]


def _map_upload_file(args, kwargs, semantic=None):
    selector = _arg(args, kwargs, 0, "selector")
    files = _arg(args, kwargs, 1, "file_paths", [])
    files = [files] if isinstance(files, str) else files
    return [f"page.locator({_repr(selector)}).first.set_input_files({_repr(files)})"]


def _map_drag_and_drop(args, kwargs, semantic=None):
    source = _arg(args, kwargs, 0, "source_selector")
    target = _arg(args, kwargs, 1, "target_selector")
    return [f"page.locator({_repr(source)}).first.drag_to(page.locator({_repr(target)}).first)"]


def _map_execute_js(args, kwargs, semantic=None):
    script = _arg(args, kwargs, 0, "script", "")
    return [f"page.evaluate({_repr(script)})"]


def _map_export_pdf(args, kwargs, semantic=None):
    path = kwargs.get("path") or "output.pdf"
    return [f"page.pdf(path={_repr(path)})"]


def _map_assert_goal_state(args, kwargs, semantic=None):
    expected_domain = (semantic or {}).get("expected_domain")
    if expected_domain:
        return [f"assert_url_contains(page, {_repr(expected_domain)})"]
    return ["# goal completed but no target domain was recorded to assert against"]


_ACTION_MAP = {
    "navigate": _map_navigate,
    "open_site": _map_open_site,
    "click": _map_click,
    "type": _map_type,
    "press": _map_press,
    "scroll": _map_scroll,
    "wait": _map_wait,
    "screenshot": _map_screenshot,
    "human_click": _map_human_click,
    "human_type": _map_human_type,
    "switch_tab": _map_switch_tab,
    "new_tab": _map_new_tab,
    "upload_file": _map_upload_file,
    "drag_and_drop": _map_drag_and_drop,
    "execute_js": _map_execute_js,
    "export_pdf": _map_export_pdf,
    "__assert_goal_state__": _map_assert_goal_state,
}


async def get_recordable_actions():
    """List which recorded action names codegen currently knows how to translate into code."""
    return {"success": True, "supported_actions": sorted(_ACTION_MAP.keys())}


# ============================================================
# SCRIPT ASSEMBLY
# ============================================================

_SCRIPT_HEADER = '''"""
Auto-generated by Raj Browser MCP codegen.
Replays a recorded session as a standalone Playwright script --
no Claude/MCP needed to run this.

Includes self-healing clicks/types: if a site redesign breaks a
frozen CSS selector, smart_click()/smart_type() fall back to
finding the element by its recorded semantic role + accessible
name (fuzzy text match) instead of failing outright.

Connects to an already-running Chrome with:
    chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\\\\ChromeAutomation"
"""

from playwright.sync_api import sync_playwright
from difflib import SequenceMatcher
import time


CDP_URL = "http://127.0.0.1:9222"


def _find_semantic_candidates(page):
    """Tag every interactive element on the page with a temp id and describe its role+name."""
    return page.evaluate("""() => {
        const tagRoles = {A:'link', BUTTON:'button', INPUT:'textbox', TEXTAREA:'textbox', SELECT:'combobox'};
        const els = Array.from(document.querySelectorAll('a, button, input, textarea, select, [role]'));
        return els.map((el, i) => {
            const role = el.getAttribute('role') || tagRoles[el.tagName] || 'generic';
            const name = (el.getAttribute('aria-label') || el.innerText || el.value || el.placeholder || '').trim().slice(0, 80);
            el.setAttribute('data-heal-id', String(i));
            return { index: i, role: role, name: name };
        });
    }""")


def _best_semantic_match(page, role, name):
    candidates = _find_semantic_candidates(page)
    best, best_score = None, 0.0
    for c in candidates:
        role_score = 1.0 if role and c["role"] == role else 0.5
        name_score = SequenceMatcher(None, (name or "").lower(), (c["name"] or "").lower()).ratio() if name else 0.0
        score = role_score * 0.3 + name_score * 0.7
        if score > best_score:
            best_score, best = score, c
    return best, best_score


def smart_click(page, selector, role=None, name=None, timeout=3000):
    """Click by selector; if that fails, self-heal by role+accessible-name."""
    try:
        loc = page.locator(selector).first
        loc.wait_for(state="visible", timeout=timeout)
        loc.click()
        return
    except Exception:
        pass

    if not role and not name:
        raise RuntimeError(f"Selector {selector!r} failed and no semantic fallback info was recorded.")

    print(f"[self-heal] selector {selector!r} failed -- searching by role={role!r} name={name!r}...")
    best, score = _best_semantic_match(page, role, name)
    if best is None or score < 0.4:
        raise RuntimeError(f"Self-healing failed: nothing resembling role={role!r} name={name!r} found on the page.")

    print(f"[self-heal] matched '{best['name']}' (role={best['role']}, score={score:.2f}) -- healed, clicking it.")
    page.locator(f'[data-heal-id="{best["index"]}"]').first.click()


def smart_type(page, selector, text, role=None, name=None, timeout=3000):
    """Type by selector; if that fails, self-heal by role+accessible-name."""
    try:
        loc = page.locator(selector).first
        loc.wait_for(state="visible", timeout=timeout)
        loc.fill('')
        loc.type(text)
        return
    except Exception:
        pass

    if not role and not name:
        raise RuntimeError(f"Selector {selector!r} failed and no semantic fallback info was recorded.")

    print(f"[self-heal] selector {selector!r} failed -- searching by role={role!r} name={name!r}...")
    best, score = _best_semantic_match(page, role, name)
    if best is None or score < 0.4:
        raise RuntimeError(f"Self-healing failed: nothing resembling role={role!r} name={name!r} found on the page.")

    print(f"[self-heal] matched '{best['name']}' (role={best['role']}, score={score:.2f}) -- healed, typing into it.")
    healed = page.locator(f'[data-heal-id="{best["index"]}"]').first
    healed.fill('')
    healed.type(text)


# ------------------------------------------------------------
# READY-TO-USE ASSERTIONS -- verify the replay actually worked,
# not just that every step ran without raising an exception.
# ------------------------------------------------------------

def assert_url_contains(page, substring):
    assert substring in page.url, f"Expected URL to contain {substring!r}, got {page.url!r}"
    print(f"[assert] OK -- URL contains {substring!r}")


def assert_text_present(page, text, timeout=5000):
    page.wait_for_function(
        "(t) => document.body.innerText.includes(t)", arg=text, timeout=timeout,
    )
    print(f"[assert] OK -- page contains text {text!r}")


def assert_element_visible(page, selector, timeout=5000):
    page.locator(selector).first.wait_for(state="visible", timeout=timeout)
    print(f"[assert] OK -- element {selector!r} is visible")


def run():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.pages[-1] if context.pages else context.new_page()

'''

_SCRIPT_FOOTER = '''

if __name__ == "__main__":
    run()
'''


async def generate_playwright_code(limit: int = 500):
    """
    Build a standalone Playwright Python script from the recorded
    action history. Actions codegen doesn't have a mapping for
    are still included, as a comment, so the script is a complete
    record even where it can't auto-translate every step.
    """
    try:
        history_result = history.get_history(limit=limit)
        entries = history_result.get("history", [])

        if not entries:
            return {
                "success": False,
                "error": (
                    "No recorded actions to generate code from. Run some "
                    "actions via browser_agent(), or log manual steps with "
                    "browser_log_action(), then try again."
                ),
            }

        lines = []
        unmapped = 0

        for entry in entries:
            action = entry.get("action", "")
            details = entry.get("details", {}) or {}
            args = tuple(details.get("args", ()) or ())
            kwargs = dict(details.get("kwargs", {}) or {})

            mapper = _ACTION_MAP.get(action)

            if mapper is None:
                unmapped += 1
                lines.append(
                    f"        # [unmapped action] {action}(args={args!r}, kwargs={kwargs!r})"
                )
                continue

            try:
                for code_line in mapper(args, kwargs, details.get("semantic")):
                    lines.append(f"        {code_line}")
            except Exception as map_error:
                lines.append(f"        # [codegen error mapping {action}]: {map_error}")

        body = "\n".join(lines) if lines else "        pass"
        script = _SCRIPT_HEADER + body + _SCRIPT_FOOTER

        return {
            "success": True,
            "action_count": len(entries),
            "unmapped_count": unmapped,
            "code": script,
        }

    except Exception as error:
        return {"success": False, "error": str(error)}


async def export_codegen_script(path: str = None, limit: int = 500):
    """Generate the script and write it to a .py file."""
    try:
        generated = await generate_playwright_code(limit=limit)
        if not generated.get("success"):
            return generated

        if not path:
            out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "codegen")
            os.makedirs(out_dir, exist_ok=True)
            path = os.path.join(out_dir, f"session_{int(time.time())}.py")
        else:
            os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            f.write(generated["code"])

        return {
            "success": True,
            "path": path,
            "action_count": generated["action_count"],
            "unmapped_count": generated["unmapped_count"],
        }

    except Exception as error:
        return {"success": False, "error": str(error)}


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "get_recordable_actions",
    "generate_playwright_code",
    "export_codegen_script",
]
