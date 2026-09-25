"""
Raj Browser MCP — iframe / Frame Support

Every function that previously only worked on the main page can
now be scoped to a specific iframe using Playwright's
frame_locator(), which auto-waits for the iframe to attach and
load -- no manual polling needed.

Frames are targeted by the CSS selector of the <iframe> element
itself (e.g. "iframe#payment-frame" or "iframe[name='checkout']"),
found via list_frames().
"""

from browser import browser


# ============================================================
# PAGE ACCESS
# ============================================================

async def _get_page():
    page = await browser.get_page()

    if page is None:
        raise RuntimeError("No active browser page available.")

    return page


def _normalize_timeout(timeout: int) -> int:
    return max(100, int(timeout))


# ============================================================
# DISCOVERY
# ============================================================

async def list_frames():
    """
    List every frame currently attached to the page, including
    the main frame, with enough info to target one with the
    frame_* functions below.
    """
    try:
        page = await _get_page()

        frames = []
        for f in page.frames:
            try:
                el = await f.frame_element()
                selector_hint = None
                if el is not None:
                    name = await el.get_attribute("name")
                    fid = await el.get_attribute("id")
                    if fid:
                        selector_hint = f'iframe#{fid}'
                    elif name:
                        selector_hint = f'iframe[name="{name}"]'
            except Exception:
                selector_hint = None

            frames.append({
                "url": f.url,
                "name": f.name,
                "is_main_frame": f == page.main_frame,
                "suggested_selector": selector_hint,
            })

        return {"success": True, "count": len(frames), "frames": frames}

    except Exception as error:
        return {"success": False, "error": str(error)}


def _frame_locator(page, iframe_selector: str, inner_selector: str):
    if not isinstance(iframe_selector, str) or not iframe_selector.strip():
        raise ValueError("iframe_selector cannot be empty.")
    if not isinstance(inner_selector, str) or not inner_selector.strip():
        raise ValueError("inner_selector cannot be empty.")

    return page.frame_locator(iframe_selector).locator(inner_selector).first


# ============================================================
# INTERACTION INSIDE A FRAME
# ============================================================

async def frame_click(iframe_selector: str, inner_selector: str, timeout: int = 10000):
    try:
        page = await _get_page()
        locator = _frame_locator(page, iframe_selector, inner_selector)

        await locator.click(timeout=_normalize_timeout(timeout))

        return {
            "success": True,
            "action": "frame_click",
            "iframe": iframe_selector,
            "selector": inner_selector,
        }

    except Exception as error:
        return {
            "success": False,
            "action": "frame_click",
            "iframe": iframe_selector,
            "selector": inner_selector,
            "error": str(error),
        }


async def frame_type(
    iframe_selector: str,
    inner_selector: str,
    text: str,
    clear: bool = True,
    timeout: int = 10000,
):
    try:
        page = await _get_page()
        locator = _frame_locator(page, iframe_selector, inner_selector)

        timeout = _normalize_timeout(timeout)

        if clear:
            await locator.fill("", timeout=timeout)

        await locator.type(text, timeout=timeout)

        return {
            "success": True,
            "action": "frame_type",
            "iframe": iframe_selector,
            "selector": inner_selector,
            "text_length": len(text or ""),
        }

    except Exception as error:
        return {
            "success": False,
            "action": "frame_type",
            "iframe": iframe_selector,
            "selector": inner_selector,
            "error": str(error),
        }


async def frame_hover(iframe_selector: str, inner_selector: str, timeout: int = 10000):
    try:
        page = await _get_page()
        locator = _frame_locator(page, iframe_selector, inner_selector)

        await locator.hover(timeout=_normalize_timeout(timeout))

        return {
            "success": True,
            "action": "frame_hover",
            "iframe": iframe_selector,
            "selector": inner_selector,
        }

    except Exception as error:
        return {
            "success": False,
            "action": "frame_hover",
            "iframe": iframe_selector,
            "selector": inner_selector,
            "error": str(error),
        }


# ============================================================
# READING INSIDE A FRAME
# ============================================================

async def frame_get_text(iframe_selector: str, inner_selector: str = "body", timeout: int = 10000):
    try:
        page = await _get_page()
        locator = _frame_locator(page, iframe_selector, inner_selector)

        await locator.wait_for(state="attached", timeout=_normalize_timeout(timeout))
        text = await locator.inner_text()

        return {
            "success": True,
            "action": "frame_get_text",
            "iframe": iframe_selector,
            "selector": inner_selector,
            "text": text,
        }

    except Exception as error:
        return {
            "success": False,
            "action": "frame_get_text",
            "iframe": iframe_selector,
            "selector": inner_selector,
            "error": str(error),
        }


async def frame_extract_links(iframe_selector: str):
    try:
        page = await _get_page()
        frame_loc = page.frame_locator(iframe_selector)

        links = await frame_loc.locator("a[href]").evaluate_all(
            "els => els.map(e => ({ text: (e.innerText || '').trim(), href: e.href }))"
        )

        return {
            "success": True,
            "action": "frame_extract_links",
            "iframe": iframe_selector,
            "count": len(links),
            "links": links,
        }

    except Exception as error:
        return {
            "success": False,
            "action": "frame_extract_links",
            "iframe": iframe_selector,
            "error": str(error),
        }


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "list_frames",
    "frame_click",
    "frame_type",
    "frame_hover",
    "frame_get_text",
    "frame_extract_links",
]
