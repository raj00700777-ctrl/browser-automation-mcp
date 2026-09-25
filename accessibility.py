import asyncio
from typing import Optional

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
# REF -> SELECTOR
# ============================================================

def _ref_selector(ref: str) -> str:
    """
    Every element in a snapshot is tagged with a stable
    data-raj-ref attribute. This converts a ref like "e12"
    back into a CSS selector that can be used with the
    existing interaction.py / extraction.py functions.
    """
    if not isinstance(ref, str) or not ref.strip():
        raise ValueError("ref cannot be empty.")

    ref = ref.strip()
    return f'[data-raj-ref="{ref}"]'


# ============================================================
# ACCESSIBILITY SNAPSHOT (JS SIDE)
# ============================================================

_SNAPSHOT_JS = r"""
() => {
    const MAX_NODES = 2500;
    let counter = 0;

    // Wipe any refs left over from a previous snapshot so
    // stale attributes never leak between calls.
    document.querySelectorAll('[data-raj-ref]').forEach(el => {
        el.removeAttribute('data-raj-ref');
    });

    function accessibleName(el) {
        const aria = el.getAttribute('aria-label');
        if (aria) return aria.trim();

        const labelledBy = el.getAttribute('aria-labelledby');
        if (labelledBy) {
            const parts = labelledBy
                .split(/\s+/)
                .map(id => document.getElementById(id))
                .filter(Boolean)
                .map(n => n.innerText || n.textContent || '');
            if (parts.length) return parts.join(' ').trim();
        }

        if (el.id) {
            const lbl = document.querySelector(`label[for="${el.id}"]`);
            if (lbl) return (lbl.innerText || '').trim();
        }

        if (el.tagName === 'IMG' && el.alt) return el.alt.trim();

        if (el.placeholder) return el.placeholder.trim();

        if (el.value && ['INPUT', 'TEXTAREA', 'BUTTON'].includes(el.tagName)) {
            return String(el.value).trim();
        }

        const text = (el.innerText || el.textContent || '').trim();
        return text.slice(0, 120);
    }

    function role(el) {
        const explicit = el.getAttribute('role');
        if (explicit) return explicit;

        const tag = el.tagName.toLowerCase();
        const type = (el.getAttribute('type') || '').toLowerCase();

        const map = {
            a: el.hasAttribute('href') ? 'link' : 'generic',
            button: 'button',
            input: type === 'checkbox' ? 'checkbox'
                : type === 'radio' ? 'radio'
                : type === 'submit' || type === 'button' ? 'button'
                : 'textbox',
            textarea: 'textbox',
            select: 'combobox',
            img: 'img',
            h1: 'heading', h2: 'heading', h3: 'heading',
            h4: 'heading', h5: 'heading', h6: 'heading',
            nav: 'navigation',
            form: 'form',
            table: 'table',
            ul: 'list', ol: 'list',
            li: 'listitem',
        };

        return map[tag] || null;
    }

    function isInteractive(el) {
        const tag = el.tagName.toLowerCase();
        const interactiveTags = [
            'a', 'button', 'input', 'textarea', 'select', 'option',
        ];
        if (interactiveTags.includes(tag)) return true;
        if (el.hasAttribute('onclick')) return true;
        if (el.getAttribute('role') &&
            ['button', 'link', 'checkbox', 'radio', 'tab', 'menuitem']
                .includes(el.getAttribute('role'))) {
            return true;
        }
        if (el.tabIndex !== undefined && el.tabIndex >= 0 &&
            el.tabIndex !== -1 && tag !== 'body') {
            return true;
        }
        return false;
    }

    function isVisible(el) {
        const style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden') {
            return false;
        }
        const rect = el.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
    }

    function walk(el, depth) {
        if (counter > MAX_NODES) return null;
        if (depth > 40) return null;
        if (!el || el.nodeType !== 1) return null;

        const tag = el.tagName.toLowerCase();
        if (['script', 'style', 'noscript', 'svg', 'path'].includes(tag)) {
            return null;
        }

        const visible = isVisible(el);
        const interactive = isInteractive(el);
        const elRole = role(el);

        let node = null;

        if (visible && (interactive || elRole)) {
            counter++;
            const ref = 'e' + counter;
            el.setAttribute('data-raj-ref', ref);

            node = {
                ref: ref,
                role: elRole || 'generic',
                name: accessibleName(el),
                interactive: interactive,
                tag: tag,
                disabled: !!(el.disabled),
                checked: el.checked !== undefined ? !!el.checked : null,
                value: (tag === 'input' || tag === 'textarea' || tag === 'select')
                    ? String(el.value || '') : null,
                children: [],
            };
        }

        const childNodes = [];
        for (const child of el.children) {
            const built = walk(child, depth + 1);
            if (built) childNodes.push(built);
        }

        // Pierce open shadow roots (Shadow DOM) -- web components
        // (custom design systems, YouTube's own player chrome,
        // many modern chat/checkout widgets) hide their real
        // markup inside el.shadowRoot, which normal DOM traversal
        // never sees. Closed shadow roots are intentionally
        // inaccessible from JS by browser design and can't be
        // pierced this way, but the vast majority of real-world
        // components use open mode.
        if (el.shadowRoot) {
            for (const shadowChild of el.shadowRoot.children) {
                const built = walk(shadowChild, depth + 1);
                if (built) {
                    built.in_shadow_dom = true;
                    childNodes.push(built);
                }
            }
        }

        if (node) {
            node.children = childNodes;
            return node;
        }

        if (childNodes.length === 1) return childNodes[0];
        if (childNodes.length > 1) {
            return {
                ref: null,
                role: 'generic',
                name: '',
                interactive: false,
                tag: tag,
                children: childNodes,
            };
        }

        return null;
    }

    const tree = walk(document.body, 0);

    return {
        tree: tree || { role: 'generic', children: [] },
        node_count: counter,
        truncated: counter > MAX_NODES,
        url: window.location.href,
        title: document.title,
    };
}
"""


# ============================================================
# PUBLIC: TAKE SNAPSHOT
# ============================================================

async def browser_snapshot():
    """
    Build a ref-based accessibility snapshot of the current page.

    Unlike CSS-selector scraping, every meaningful element gets
    a stable ref (e.g. "e12") tagged directly on the DOM via
    data-raj-ref. Those refs can then be passed to click_ref(),
    type_ref(), hover_ref() etc. so automation does not depend
    on fragile class names or generated selectors.
    """
    try:
        page = await _get_page()

        result = await page.evaluate(_SNAPSHOT_JS)

        return {
            "success": True,
            "action": "browser_snapshot",
            "url": result.get("url"),
            "title": result.get("title"),
            "node_count": result.get("node_count"),
            "truncated": result.get("truncated"),
            "tree": result.get("tree"),
        }

    except Exception as error:
        return {
            "success": False,
            "action": "browser_snapshot",
            "error": str(error),
        }


# ============================================================
# PUBLIC: RESOLVE A REF TO A SELECTOR
# ============================================================

async def resolve_ref(ref: str):
    """
    Confirm a ref from the last snapshot still exists on the
    page, and return the CSS selector that targets it.
    """
    try:
        page = await _get_page()
        selector = _ref_selector(ref)

        count = await page.locator(selector).count()

        if count == 0:
            return {
                "success": False,
                "action": "resolve_ref",
                "ref": ref,
                "error": (
                    "ref not found on page. The page may have "
                    "changed since the last browser_snapshot() call "
                    "-- take a new snapshot."
                ),
            }

        return {
            "success": True,
            "action": "resolve_ref",
            "ref": ref,
            "selector": selector,
        }

    except Exception as error:
        return {
            "success": False,
            "action": "resolve_ref",
            "ref": ref,
            "error": str(error),
        }


# ============================================================
# PUBLIC: REF-BASED ACTIONS
# ============================================================
#
# These simply translate a ref into the matching data-raj-ref
# selector and delegate to the existing, already-tested
# interaction.py functions -- so click_ref/type_ref inherit the
# same human-like delays, visibility waits, and safety checks
# as the selector-based tools, without duplicating that logic.

async def click_ref(ref: str, timeout: int = 10000, force: bool = False):
    import interaction

    check = await resolve_ref(ref)
    if not check.get("success"):
        return check

    result = await interaction.click_element(
        check["selector"],
        timeout=timeout,
        force=force,
    )
    result["ref"] = ref
    return result


async def type_ref(
    ref: str,
    text: str,
    clear: bool = True,
    timeout: int = 10000,
):
    import interaction

    check = await resolve_ref(ref)
    if not check.get("success"):
        return check

    result = await interaction.type_text(
        check["selector"],
        text,
        clear=clear,
        timeout=timeout,
    )
    result["ref"] = ref
    return result


async def hover_ref(ref: str, timeout: int = 10000):
    import interaction

    check = await resolve_ref(ref)
    if not check.get("success"):
        return check

    result = await interaction.hover_element(
        check["selector"],
        timeout=timeout,
    )
    result["ref"] = ref
    return result


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "browser_snapshot",
    "resolve_ref",
    "click_ref",
    "type_ref",
    "hover_ref",
]
