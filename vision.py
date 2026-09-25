"""
Raj Browser MCP
Vision / Page Observation Engine

Responsibilities:
- Full-page screenshots
- Viewport screenshots
- Page state
- Viewport geometry
- Scroll information
- Visible element inventory
- Interactive element inventory
- Basic visual/page diagnostics

Compatibility:
- Existing server.py interface preserved:
    screenshot()
    viewport_screenshot()
    page_state()
"""

import os
from datetime import datetime

from browser import browser


SCREENSHOT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "screenshots"
)


# ============================================================
# INTERNAL
# ============================================================

async def _get_page():
    return await browser.get_page()


def _ensure_screenshot_dir():
    os.makedirs(
        SCREENSHOT_DIR,
        exist_ok=True,
    )


def _timestamp():
    return datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )


async def _safe_title(page):
    try:
        return await page.title()
    except Exception:
        return ""


async def _safe_evaluate(page, script, default=None):
    try:
        return await page.evaluate(script)
    except Exception:
        return default


# ============================================================
# FULL SCREENSHOT
# ============================================================

async def screenshot(path: str = None):
    """
    Capture the complete page.
    """

    try:
        page = await _get_page()

        if not path:
            _ensure_screenshot_dir()

            path = os.path.join(
                SCREENSHOT_DIR,
                f"page_{_timestamp()}.png",
            )

        await page.screenshot(
            path=path,
            full_page=True,
        )

        return {
            "success": True,
            "action": "screenshot",
            "path": path,
            "url": page.url,
            "title": await _safe_title(page),
            "full_page": True,
        }

    except Exception as error:
        return {
            "success": False,
            "action": "screenshot",
            "error": str(error),
        }


# ============================================================
# VIEWPORT SCREENSHOT
# ============================================================

async def viewport_screenshot():
    """
    Capture only the currently visible viewport.
    """

    try:
        page = await _get_page()

        _ensure_screenshot_dir()

        path = os.path.join(
            SCREENSHOT_DIR,
            f"viewport_{_timestamp()}.png",
        )

        await page.screenshot(
            path=path,
            full_page=False,
        )

        return {
            "success": True,
            "action": "viewport_screenshot",
            "path": path,
            "url": page.url,
            "title": await _safe_title(page),
            "full_page": False,
        }

    except Exception as error:
        return {
            "success": False,
            "action": "viewport_screenshot",
            "error": str(error),
        }


# ============================================================
# PAGE STATE
# ============================================================

async def page_state():
    """
    Return detailed current page state.
    """

    try:
        page = await _get_page()

        state = await _safe_evaluate(
            page,
            """
            () => {
                const doc = document.documentElement;
                const body = document.body;

                return {
                    viewport: {
                        width: window.innerWidth,
                        height: window.innerHeight
                    },

                    scroll: {
                        x: window.scrollX,
                        y: window.scrollY
                    },

                    document: {
                        width: doc ? doc.scrollWidth : 0,
                        height: doc ? doc.scrollHeight : 0
                    },

                    body: {
                        width: body ? body.scrollWidth : 0,
                        height: body ? body.scrollHeight : 0
                    },

                    readyState: document.readyState,

                    visibleTextLength:
                        body && body.innerText
                            ? body.innerText.length
                            : 0,

                    links:
                        document.querySelectorAll(
                            "a"
                        ).length,

                    images:
                        document.querySelectorAll(
                            "img"
                        ).length,

                    buttons:
                        document.querySelectorAll(
                            "button"
                        ).length,

                    inputs:
                        document.querySelectorAll(
                            "input, textarea, select"
                        ).length
                };
            }
            """,
            default={},
        )

        return {
            "success": True,
            "action": "page_state",
            "url": page.url,
            "title": await _safe_title(page),
            **state,
        }

    except Exception as error:
        return {
            "success": False,
            "action": "page_state",
            "error": str(error),
        }


# ============================================================
# VISIBLE ELEMENT INVENTORY
# ============================================================

async def visible_elements(limit: int = 200):
    """
    Return visible elements useful for browser agents.
    """

    try:
        page = await _get_page()

        limit = max(
            1,
            min(int(limit), 500),
        )

        elements = await page.evaluate(
            """
            (limit) => {

                const selectors = [
                    "a",
                    "button",
                    "input",
                    "textarea",
                    "select",
                    "[role='button']",
                    "[role='link']",
                    "[contenteditable='true']"
                ];

                const output = [];

                for (const selector of selectors) {

                    const nodes =
                        document.querySelectorAll(
                            selector
                        );

                    for (const element of nodes) {

                        if (
                            output.length >= limit
                        ) {
                            break;
                        }

                        const rect =
                            element.getBoundingClientRect();

                        const style =
                            window.getComputedStyle(
                                element
                            );

                        const visible =
                            rect.width > 0 &&
                            rect.height > 0 &&
                            style.visibility !== "hidden" &&
                            style.display !== "none";

                        if (!visible) {
                            continue;
                        }

                        output.push({
                            tag: element.tagName.toLowerCase(),

                            text:
                                (
                                    element.innerText ||
                                    element.value ||
                                    element.getAttribute("aria-label") ||
                                    ""
                                )
                                .trim()
                                .slice(0, 300),

                            aria:
                                element.getAttribute(
                                    "aria-label"
                                ),

                            role:
                                element.getAttribute(
                                    "role"
                                ),

                            id:
                                element.id || null,

                            name:
                                element.getAttribute(
                                    "name"
                                ),

                            type:
                                element.getAttribute(
                                    "type"
                                ),

                            href:
                                element.getAttribute(
                                    "href"
                                ),

                            placeholder:
                                element.getAttribute(
                                    "placeholder"
                                ),

                            rect: {
                                x: Math.round(rect.x),
                                y: Math.round(rect.y),
                                width: Math.round(rect.width),
                                height: Math.round(rect.height)
                            }
                        });
                    }

                    if (
                        output.length >= limit
                    ) {
                        break;
                    }
                }

                return output;
            }
            """,
            limit,
        )

        return {
            "success": True,
            "action": "visible_elements",
            "url": page.url,
            "count": len(elements),
            "elements": elements,
        }

    except Exception as error:
        return {
            "success": False,
            "action": "visible_elements",
            "error": str(error),
        }


# ============================================================
# VIEWPORT INFORMATION
# ============================================================

async def viewport_info():
    """
    Return viewport and scroll geometry.
    """

    try:
        page = await _get_page()

        result = await _safe_evaluate(
            page,
            """
            () => ({
                width: window.innerWidth,
                height: window.innerHeight,

                scrollX: window.scrollX,
                scrollY: window.scrollY,

                documentWidth:
                    document.documentElement.scrollWidth,

                documentHeight:
                    document.documentElement.scrollHeight,

                atTop:
                    window.scrollY <= 0,

                atBottom:
                    Math.ceil(
                        window.scrollY +
                        window.innerHeight
                    ) >=
                    document.documentElement.scrollHeight
            })
            """,
            default={},
        )

        return {
            "success": True,
            "action": "viewport_info",
            "url": page.url,
            **result,
        }

    except Exception as error:
        return {
            "success": False,
            "action": "viewport_info",
            "error": str(error),
        }


# ============================================================
# VISUAL DIAGNOSTICS
# ============================================================

async def visual_diagnostics():
    """
    Compact agent-oriented visual/page diagnostics.
    """

    try:
        page = await _get_page()

        result = await _safe_evaluate(
            page,
            """
            () => {

                const body = document.body;

                const visible = (element) => {

                    if (!element) {
                        return false;
                    }

                    const rect =
                        element.getBoundingClientRect();

                    const style =
                        window.getComputedStyle(
                            element
                        );

                    return (
                        rect.width > 0 &&
                        rect.height > 0 &&
                        style.display !== "none" &&
                        style.visibility !== "hidden"
                    );
                };

                return {

                    readyState:
                        document.readyState,

                    hasBody:
                        !!body,

                    bodyText:
                        body && body.innerText
                            ? body.innerText
                                .trim()
                                .slice(0, 1000)
                            : "",

                    visibleButtons:
                        Array.from(
                            document.querySelectorAll(
                                "button, [role='button']"
                            )
                        )
                        .filter(visible)
                        .length,

                    visibleLinks:
                        Array.from(
                            document.querySelectorAll(
                                "a"
                            )
                        )
                        .filter(visible)
                        .length,

                    visibleInputs:
                        Array.from(
                            document.querySelectorAll(
                                "input, textarea, select"
                            )
                        )
                        .filter(visible)
                        .length,

                    images:
                        document.querySelectorAll(
                            "img"
                        ).length
                };
            }
            """,
            default={},
        )

        return {
            "success": True,
            "action": "visual_diagnostics",
            "url": page.url,
            "title": await _safe_title(page),
            "diagnostics": result,
        }

    except Exception as error:
        return {
            "success": False,
            "action": "visual_diagnostics",
            "error": str(error),
        }


# ============================================================
# ELEMENT-SPECIFIC SCREENSHOTS
# ============================================================
#
# Playwright's own locator.screenshot() already crops to a single
# element -- the extras here are what most tools skip:
#   - padding around the crop (via page.screenshot(clip=...) with
#     an expanded, viewport-clamped box, not just the raw element
#     bounding box)
#   - a temporary visible highlight border before capture, so it's
#     obvious which element the crop is showing
#   - capturing SEVERAL named elements in one call

async def element_screenshot(
    selector: str,
    path: str = None,
    padding: int = 0,
    highlight: bool = False,
    timeout: int = 10000,
):
    """
    Screenshot just one element (e.g. a single chart or table),
    not the whole page. padding expands the crop by N pixels on
    every side (clamped to the viewport). highlight=True draws a
    temporary red outline around the element before capturing, so
    it's visually obvious what was captured.
    """
    try:
        page = await _get_page()
        _ensure_screenshot_dir()

        locator = page.locator(selector).first
        await locator.wait_for(state="visible", timeout=timeout)
        await locator.scroll_into_view_if_needed()

        box = await locator.bounding_box()
        if not box:
            return {"success": False, "action": "element_screenshot", "error": "Could not compute element bounding box."}

        viewport = page.viewport_size or {"width": 1280, "height": 800}
        clip = {
            "x": max(0, box["x"] - padding),
            "y": max(0, box["y"] - padding),
            "width": min(viewport["width"] - max(0, box["x"] - padding), box["width"] + padding * 2),
            "height": min(viewport["height"] - max(0, box["y"] - padding), box["height"] + padding * 2),
        }

        applied_highlight = False
        if highlight:
            try:
                await page.evaluate(
                    "(sel) => { const el = document.querySelector(sel); if (el) el.setAttribute('data-raj-highlight-prev-outline', el.style.outline || ''); if (el) el.style.outline = '4px solid #ff3355'; }",
                    selector,
                )
                applied_highlight = True
            except Exception:
                pass

        if not path:
            path = os.path.join(SCREENSHOT_DIR, f"element_{int(datetime.now().timestamp())}.png")
        else:
            os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)

        await page.screenshot(path=path, clip=clip)

        if applied_highlight:
            try:
                await page.evaluate(
                    "(sel) => { const el = document.querySelector(sel); if (el) el.style.outline = el.getAttribute('data-raj-highlight-prev-outline') || ''; }",
                    selector,
                )
            except Exception:
                pass

        return {
            "success": True,
            "action": "element_screenshot",
            "selector": selector,
            "path": path,
            "padding": padding,
            "clip": clip,
        }

    except Exception as error:
        return {"success": False, "action": "element_screenshot", "error": str(error)}


async def multi_element_screenshot(selectors: list, padding: int = 0, timeout: int = 10000):
    """Screenshot several named elements in one call (e.g. every chart on a dashboard)."""
    results = []
    for selector in selectors:
        result = await element_screenshot(selector, padding=padding, timeout=timeout)
        results.append(result)

    return {
        "success": any(r.get("success") for r in results),
        "action": "multi_element_screenshot",
        "count": len(results),
        "results": results,
    }